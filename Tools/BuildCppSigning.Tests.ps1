# Offline tests for BuildCpp.proposed.ps1. They never start Unreal, Azure, az, dotnet, signtool or Build.bat: every native call goes through a mock that THROWS for anything unknown,
# Get-AuthenticodeSignature is replaced by a fake that understands a toy signature format, and all files live in a temporary directory.
#   powershell -NoProfile -ExecutionPolicy Bypass -File BuildCppSigning.Tests.ps1 [-Script <path to the script under test>]
param([string]$Script = (Join-Path $PSScriptRoot "BuildCpp.ps1"))
$ErrorActionPreference = "Stop"
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("cwsign-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $root | Out-Null
$env:LOCALAPPDATA = Join-Path $root "LocalAppData"          # so nothing is ever written to the real profile
$env:CW_SIGN_CONFIG = Join-Path $root "no-config.json"
foreach ($n in "AZURE_CLIENT_SECRET", "AZURE_PASSWORD", "AZURE_CLIENT_CERTIFICATE_PATH", "AZURE_FEDERATED_TOKEN_FILE") { Remove-Item "Env:$n" -ErrorAction SilentlyContinue }

. $Script            # dot-sourcing only defines the functions (the main block is skipped)
# From here on nothing may be written next to the script under test (for example the real Saved\ArtifactSigning of the repository): redirect state and log into the temp directory.
$script:stateDir = Join-Path $root "early-state"; $script:statePath = Join-Path $script:stateDir "state.json"; $script:logPath = Join-Path $script:stateDir "sign.log"; $script:workRoot = Join-Path $script:stateDir "work"

# ---------------------------------------------------------------- harness
$script:Pass = 0; $script:FailCount = 0
function Check([bool]$Condition, [string]$Name) { if ($Condition) { $script:Pass++ } else { $script:FailCount++; Write-Host "  FAIL: $Name" -ForegroundColor Red } }
function Expect-Fail([int]$Code, [string]$Name, [scriptblock]$Block) {
	$script:ExitCode = 0; $threw = $false
	try { & $Block } catch { if ($_.Exception.Message -like "CWSIGN:*") { $threw = $true } else { Write-Host "  unexpected: $($_.Exception.Message)" -ForegroundColor Yellow } }
	Check ($threw -and $script:ExitCode -eq $Code) "$Name (expected fail code $Code, got threw=$threw exit=$($script:ExitCode))"
}
function Expect-Ok([string]$Name, [scriptblock]$Block) {
	$script:ExitCode = 0; $ok = $true
	try { & $Block } catch { $ok = $false; Write-Host "  unexpected: $($_.Exception.Message)" -ForegroundColor Yellow }
	Check ($ok -and $script:ExitCode -eq 0) $Name
}
function Bytes([string]$Path) { [System.IO.File]::ReadAllBytes($Path) }
$sha = [System.Security.Cryptography.SHA256]::Create()
function HexSha([byte[]]$b) { ([BitConverter]::ToString($sha.ComputeHash($b))).Replace("-", "") }
function Same([string]$Path, [byte[]]$Expected) { (HexSha (Bytes $Path)) -eq (HexSha $Expected) }
$latin1 = [System.Text.Encoding]::GetEncoding(28591)
$Marker = "`n#SIG|"

# Toy signature: the base bytes followed by "\n#SIG|cn|timestamp|root|expired|sha256(base)".
function Strip-Signature([byte[]]$b) { $t = $latin1.GetString($b); $i = $t.LastIndexOf($Marker); if ($i -lt 0) { return $b } return ,[byte[]]($latin1.GetBytes($t.Substring(0, $i))) }
function Add-FakeSignature([string]$Path, [string]$Cn, [int]$Ts = 1, [string]$Root = "Microsoft Identity Verification Root Certificate Authority 2020", [int]$Expired = 0) {
	$base = Strip-Signature (Bytes $Path)
	$tail = $latin1.GetBytes("$Marker$Cn|$Ts|$Root|$Expired|$(HexSha $base)")
	[System.IO.File]::WriteAllBytes($Path, [byte[]]($base + $tail))
}
function Get-AuthenticodeSignature {
	param([string]$LiteralPath, [string]$FilePath)
	$b = Bytes $LiteralPath; $t = $latin1.GetString($b); $i = $t.LastIndexOf($Marker)
	if ($i -lt 0) { return [pscustomobject]@{ Status = "NotSigned"; SignerCertificate = $null; TimeStamperCertificate = $null } }
	$f = $t.Substring($i + $Marker.Length).Split("|")
	$intact = (HexSha ([byte[]]$latin1.GetBytes($t.Substring(0, $i)))) -eq $f[4]
	$status = if (-not $intact) { "HashMismatch" } elseif ($f[3] -eq "1") { "NotTrusted" } else { "Valid" }
	$cert = [pscustomobject]@{ Subject = "CN=$($f[0]), L=Test, S=TX, C=US"; Thumbprint = "AAAA"; CN = $f[0]; Root = $f[2]
		EnhancedKeyUsageList = @([pscustomobject]@{ ObjectId = "1.3.6.1.5.5.7.3.3" }) }
	$tsa = if ($f[1] -eq "1") { [pscustomobject]@{ Subject = "CN=Microsoft Public RSA Time Stamping Authority" } } elseif ($f[1] -eq "2") { [pscustomobject]@{ Subject = "CN=Some Other Timestamp Service" } } else { $null }
	[pscustomobject]@{ Status = $status; SignerCertificate = $cert; TimeStamperCertificate = $tsa }
}
function Get-CertCommonName($Cert) { $Cert.CN }
function Get-CertChainRoot($Cert) { [pscustomobject]@{ Subject = "CN=$($Cert.Root)"; Thumbprint = "ROOT1" } }
function Test-AzAvailable { $true }

# Every native call is mocked; an unknown one throws, which proves nothing real can be launched.
function Reset-T { $global:T = @{ SignCalls = 0; VerifyCalls = 0; AzCalls = 0; BuildCalls = 0; SignExit = 0; VerifyExit = 0; VerifyFailOn = 0; SignHook = $null; SignCN = "Ricky Test"; SignTs = 1
	SignRoot = "Microsoft Identity Verification Root Certificate Authority 2020"; AzJson = $null; AzShowExit = 0; AzTokenExit = 0; BuildExit = 0; RunningHook = $null; Natives = @() } }
function Invoke-Native([string]$File, [string[]]$Arguments) {
	$global:T.Natives += $File
	$o = { param($code, $out = "", $err = "") [pscustomobject]@{ Code = $code; Out = $out; Err = $err; Text = "$out`n$err" } }
	if ($File -like "*signtool*") {
		if ($Arguments[0] -eq "verify") { $global:T.VerifyCalls++; $c = if ($global:T.VerifyFailOn -eq $global:T.VerifyCalls) { 1 } else { $global:T.VerifyExit }; return (& $o $c) }
		if ($Arguments[0] -eq "sign") {
			$global:T.SignCalls++
			if ($global:T.SignHook) { & $global:T.SignHook $Arguments[-1] }
			if ($global:T.SignExit -ne 0) { return (& $o $global:T.SignExit "" "mock signing failure") }
			Add-FakeSignature $Arguments[-1] $global:T.SignCN $global:T.SignTs $global:T.SignRoot
			return (& $o 0)
		}
	}
	if ($File -eq "az") {
		$global:T.AzCalls++
		if ($Arguments[1] -eq "show") { return (& $o $global:T.AzShowExit $global:T.AzJson "WARNING: a noisy azure-cli warning on stderr") }
		return (& $o $global:T.AzTokenExit "2099-01-01 00:00:00.000000")
	}
	if ($File -eq "dotnet") { return (& $o 0 "Microsoft.NETCore.App 8.0.19 [x]") }
	throw "TEST MOCK: unexpected native call '$File' - nothing real may be launched"
}
function Invoke-UnrealBuild { $global:T.BuildCalls++; return $global:T.BuildExit }
function Test-UnrealRunning { if ($global:T.RunningHook) { return (& $global:T.RunningHook) } return $false }

$tid = "11111111-1111-1111-1111-111111111111"; $sid = "22222222-2222-2222-2222-222222222222"
function New-Cfg([hashtable]$Over = @{}) {
	$h = @{ Mode = "Required"; Endpoint = "https://eus.codesigning.azure.net"; Account = "cwacct"; Profile = "cwprofile"; TenantId = $tid; SubscriptionId = $sid; ExpectedCommonName = "Ricky Test"; DlibPath = "x" }
	foreach ($k in $Over.Keys) { $h[$k] = $Over[$k] }
	[pscustomobject]$h
}
$tools = [pscustomobject]@{ SignTool = "C:\mock\signtool.exe"; Dlib = "C:\mock\dlib.dll" }
$cfg = New-Cfg
$script:dll = $null
function New-Env([string]$Seed = "base") {
	Reset-T
	$script:Root2 = Join-Path $root ([guid]::NewGuid().ToString("N")); New-Item -ItemType Directory -Force -Path (Join-Path $script:Root2 "Binaries\Win64") | Out-Null
	$script:stateDir = Join-Path $script:Root2 "Saved\ArtifactSigning"; $script:statePath = Join-Path $script:stateDir "state.json"; $script:logPath = Join-Path $script:stateDir "sign.log"; $script:workRoot = Join-Path $script:stateDir "work"
	$script:dll = Join-Path $script:Root2 "Binaries\Win64\UnrealEditor-CyberWarden.dll"
	[System.IO.File]::WriteAllBytes($script:dll, $latin1.GetBytes(($Seed * 400)))
	$script:retryDelaySeconds = 0; $script:replaceDelayMilliseconds = 5; $script:VerifyOnly = $false; $script:ForceResign = $false; $script:KeepWorkDir = $false
	$global:T.AzJson = ('{"id":"' + $sid + '","tenantId":"' + $tid + '"}')
}
function WriteConfig([string]$Json) { Set-Content -LiteralPath $env:CW_SIGN_CONFIG -Value $Json -Encoding UTF8 }
function RemoveConfig { Remove-Item -LiteralPath $env:CW_SIGN_CONFIG -ErrorAction SilentlyContinue }
Write-Host "== 1. configuration and default-off"
RemoveConfig
Check ($null -eq (Read-SigningConfig)) "no config file -> null (signing off)"
WriteConfig '{ "Mode": "Off" }'
Check ((Read-SigningConfig).Mode -ceq "Off") "Mode Off with no other field is accepted and does not fail"
WriteConfig '{ "Mode": "required" }'; Expect-Fail 20 "lower-case 'required' is not accepted" { Read-SigningConfig }
WriteConfig '{ "Mode": "On" }'; Expect-Fail 20 "unknown Mode rejected" { Read-SigningConfig }
WriteConfig '{ "Endpoint": "https://eus.codesigning.azure.net" }'; Expect-Fail 20 "config without Mode rejected" { Read-SigningConfig }
WriteConfig '{ not json'; Expect-Fail 20 "malformed JSON rejected, never read as Off" { Read-SigningConfig }
WriteConfig '{ "Mode": "Required" }'; Expect-Fail 20 "Required with missing fields rejected" { Read-SigningConfig }
$good = '{ "Mode":"Required","Endpoint":"https://eus.codesigning.azure.net","Account":"cwacct","Profile":"cwprofile","TenantId":"' + $tid + '","SubscriptionId":"' + $sid + '","ExpectedCommonName":"Ricky Test","DlibPath":"x" }'
WriteConfig $good; Check ((Read-SigningConfig).Mode -ceq "Required") "complete Required config accepted"
# a config inside the repository could be committed by accident: refused outright (the 'repository' here is a temp directory)
$realProject = $script:project; $realConfigPath = $script:configPath
$script:project = Join-Path $root "fake-repo"; New-Item -ItemType Directory -Force -Path $script:project | Out-Null
$script:configPath = Join-Path $script:project "ArtifactSigning.config.json"; Set-Content -LiteralPath $script:configPath -Value $good
Expect-Fail 20 "a signing config inside the repository is refused" { Read-SigningConfig }
Set-Content -LiteralPath $script:configPath -Value '{ "Mode": "Off" }'
Expect-Fail 20 "...even when it says Off" { Read-SigningConfig }
$script:project = $realProject; $script:configPath = $realConfigPath
WriteConfig ($good.Replace("eus.codesigning.azure.net", "evil.example.com")); Expect-Fail 20 "foreign endpoint rejected" { Read-SigningConfig }
WriteConfig ($good.Replace('"Ricky Test"', '"CN=Ricky Test"')); Expect-Fail 20 "CN= prefix rejected" { Read-SigningConfig }
WriteConfig ($good.Replace($tid, "not-a-guid")); Expect-Fail 20 "bad tenant id rejected" { Read-SigningConfig }

Write-Host "== 2. Invoke-Main: default off, build failure, exit-code propagation"
New-Env; RemoveConfig
Expect-Ok "no config: build runs, no error" { Invoke-Main }
Check ($T.BuildCalls -eq 1 -and $T.SignCalls -eq 0 -and $T.AzCalls -eq 0 -and $T.Natives.Count -eq 0) "no config: one build, zero signing, zero Azure, zero native calls"
WriteConfig '{ "Mode": "Off" }'; New-Env
Expect-Ok "Mode Off: build runs" { Invoke-Main }
Check ($T.BuildCalls -eq 1 -and $T.SignCalls -eq 0 -and $T.AzCalls -eq 0) "Mode Off: no signing, no Azure"
New-Env; WriteConfig $good; $global:T.BuildExit = 7
$script:ExitCode = 0
function Resolve-SigningTools($c) { $tools }
Invoke-Main
Check ($script:ExitCode -eq 7) "build exit 7 is propagated exactly"
Check ($T.SignCalls -eq 0 -and $T.AzCalls -eq 0) "build failure: nothing is signed, Azure untouched"
New-Env; $global:T.BuildExit = -1; $script:ExitCode = 0; Invoke-Main
Check ($script:ExitCode -eq -1) "a build that reports no exit code (-1 sentinel) is a failure"
New-Env; RemoveConfig; $script:ExitCode = 0
Expect-Fail 20 "-VerifyOnly with signing off is refused" { $script:VerifyOnly = $true; try { Invoke-Main } finally { $script:VerifyOnly = $false } }

Write-Host "== 3. signature verification (Public Trust, timestamp, chain)"
New-Env; $c = New-Cfg
Add-FakeSignature $dll "Ricky Test"; Check ((Test-SignedDll $dll $c $tools).Ok) "valid signature from the expected signer verifies"
Add-FakeSignature $dll "Ricky Tester"; Check (-not (Test-SignedDll $dll $c $tools).Ok) "a superstring common name is NOT the expected signer"
Add-FakeSignature $dll "ricky test"; Check ((Test-SignedDll $dll $c $tools).Ok) "common-name comparison is case-insensitive"
Add-FakeSignature $dll "Ricky Test" 0; Check (-not (Test-SignedDll $dll $c $tools).Ok) "no timestamp -> not ok"
Add-FakeSignature $dll "Ricky Test" 2; Check (-not (Test-SignedDll $dll $c $tools).Ok) "timestamp from a non-Microsoft authority -> not ok"
Add-FakeSignature $dll "Ricky Test" 1 "Some Test Root"; Check (-not (Test-SignedDll $dll $c $tools).Ok) "wrong chain root (Test profile style) -> not ok"
Add-FakeSignature $dll "Ricky Test"; Check (-not (Test-SignedDll $dll (New-Cfg @{ ExpectedRootThumbprint = "OTHER" }) $tools).Ok) "pinned root thumbprint mismatch -> not ok"
Check ((Test-SignedDll $dll (New-Cfg @{ ExpectedRootThumbprint = "ROOT1" }) $tools).Ok) "pinned root thumbprint match -> ok"
$T.VerifyExit = 1; Check (-not (Test-SignedDll $dll $c $tools).Ok) "signtool verify failure -> not ok"; $T.VerifyExit = 0
Add-FakeSignature $dll "Ricky Test"; $b = Bytes $dll; $b[10] = [byte]88; [System.IO.File]::WriteAllBytes($dll, $b)
$r = Test-SignedDll $dll $c $tools; Check ((-not $r.Ok) -and "$($r.Sig.Status)" -eq "HashMismatch") "a byte flipped after signing -> HashMismatch, not ok"

Write-Host "== 4. signing flow, up-to-date, replaced, manifest"
New-Env; $orig = Bytes $dll
Expect-Ok "unsigned DLL is signed" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq 1 -and $T.AzCalls -eq 2) "one signature, Azure checked once"
Check ((Test-SignedDll $dll $cfg $tools).Ok) "installed DLL verifies"
$entry = Get-StateEntry $dll; Check ($entry -and $entry.SignedSha256 -eq (Get-Sha256 $dll) -and $entry.UnsignedSha256 -eq (HexSha $orig)) "manifest records the signed and the unsigned hash"
Check (-not (Test-Path $workRoot) -or @(Get-ChildItem $workRoot).Count -eq 0) "work directory cleaned"
$calls = $T.SignCalls; $az = $T.AzCalls
Expect-Ok "second run" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq $calls -and $T.AzCalls -eq $az) "second run: up to date, no signing, no Azure call"
# replaced by a subsequent (unsigned) build
$newBuild = $latin1.GetBytes("NEWBUILD" * 500); [System.IO.File]::WriteAllBytes($dll, $newBuild)
Expect-Ok "replaced DLL" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq $calls + 1) "a replaced (unsigned) DLL is signed again"
Check ((Get-StateEntry $dll).SignedSha256 -eq (Get-Sha256 $dll)) "manifest follows the new file"
# modified after signing: hash mismatch must never be called valid
$b = Bytes $dll; $b[5] = [byte]90; [System.IO.File]::WriteAllBytes($dll, $b); $before = Get-Sha256 $dll; $calls = $T.SignCalls
Expect-Fail 24 "modified-after-signing DLL is refused" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq $calls -and (Get-Sha256 $dll) -eq $before) "modified DLL: not re-signed (no laundering), file untouched"
Expect-Fail 24 "-VerifyOnly refuses the modified DLL" { $script:VerifyOnly = $true; try { Sign-OneDll $dll $cfg $tools } finally { $script:VerifyOnly = $false } }
# a validly signed DLL that the manifest does not know (stale copy, lost manifest) is not adopted
New-Env; Add-FakeSignature $dll "Ricky Test"
Expect-Fail 24 "-VerifyOnly: valid signature without a manifest record is NOT accepted" { $script:VerifyOnly = $true; try { Sign-OneDll $dll $cfg $tools } finally { $script:VerifyOnly = $false } }
Expect-Ok "validly signed but unrecorded DLL is re-signed, not adopted" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq 1 -and (Get-StateEntry $dll)) "re-signed once and now recorded"
# manifest with another file's hash
$state = Read-State; $state.Entries[0].SignedSha256 = "DEADBEEF"; $state | ConvertTo-Json -Depth 4 | Set-Content $statePath
$calls = $T.SignCalls; Expect-Ok "stale manifest entry" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq $calls + 1) "manifest hash differs from the file -> not up to date -> signed again"
Set-Content -LiteralPath $statePath -Value "{ half written"; $calls = $T.SignCalls
Expect-Ok "corrupt manifest" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq $calls + 1 -and (Get-StateEntry $dll)) "corrupt manifest = no record: signed again and rewritten"
# manifest keeps one entry per DLL
$other = Join-Path $Root2 "Binaries\Win64\Other.dll"; [System.IO.File]::WriteAllBytes($other, $latin1.GetBytes("OTHER" * 300))
Expect-Ok "second DLL" { Sign-OneDll $other $cfg $tools }
Check ((Get-StateEntry $dll) -and (Get-StateEntry $other)) "two DLLs, two manifest entries"

