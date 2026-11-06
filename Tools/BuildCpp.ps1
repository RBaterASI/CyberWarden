# Artifact Signing integration v2. Signing is OFF unless the per-user config exists and says "Required"; see Docs/NPC/ArtifactSigning_Setup.md and Tools/BuildCppSigning.Tests.ps1.
# Builds the CyberWarden editor target and, when signing is switched on in the per-user config, signs the project's module DLL with a Microsoft
# Artifact Signing Public Trust certificate profile so that Smart App Control (policy VerifiedAndReputableDesktop) accepts it.
#
#   powershell -ExecutionPolicy Bypass -File Tools\BuildCpp.ps1                 build, then sign if the config says Mode "Required"
#   ... -VerifyOnly       build nothing, sign nothing: the DLL must carry a valid signature that this script recorded (no Azure access)
#   ... -PreflightOnly    build nothing, sign nothing: check config, tools and the Azure CLI session
#   ... -ForceResign      sign again even when the recorded signature is current
#
# Signing is OFF unless %LOCALAPPDATA%\CyberWarden\ArtifactSigning\config.json (or the file named by CW_SIGN_CONFIG) exists and says "Mode": "Required".
# Without that file the script is the old build script plus a warning that the DLL is unsigned.
#
# Exit codes: the Unreal Build Tool exit code when the build fails; otherwise
#   0 ok | 1 unexpected error | 20 config | 21 tools | 22 Azure authentication | 23 signing failed | 24 signature verification / policy failure
#   25 DLL changed while it was being signed | 26 lock or DLL replacement problem
param(
	[string]$Configuration = "Development",
	[switch]$VerifyOnly,
	[switch]$PreflightOnly,
	[switch]$ForceResign
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$project = Split-Path $PSScriptRoot -Parent
$uproject = Join-Path $project "CyberWarden.uproject"
$stateDir = Join-Path $project "Saved\ArtifactSigning"           # generated, ignored by Git (.gitignore: Saved/); same volume as Binaries\, which atomic replacement needs
$statePath = Join-Path $stateDir "state.json"
$logPath = Join-Path $stateDir "sign.log"
$workRoot = Join-Path $stateDir "work"
$configPath = if ($env:CW_SIGN_CONFIG) { $env:CW_SIGN_CONFIG } else { Join-Path $env:LOCALAPPDATA "CyberWarden\ArtifactSigning\config.json" }   # per user, outside the repository
$targets = @( (Join-Path $project "Binaries\Win64\UnrealEditor-CyberWarden.dll") )   # the only module the project builds; add paths here if more appear
$timestampUrl = "http://timestamp.acs.microsoft.com"                # certificates live three days, so a trusted timestamp is mandatory
$defaultRoot = "Microsoft Identity Verification Root Certificate Authority 2020"   # Public Trust chain root (confirm on the first real signature, then pin ExpectedRootThumbprint)
$lockName = "Global\CyberWardenBuildAndSign"
$retryDelaySeconds = 5                                              # between the two signing attempts
$replaceAttempts = 5
$replaceDelayMilliseconds = 300
$script:ExitCode = 0
$script:KeepWorkDir = $false

function Write-Log([string]$Message) {
	$line = "{0:u} {1}" -f (Get-Date), $Message
	Write-Host $line
	try { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null; Add-Content -LiteralPath $logPath -Value $line } catch { }
}

function Fail([int]$Code, [string]$Message) {
	Write-Log "SIGNING FAILED [$Code]: $Message"
	$script:ExitCode = $Code
	throw "CWSIGN:$Code"
}

# Runs a native tool without PowerShell turning its stderr into terminating errors. Out is stdout only (safe to parse), Err is stderr, Code is the exit code.
function Invoke-Native([string]$File, [string[]]$Arguments) {
	$previous = $ErrorActionPreference
	$ErrorActionPreference = "Continue"
	try {
		$out = New-Object System.Collections.Generic.List[string]
		$err = New-Object System.Collections.Generic.List[string]
		& $File @Arguments 2>&1 | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $err.Add("$_") } else { $out.Add("$_") } }
		$code = $LASTEXITCODE
		return [pscustomobject]@{ Code = $code; Out = ($out -join "`n"); Err = ($err -join "`n"); Text = ((@($out) + @($err)) -join "`n") }
	} finally { $ErrorActionPreference = $previous }
}

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
function Short-Hash($Hash) { $h = "$Hash"; if ($h.Length -gt 12) { $h.Substring(0, 12) } else { $h } }   # for log lines only; a damaged manifest must not crash the run
function Test-Contains([string]$Text, [string]$Needle) { $Text -and $Needle -and ($Text.IndexOf($Needle, [StringComparison]::OrdinalIgnoreCase) -ge 0) }

