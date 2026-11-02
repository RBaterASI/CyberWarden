# Serial, interleaved A/B experiment for the headless shutdown crash. Never runs two Unreal processes at once.
#   powershell -File Tools\ExitStress.ps1 -PairsPerArm 20
# Arm A = module built with the native automation tests, arm B = built with CW_NO_TESTS=1 (tests compiled out).
# Expects Saved\ExitStress\A.dll and B.dll (copies of Binaries\Win64\UnrealEditor-CyberWarden.dll from the two builds).
# For every run it records: arm, DLL hash actually installed, module classes present, workload completion marker, whether
# the engine logged a normal shutdown, the real process exit code (never masked) and the crash signature.
param([int]$PairsPerArm = 20)
$project = Split-Path $PSScriptRoot -Parent
$work = Join-Path $project "Saved\ExitStress"
$dll = Join-Path $project "Binaries\Win64\UnrealEditor-CyberWarden.dll"
$csv = Join-Path $work "results.csv"
if (-not (Test-Path $csv)) { "run,arm,dllSha8,moduleOk,workloadDone,shutdownLogged,exitCode,signature,seconds" | Set-Content $csv }
$ue = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$script = ($project + "\Tools\ExitProbe.py").Replace("\", "/")
$order = @(); 1..$PairsPerArm | ForEach-Object { $order += "A"; $order += "B" }
$n = (Get-Content $csv | Measure-Object).Count - 1
foreach ($arm in $order) {
	$n++
	Copy-Item (Join-Path $work "$arm.dll") $dll -Force
	$sha = (Get-FileHash $dll -Algorithm SHA256).Hash.Substring(0, 8)
	$log = Join-Path $work "run_$n.log"
	$t0 = Get-Date
	$p = Start-Process -FilePath $ue -ArgumentList @("`"$project\CyberWarden.uproject`"", "-ExecutePythonScript=`"$script`"", "-unattended", "-nop4", "-nosplash", "-NullRHI", "-stdout", "-abslog=`"$log`"") -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput "$log.stdout"
	$sec = [int]((Get-Date) - $t0).TotalSeconds
	$txt = if (Test-Path $log) { Get-Content $log -Raw } else { "" }
	$moduleOk = $txt -match "\[EXITPROBE\] module=ok"
	$done = $txt -match "\[SCHEDCHK\] RESULT: PASS"
	$shut = $txt -match "Log file closed"
	$code = $p.ExitCode
	$sig = if ($code -eq 0) { "clean" } elseif ($code -eq -1073741819) { "ACCESS_VIOLATION_0xC0000005" } else { "exit_$code" }
	"$n,$arm,$sha,$moduleOk,$done,$shut,$code,$sig,$sec" | Add-Content $csv
}
Write-Output "ExitStress finished: see $csv"