Write-Host "== 5. expired, untimestamped and foreign signatures"
New-Env; Add-FakeSignature $dll "Ricky Test" 0   # ours, valid but no timestamp
Expect-Ok "own untimestamped signature is replaced" { Sign-OneDll $dll $cfg $tools }; Check ($T.SignCalls -eq 1 -and (Test-SignedDll $dll $cfg $tools).Ok) "...with a verified timestamped one"
New-Env; Add-FakeSignature $dll "Ricky Test" 1 "Microsoft Identity Verification Root Certificate Authority 2020" 1   # ours, expired -> NotTrusted
Expect-Ok "own expired signature is replaced" { Sign-OneDll $dll $cfg $tools }; Check ($T.SignCalls -eq 1 -and (Test-SignedDll $dll $cfg $tools).Ok) "...and the result verifies"
New-Env; Add-FakeSignature $dll "Somebody Else"; $before = Get-Sha256 $dll
Expect-Fail 24 "foreign valid signature is refused" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq 0 -and $T.AzCalls -eq 0 -and (Get-Sha256 $dll) -eq $before) "foreign signature: no Azure call, no signing, file untouched"
New-Env; Add-FakeSignature $dll "Somebody Else"; $b = Bytes $dll; $b[3] = [byte]77; [System.IO.File]::WriteAllBytes($dll, $b)
Expect-Fail 24 "foreign + modified signature is refused" { Sign-OneDll $dll $cfg $tools }