# Small wrappers so the logic above them can be tested offline with mocks.
function Test-AzAvailable { [bool](Get-Command az -ErrorAction SilentlyContinue) }
function Test-UnrealRunning { [bool](Get-Process -Name "UnrealEditor*" -ErrorAction SilentlyContinue) }
function Get-CertCommonName($Cert) { $Cert.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) }
function Get-CertChainRoot($Cert) {
	$chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
	$chain.ChainPolicy.RevocationMode = [System.Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck   # only inspected here: trust is judged by Authenticode and signtool
	[void]$chain.Build($Cert)
	return $chain.ChainElements[$chain.ChainElements.Count - 1].Certificate
}
function Invoke-UnrealBuild {
	$global:LASTEXITCODE = -1          # a build that never reports an exit code counts as a failure, never as a stale 0
	& "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" CyberWardenEditor Win64 $Configuration "-project=$uproject" -WaitMutex -NoHotReload | Out-Host
	return [int]$global:LASTEXITCODE
}

# ---------------------------------------------------------------- configuration (per user, outside Git, no secrets in it)
function Read-SigningConfig {
	if (-not (Test-Path -LiteralPath $configPath)) { return $null }
	$repoPrefix = ([System.IO.Path]::GetFullPath($project)).TrimEnd("\") + "\"
	if (([System.IO.Path]::GetFullPath($configPath)).StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
		Fail 20 "the signing config must live outside the repository ($configPath): keep it in %LOCALAPPDATA%\CyberWarden\ArtifactSigning\ so it can never be committed"
	}
	try { $cfg = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } catch { Fail 20 "config $configPath is not valid JSON: $($_.Exception.Message)" }
	if (-not ($cfg.PSObject.Properties.Name -contains "Mode") -or $cfg.Mode -cnotin "Off", "Required") { Fail 20 "config Mode must be exactly 'Off' or 'Required'" }
	if ($cfg.Mode -ceq "Off") { return $cfg }     # an unfinished config can neither activate signing nor break a build while it says Off
	foreach ($name in "Endpoint", "Account", "Profile", "TenantId", "SubscriptionId", "ExpectedCommonName", "DlibPath") {
		if (-not ($cfg.PSObject.Properties.Name -contains $name) -or [string]::IsNullOrWhiteSpace([string]$cfg.$name)) { Fail 20 "config is missing '$name' ($configPath)" }
	}
	if ($cfg.Endpoint -notmatch '^https://[a-z0-9]+\.codesigning\.azure\.net/?$') { Fail 20 "Endpoint must be a regional https://<region>.codesigning.azure.net URI" }
	if ($cfg.Account -notmatch '^[A-Za-z][A-Za-z0-9-]{1,22}[A-Za-z0-9]$') { Fail 20 "Account is not a valid Artifact Signing account name" }
	if ($cfg.Profile -notmatch '^[A-Za-z][A-Za-z0-9-]{3,98}[A-Za-z0-9]$') { Fail 20 "Profile is not a valid certificate profile name" }
	foreach ($name in "TenantId", "SubscriptionId") { if ($cfg.$name -notmatch '^[0-9a-fA-F-]{36}$') { Fail 20 "$name must be a GUID" } }
	if ($cfg.ExpectedCommonName -match '^\s*CN\s*=') { Fail 20 "ExpectedCommonName is the plain validated legal name without 'CN='" }
	return $cfg
}

# ---------------------------------------------------------------- tools
function Resolve-SigningTools($cfg) {
	$sdkBin = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
	$sdk = Get-ChildItem -LiteralPath $sdkBin -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^10\.0\.(\d+)\.\d+$' -and [int]$Matches[1] -ge 22621 } |
		Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
	$signtool = if ($cfg.PSObject.Properties.Name -contains "SigntoolPath" -and $cfg.SigntoolPath) { $cfg.SigntoolPath } elseif ($sdk) { Join-Path $sdk.FullName "x64\signtool.exe" } else { $null }
	if (-not $signtool -or -not (Test-Path -LiteralPath $signtool)) { Fail 21 "x64 signtool.exe from Windows SDK 10.0.22621 or newer not found (the 20348 SDK does not work with the dlib)" }
	if (-not (Test-Path -LiteralPath $cfg.DlibPath)) { Fail 21 "Artifact Signing dlib not found at $($cfg.DlibPath)" }
	foreach ($tool in $signtool, $cfg.DlibPath) {   # supply chain: only Microsoft-signed tools may handle the signing request
		$s = Get-AuthenticodeSignature -LiteralPath $tool
		if ($s.Status -ne "Valid" -or -not (Test-Contains $s.SignerCertificate.Subject "O=Microsoft Corporation")) { Fail 21 "$tool is not validly signed by Microsoft Corporation (status $($s.Status))" }
	}
	$runtimes = (Invoke-Native "dotnet" @("--list-runtimes")).Out
	if ($runtimes -notmatch 'Microsoft\.NETCore\.App 8\.') { Fail 21 ".NET 8 runtime (Microsoft.NETCore.App 8.x) is not installed; the dlib needs it" }
	return [pscustomobject]@{ SignTool = $signtool; Dlib = $cfg.DlibPath }
}

# ---------------------------------------------------------------- Azure authentication: Azure CLI session only, no secrets handled by this script
function Assert-AzureSession($cfg) {
	foreach ($name in "AZURE_CLIENT_SECRET", "AZURE_PASSWORD", "AZURE_CLIENT_CERTIFICATE_PATH", "AZURE_FEDERATED_TOKEN_FILE") {
		if (Test-Path "Env:$name") { Fail 22 "environment variable $name is set: remove it. Signing uses the interactive Azure CLI session only; no secret or alternative identity may be present in the environment" }
	}
	if (-not (Test-AzAvailable)) { Fail 22 "Azure CLI (az) is not installed" }
	$show = Invoke-Native "az" @("account", "show", "--output", "json")
	if ($show.Code -ne 0) { Fail 22 "no Azure CLI session: run 'az login' (interactive)" }
	try { $acct = $show.Out | ConvertFrom-Json } catch { Fail 22 "'az account show' did not return readable JSON" }
	if ($acct.tenantId -ne $cfg.TenantId -or $acct.id -ne $cfg.SubscriptionId) { Fail 22 "the Azure CLI session is not on the configured tenant/subscription (found tenant $($acct.tenantId), subscription $($acct.id)): refusing to sign" }
	# Prints only the expiry, never the token. Proves a token for the signing service can be obtained without a prompt.
	$tok = Invoke-Native "az" @("account", "get-access-token", "--resource", "https://codesigning.azure.net", "--query", "expiresOn", "--output", "tsv")
	if ($tok.Code -ne 0) { Fail 22 "the Azure CLI session cannot get a token for Artifact Signing: run 'az login' again" }
}

# ---------------------------------------------------------------- signature verification (fail closed)
# Ok means ALL of: Authenticode Valid (signature intact for these exact bytes, chain trusted on this machine, timestamp honoured), the signer's common name is exactly the
# validated legal name, a timestamp from the Microsoft authority is present, Code Signing usage, the chain ends at the Public Trust root, and signtool verify /pa passes.
function Test-SignedDll([string]$Path, $cfg, $tools) {
	$sig = Get-AuthenticodeSignature -LiteralPath $Path
	$no = { param($why) [pscustomobject]@{ Ok = $false; Reason = $why; Sig = $sig } }
	if ($sig.Status -ne "Valid") { return (& $no "Authenticode status $($sig.Status)") }
	$cert = $sig.SignerCertificate
	if (-not $cert) { return (& $no "no signer certificate") }
	$cn = Get-CertCommonName $cert
	if ($cn -ne $cfg.ExpectedCommonName) { return (& $no "signer is '$cn', expected exactly '$($cfg.ExpectedCommonName)'") }
	if (-not $sig.TimeStamperCertificate) { return (& $no "no timestamp (a three-day certificate is worthless without one)") }
	$tsa = if ($cfg.PSObject.Properties.Name -contains "ExpectedTimestampAuthority" -and $cfg.ExpectedTimestampAuthority) { $cfg.ExpectedTimestampAuthority } else { "Microsoft" }
	if (-not (Test-Contains $sig.TimeStamperCertificate.Subject $tsa)) { return (& $no "timestamp authority is '$($sig.TimeStamperCertificate.Subject)', expected '$tsa'") }
	if (-not (($cert.EnhancedKeyUsageList | ForEach-Object { $_.ObjectId }) -contains "1.3.6.1.5.5.7.3.3")) { return (& $no "certificate has no Code Signing usage") }
	$root = Get-CertChainRoot $cert
	$expectedRoot = if ($cfg.PSObject.Properties.Name -contains "ExpectedRoot" -and $cfg.ExpectedRoot) { $cfg.ExpectedRoot } else { $defaultRoot }
	if (-not (Test-Contains $root.Subject $expectedRoot)) { return (& $no "chain root is '$($root.Subject)', not the Public Trust root '$expectedRoot' (a Public Trust Test profile is not trusted)") }
	if ($cfg.PSObject.Properties.Name -contains "ExpectedRootThumbprint" -and $cfg.ExpectedRootThumbprint -and $root.Thumbprint -ne $cfg.ExpectedRootThumbprint) { return (& $no "chain root thumbprint $($root.Thumbprint) is not the pinned one") }
	$v = Invoke-Native $tools.SignTool @("verify", "/pa", "/v", $Path)
	if ($v.Code -ne 0) { return (& $no "signtool verify /pa failed (exit $($v.Code))") }
	return [pscustomobject]@{ Ok = $true; Reason = "valid"; Sig = $sig }
}

# ---------------------------------------------------------------- manifest: which exact file this script signed and verified (one entry per DLL path)
# It proves "these exact bytes were signed and verified here at that time". It cannot prove the DLL is current with respect to the source: that is Unreal Build Tool's job,
# and UBT always runs first in the same invocation. It is not a security boundary against code running as you; the Authenticode signature is.
function Read-State {
	if (-not (Test-Path -LiteralPath $statePath)) { return $null }
	try { return (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json) } catch { return $null }   # unreadable or half-written means "no record": more verification, never less
}
function Get-StateEntry([string]$Dll) {
	$state = Read-State
	if (-not $state -or -not ($state.PSObject.Properties.Name -contains "Entries")) { return $null }
	return (@($state.Entries) | Where-Object { $_.Path -eq $Dll } | Select-Object -First 1)
}
function Write-StateEntry([string]$Dll, [string]$UnsignedHash, [string]$SignedHash, $Sig) {
	New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
	$state = Read-State
	$others = @()
	if ($state -and ($state.PSObject.Properties.Name -contains "Entries")) { $others = @(@($state.Entries) | Where-Object { $_.Path -ne $Dll }) }   # not via an if-expression: that would unroll a one-element array
	$entry = [pscustomobject]@{ Path = $Dll; UnsignedSha256 = $UnsignedHash; SignedSha256 = $SignedHash; SignedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
		SignerThumbprint = $Sig.SignerCertificate.Thumbprint; CommonName = (Get-CertCommonName $Sig.SignerCertificate) }
	$tmp = "$statePath.tmp"
	[pscustomobject]@{ Entries = @(@($others) + @($entry)) } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $tmp -Encoding UTF8
	Move-Item -LiteralPath $tmp -Destination $statePath -Force           # a crash can leave the old manifest or a .tmp file, never a half-written manifest
}

function Write-DlibMetadata($cfg) {
	$dir = Join-Path $env:LOCALAPPDATA "CyberWarden\ArtifactSigning"
	New-Item -ItemType Directory -Force -Path $dir | Out-Null
	$path = Join-Path $dir ("metadata-" + [guid]::NewGuid().ToString("N") + ".json")
	# Identifiers only, never a secret. Every credential type except the Azure CLI session is excluded, so no other identity can be picked up by accident.
	# (Credential type names are confirmed against metadata.sample.json of the installed dlib during setup.)
	[ordered]@{
		Endpoint = $cfg.Endpoint; CodeSigningAccountName = $cfg.Account; CertificateProfileName = $cfg.Profile
		CorrelationId = "cyberwarden-" + $env:COMPUTERNAME
		ExcludeCredentials = @("EnvironmentCredential", "ManagedIdentityCredential", "WorkloadIdentityCredential", "SharedTokenCacheCredential", "VisualStudioCredential",
			"VisualStudioCodeCredential", "AzurePowerShellCredential", "AzureDeveloperCliCredential", "InteractiveBrowserCredential")
	} | ConvertTo-Json | Set-Content -LiteralPath $path -Encoding UTF8
	return $path
}

function Restore-Original([string]$Dll, [string]$Backup) {
	try { if ($Backup -and (Test-Path -LiteralPath $Backup)) { [System.IO.File]::Copy($Backup, $Dll, $true); Write-Log "restored the file that was in place before signing: $Dll" } }
	catch { $script:KeepWorkDir = $true; Write-Log "COULD NOT RESTORE ${Dll}: $($_.Exception.Message). The previous file is kept at $Backup" }
}

function Sign-OneDll([string]$Dll, $cfg, $tools) {
	if (-not (Test-Path -LiteralPath $Dll)) { Fail 24 "$Dll does not exist (did the build produce it?)" }
	$hash = Get-Sha256 $Dll
	$check = Test-SignedDll $Dll $cfg $tools
	if ((Get-Sha256 $Dll) -ne $hash) { Fail 25 "$Dll changed while it was being examined (another build?)" }
	$entry = Get-StateEntry $Dll
	$recorded = $entry -and $entry.SignedSha256 -eq $hash
	if ($check.Ok -and $recorded -and -not $ForceResign) { Write-Log "up to date: $Dll is signed and recorded (sha256 $(Short-Hash $hash)...), nothing to do"; return }
	if ($VerifyOnly) {
		Fail 24 ("$Dll fails verification: " + $(if ($check.Ok) { "the signature is valid but this exact file was not recorded as signed and verified by this script" } else { $check.Reason }))
	}
	if ($entry -and $entry.SignedSha256 -ne $hash) { Write-Log "the DLL differs from the one this script signed (was $(Short-Hash $entry.SignedSha256)..., now $(Short-Hash $hash)...): a build replaced it" }

	# Signature policy. A fresh build output is unsigned. An existing signature is replaced only when it is OUR OWN (the signer's common name is the validated one) and the signature
	# itself is intact (Valid, or NotTrusted because the certificate has expired / lacks a timestamp / came from the wrong profile). A foreign signature, or a signature of ours over
	# different bytes (HashMismatch: the DLL was modified after signing) is never overwritten: that needs a human to look at it.
	$status = "$($check.Sig.Status)"
	if ($status -ne "NotSigned") {
		$ours = $check.Sig.SignerCertificate -and ((Get-CertCommonName $check.Sig.SignerCertificate) -eq $cfg.ExpectedCommonName)
		if (-not $ours) { Fail 24 "$Dll carries a foreign or unreadable signature (status $status): not overwriting it, investigate" }
		if ($status -notin "Valid", "NotTrusted") { Fail 24 "$Dll carries our signature but its status is $status (modified after signing?): not re-signing it. Delete the file and rebuild if it is expected" }
		Write-Log "replacing our own signature ($($check.Reason))"
	}

	Assert-AzureSession $cfg                      # Azure is contacted only when something really has to be signed
	$meta = Write-DlibMetadata $cfg
	$workDir = Join-Path $workRoot ([guid]::NewGuid().ToString("N"))
	New-Item -ItemType Directory -Force -Path $workDir | Out-Null
	$work = Join-Path $workDir (Split-Path $Dll -Leaf)            # keeps the .dll name, so Authenticode treats it like the real file
	$backup = Join-Path $workDir "previous.dll"
	$installed = $false
	try {
		$signed = $false
		for ($attempt = 1; $attempt -le 2 -and -not $signed; ++$attempt) {   # at most two attempts, so a persistent failure cannot burn signing quota
			Copy-Item -LiteralPath $Dll -Destination $work -Force     # every attempt starts from a fresh copy: a failed attempt may have damaged the previous one
			$r = Invoke-Native $tools.SignTool @("sign", "/v", "/fd", "SHA256", "/tr", $timestampUrl, "/td", "SHA256", "/dlib", $tools.Dlib, "/dmdf", $meta, $work)
			if ($r.Code -eq 0) { $signed = $true } else { Write-Log "signtool attempt $attempt failed (exit $($r.Code)): $($r.Text)"; if ($attempt -lt 2) { Start-Sleep -Seconds $retryDelaySeconds } }
		}
		if (-not $signed) { Fail 23 "signtool could not sign $Dll" }
		$after = Test-SignedDll $work $cfg $tools
		if (-not $after.Ok) { Fail 24 "the signed copy does not verify: $($after.Reason)" }
		$signedHash = Get-Sha256 $work
		if ((Get-Sha256 $Dll) -ne $hash) { Fail 25 "$Dll changed while it was being signed (a build replaced it): not installing the signature of the old file" }
		if (Test-UnrealRunning) { Fail 26 "an Unreal Editor process is running and may hold ${Dll} - close it and build again" }

		$replaced = $false
		$lastError = ""
		for ($i = 1; $i -le $replaceAttempts -and -not $replaced; ++$i) {   # antivirus and indexers hold files for a moment: a short bounded retry, then fail
			try { [System.IO.File]::Replace($work, $Dll, $backup); $replaced = $true }
			catch [System.IO.IOException], [System.UnauthorizedAccessException] { $lastError = $_.Exception.Message; Start-Sleep -Milliseconds $replaceDelayMilliseconds }
		}
		if (-not $replaced) {
			if (-not (Test-Path -LiteralPath $Dll)) { Restore-Original $Dll $backup }   # ReplaceFile can fail after having moved the old file away
			Fail 26 "could not replace $Dll with the signed copy after $replaceAttempts attempts: $lastError"
		}
		$installed = $true
		# The file that was just replaced must be exactly the one that was signed. If a build swapped the DLL in the last instant, put that newer file back.
		if ((Get-Sha256 $backup) -ne $hash) { Restore-Original $Dll $backup; $installed = $false; Fail 25 "the DLL changed during the final swap (a newer build appeared): its file has been put back and is not signed" }
		$final = Test-SignedDll $Dll $cfg $tools     # the file that Unreal will load, verified in place
		if (-not $final.Ok) { Restore-Original $Dll $backup; $installed = $false; Fail 24 "$Dll does not verify after installation: $($final.Reason)" }
		if ((Get-Sha256 $Dll) -ne $signedHash) { Fail 25 "$Dll was replaced right after the signed copy was installed" }
		Write-StateEntry $Dll $hash $signedHash $final.Sig
		Write-Log "signed and verified: $Dll (sha256 $(Short-Hash $signedHash)..., signer $(Get-CertCommonName $final.Sig.SignerCertificate))"
	} finally {
		Remove-Item -LiteralPath $meta -Force -ErrorAction SilentlyContinue
		if (-not $script:KeepWorkDir) { Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue }   # kept only when the previous DLL could not be put back
	}
}

# ---------------------------------------------------------------- lock: one build-and-sign at a time
function Enter-BuildLock([string]$Name, [int]$TimeoutSeconds = 600) {
	$m = New-Object System.Threading.Mutex($false, $Name)
	$got = $false
	try { $got = $m.WaitOne([TimeSpan]::FromSeconds($TimeoutSeconds)) }
	catch [System.Threading.AbandonedMutexException] { $got = $true; Write-Log "the previous build/sign run died while holding the lock; continuing" }
	if (-not $got) { $m.Dispose(); Fail 26 "another build/sign run has held the lock for more than $TimeoutSeconds s" }
	return $m
}
function Exit-BuildLock($Mutex) { try { $Mutex.ReleaseMutex() } catch { }; $Mutex.Dispose() }

# ---------------------------------------------------------------- main
function Invoke-Main {   # a function so that 'return' ends only this part and the exit code at the bottom is always reported
	$cfg = Read-SigningConfig
	$signing = [bool]($cfg -and $cfg.Mode -ceq "Required")
	Write-Log ("signing mode: " + $(if ($signing) { "Required" } else { "Off" }) + " (config: $configPath)")
	$tools = $null
	if ($signing) { $tools = Resolve-SigningTools $cfg }

	if ($PreflightOnly) {
		if (-not $signing) { Write-Log "preflight: signing is OFF"; return }
		Assert-AzureSession $cfg
		Write-Log "preflight OK: config, tools ($($tools.SignTool)) and the Azure CLI session are ready"
		return
	}
	if ($VerifyOnly) {
		if (-not $signing) { Fail 20 "-VerifyOnly needs a config with Mode 'Required'" }
		foreach ($dll in $targets) { Sign-OneDll $dll $cfg $tools }
		return
	}

	# 1. The unchanged build (same command as the current script). Signing never runs after a failed build, and nothing builds after signing.
	$buildExit = Invoke-UnrealBuild
	if ($buildExit -ne 0) { $script:ExitCode = $buildExit; Write-Log "build failed with exit code $buildExit; nothing was signed"; return }

	# 2. Signing. When it is off the DLL stays unsigned and Smart App Control will refuse it: say so loudly instead of pretending.
	if (-not $signing) {
		Write-Log "WARNING: signing is OFF: $($targets -join ', ') is NOT signed and Smart App Control may block it"
		return
	}
	foreach ($dll in $targets) { Sign-OneDll $dll $cfg $tools }
}

if ($MyInvocation.InvocationName -ne ".") {    # dot-sourcing (the offline tests) loads the functions without running anything
	$lock = $null
	try {
		$lock = Enter-BuildLock $lockName       # held for the whole build + sign + verify, released only in 'finally'
		Invoke-Main
	}
	catch {
		if ($_.Exception.Message -notlike "CWSIGN:*") { Write-Log "UNEXPECTED ERROR: $($_.Exception.Message)"; $script:ExitCode = 1 }
	}
	finally {
		if ($lock) { Exit-BuildLock $lock }
	}
	exit $script:ExitCode
}