Write-Host "== 6. fail-closed signing paths, replacement, races"
New-Env; $orig = Bytes $dll; $T.SignExit = 1
Expect-Fail 23 "signing failure" { Sign-OneDll $dll $cfg $tools }
Check ($T.SignCalls -eq 2 -and (Same $dll $orig) -and -not (Get-StateEntry $dll)) "two attempts only, DLL untouched, nothing recorded"
New-Env; $orig = Bytes $dll; $T.SignCN = "Wrong Person"
Expect-Fail 24 "signed copy with the wrong publisher does not verify" { Sign-OneDll $dll $cfg $tools }
Check ((Same $dll $orig) -and -not (Get-StateEntry $dll)) "wrong-publisher copy was never installed"
New-Env; $orig = Bytes $dll; $T.SignRoot = "Some Test Root"
Expect-Fail 24 "signed copy from a Test-profile chain does not verify" { Sign-OneDll $dll $cfg $tools }
Check (Same $dll $orig) "Test-profile copy was never installed"
New-Env; $orig = Bytes $dll; $T.VerifyFailOn = 2    # 1st verify = signed copy, 2nd = the installed file
Expect-Fail 24 "verification of the installed file fails" { Sign-OneDll $dll $cfg $tools }
Check ((Same $dll $orig) -and -not (Get-StateEntry $dll)) "installed file that fails verification is rolled back to the previous file"
New-Env; $newer = $latin1.GetBytes("BUILDER" * 500); $d = $dll
$T.SignHook = { param($work) [System.IO.File]::WriteAllBytes($d, $newer) }
Expect-Fail 25 "DLL replaced while it was being signed" { Sign-OneDll $dll $cfg $tools }
Check ((Same $dll $newer) -and -not (Get-StateEntry $dll)) "the newer build is untouched and not recorded"
New-Env; $newer = $latin1.GetBytes("LATEBUILD" * 500); $d = $dll
$T.RunningHook = { [System.IO.File]::WriteAllBytes($d, $newer); $false }   # swapped in the instant between the last check and the replacement
Expect-Fail 25 "DLL replaced during the final swap" { Sign-OneDll $dll $cfg $tools }
Check ((Same $dll $newer) -and -not (Get-StateEntry $dll)) "the newer build was put back, unsigned, and nothing recorded"
New-Env; $orig = Bytes $dll; $T.RunningHook = { $true }
Expect-Fail 26 "Unreal running" { Sign-OneDll $dll $cfg $tools }
Check (Same $dll $orig) "Unreal running: DLL untouched"
New-Env; $orig = Bytes $dll; $d = $dll; $script:lockStream = $null
$T.RunningHook = { $script:lockStream = [System.IO.File]::Open($d, "Open", "Read", "None"); $false }   # something holds the file open exclusively
try { Expect-Fail 26 "locked DLL cannot be replaced" { Sign-OneDll $dll $cfg $tools } } finally { if ($script:lockStream) { $script:lockStream.Dispose() } }
Check ((Same $dll $orig) -and -not (Get-StateEntry $dll)) "locked DLL: intact after the bounded retries, nothing recorded"
Check (-not (Test-Path $workRoot) -or @(Get-ChildItem $workRoot).Count -eq 0) "no work files left behind after failures"
Check (@(Get-ChildItem (Split-Path $dll)).Count -eq 1) "no temp files next to the DLL"
New-Env; $T.SignHook = { param($work) if ($work -notlike "*\work\*") { throw "signing must happen on a copy in the work directory" } }
Expect-Ok "signing works on a copy" { Sign-OneDll $dll $cfg $tools }

Write-Host "== 7. Azure authentication and metadata"
New-Env; $env:AZURE_CLIENT_SECRET = "x"
Expect-Fail 22 "AZURE_CLIENT_SECRET in the environment is refused" { Assert-AzureSession $cfg }; Remove-Item Env:AZURE_CLIENT_SECRET
Check ($T.AzCalls -eq 0) "...before az is even called"
New-Env; $T.AzShowExit = 1; Expect-Fail 22 "not logged in" { Assert-AzureSession $cfg }
New-Env; $T.AzJson = ('{"id":"' + $sid + '","tenantId":"99999999-9999-9999-9999-999999999999"}'); Expect-Fail 22 "wrong tenant" { Assert-AzureSession $cfg }
New-Env; $T.AzJson = ('{"id":"99999999-9999-9999-9999-999999999999","tenantId":"' + $tid + '"}'); Expect-Fail 22 "wrong subscription" { Assert-AzureSession $cfg }
New-Env; $T.AzTokenExit = 1; Expect-Fail 22 "no token for the signing service" { Assert-AzureSession $cfg }
New-Env; $T.AzJson = "not json"; Expect-Fail 22 "unreadable az output fails closed with 22" { Assert-AzureSession $cfg }
New-Env; Expect-Ok "correct session passes even though az printed a warning on stderr" { Assert-AzureSession $cfg }
$m = Write-DlibMetadata $cfg; $j = Get-Content $m -Raw | ConvertFrom-Json
Check ((Test-Path $m) -and $j.Endpoint -eq $cfg.Endpoint -and $j.ExcludeCredentials -contains "EnvironmentCredential" -and $j.ExcludeCredentials -notcontains "AzureCliCredential") "metadata: identifiers only, Azure CLI is the only credential left"
$allowed = @("Endpoint", "CodeSigningAccountName", "CertificateProfileName", "CorrelationId", "ExcludeCredentials")
Check (@($j.PSObject.Properties.Name | Where-Object { $allowed -notcontains $_ }).Count -eq 0) "metadata has only the five identifier/exclusion fields: no secret, token or key field"
Remove-Item $m -Force
New-Env; Expect-Ok "metadata removed after signing" { Sign-OneDll $dll $cfg $tools }
Check (@(Get-ChildItem (Join-Path $env:LOCALAPPDATA "CyberWarden\ArtifactSigning") -Filter "metadata-*.json" -ErrorAction SilentlyContinue).Count -eq 0) "no metadata file left behind"

Write-Host "== 8. lock covers the whole run"
$name = "Local\cwsign-test-" + [guid]::NewGuid().ToString("N")
$m1 = Enter-BuildLock $name 5
$rs = [runspacefactory]::CreateRunspace(); $rs.Open(); $ps = [powershell]::Create(); $ps.Runspace = $rs
[void]$ps.AddScript({ param($n) $m = New-Object System.Threading.Mutex($false, $n); $got = $m.WaitOne(0); if ($got) { $m.ReleaseMutex() }; $m.Dispose(); $got }).AddArgument($name)
Check (-not ($ps.Invoke()[0])) "a second build/sign cannot take the lock while the first holds it"
Exit-BuildLock $m1
$ps.Commands.Clear(); [void]$ps.AddScript({ param($n) $m = New-Object System.Threading.Mutex($false, $n); $got = $m.WaitOne(0); if ($got) { $m.ReleaseMutex() }; $m.Dispose(); $got }).AddArgument($name)
Check ($ps.Invoke()[0]) "the lock is free again once released"
$ps.Dispose(); $rs.Dispose()
$m1 = Enter-BuildLock $name 5
$rs = [runspacefactory]::CreateRunspace(); $rs.Open(); $pw = [powershell]::Create(); $pw.Runspace = $rs
[void]$pw.AddScript({ param($f, $n, $r) . $f; $stateDir = $r; $logPath = Join-Path $r "lock.log"; Enter-BuildLock $n 1 }).AddArgument($Script).AddArgument($name).AddArgument($root)
$msg = ""; try { $null = $pw.Invoke() } catch { $msg = $_.Exception.ToString() }
Check ($msg -like "*CWSIGN:26*") "waiting for a held lock times out with code 26"
$pw.Dispose(); $rs.Dispose(); Exit-BuildLock $m1
$src = Get-Content $Script -Raw
$iLock = $src.IndexOf('$lock = Enter-BuildLock'); $iMain = $src.IndexOf("Invoke-Main", $iLock); $iFin = $src.IndexOf("Exit-BuildLock", $iMain)
Check ($iLock -gt 0 -and $iMain -gt $iLock -and $iFin -gt $iMain) "structure: lock is taken before Invoke-Main and released after it, in 'finally'"

Write-Host "== 9. real process exit codes (child PowerShell; no build, no Azure, no Unreal)"
function Run-Child([string]$ScriptPath, [string[]]$ChildArgs, [hashtable]$Env = @{}) {
	$psi = New-Object System.Diagnostics.ProcessStartInfo; $psi.FileName = "powershell.exe"; $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
	$psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" " + ($ChildArgs -join " ")
	foreach ($k in $Env.Keys) { $psi.EnvironmentVariables[$k] = $Env[$k] }
	$p = [System.Diagnostics.Process]::Start($psi); $out = $p.StandardOutput.ReadToEnd(); [void]$p.StandardError.ReadToEnd(); $p.WaitForExit()
	[pscustomobject]@{ Code = $p.ExitCode; Out = $out }
}
$cd = Join-Path $root "child"; New-Item -ItemType Directory -Force -Path (Join-Path $cd "Tools") | Out-Null
$fakeBuild = Join-Path $cd "fake-build.bat"
$childScript = Join-Path $cd "Tools\BuildCpp.ps1"
function Make-Child([int]$BuildExit) {
	Set-Content -LiteralPath $fakeBuild -Value "@echo off`r`nexit /b $BuildExit" -Encoding ASCII
	(Get-Content $Script -Raw).Replace('"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat"', '"' + $fakeBuild + '"') | Set-Content -LiteralPath $childScript -Encoding UTF8
}
$envBase = @{ LOCALAPPDATA = (Join-Path $root "LocalAppData") }
Make-Child 0
$noCfg = Join-Path $root "absent.json"
$r = Run-Child $childScript @() ($envBase + @{ CW_SIGN_CONFIG = $noCfg }); Check ($r.Code -eq 0 -and $r.Out -match "signing mode: Off" -and $r.Out -match "WARNING: signing is OFF") "no config: exit 0, says signing is OFF, warns that the DLL is unsigned"
Make-Child 7
$r = Run-Child $childScript @() ($envBase + @{ CW_SIGN_CONFIG = $noCfg }); Check ($r.Code -eq 7) "fake build exits 7 -> the script exits 7 (real process exit code)"
Make-Child 0
$r = Run-Child $childScript @("-VerifyOnly") ($envBase + @{ CW_SIGN_CONFIG = $noCfg }); Check ($r.Code -eq 20) "-VerifyOnly without config -> exit 20"
$bad = Join-Path $root "bad.json"; Set-Content $bad "{ nope"
$r = Run-Child $childScript @("-PreflightOnly") ($envBase + @{ CW_SIGN_CONFIG = $bad }); Check ($r.Code -eq 20) "broken config -> exit 20, not silently Off"
$off = Join-Path $root "off.json"; Set-Content $off '{ "Mode": "Off" }'
$r = Run-Child $childScript @("-PreflightOnly") ($envBase + @{ CW_SIGN_CONFIG = $off }); Check ($r.Code -eq 0) "Mode Off + preflight -> exit 0"
$req = Join-Path $root "req.json"; Set-Content $req ($good.Replace('"DlibPath":"x"', '"DlibPath":"C:\\nope\\dlib.dll","SigntoolPath":"C:\\nope\\signtool.exe"'))
$r = Run-Child $childScript @("-PreflightOnly") ($envBase + @{ CW_SIGN_CONFIG = $req }); Check ($r.Code -eq 21) "Required with missing tools -> exit 21 before anything else happens"
$r = Run-Child $childScript @() ($envBase + @{ CW_SIGN_CONFIG = $req }); Check ($r.Code -eq 21) "Required with missing tools -> exit 21 even for a plain build invocation (checked before building)"

Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host ("RESULT: {0} passed, {1} failed" -f $script:Pass, $script:FailCount)
exit $(if ($script:FailCount -eq 0) { 0 } else { 1 })
