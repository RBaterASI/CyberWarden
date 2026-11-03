# Runs one Python script headlessly with UnrealEditor-Cmd and returns the real process exit code.
#   powershell -File Tools\RunHeadless.ps1 -Script Tools\ValidateSchedule.py [-Log <abs log path>] [-Env NAME=VALUE ...]
# Notes: the script path is passed with forward slashes (a backslash followed by r, as in C:\Users\ricky, is read as an
# escape sequence by the Python executor and the script silently fails to load). Run Tools\BuildCpp.ps1 first: a stale module
# fails the run. The launcher exists because Git Bash reported exit 139 after a clean engine shutdown in roughly 1 of 12 runs
# (see Docs/NPC/M2_2_Checkpoint_A.md).
param(
	[Parameter(Mandatory = $true)][string]$Script,
	[string]$Log = "",
	[string[]]$Env = @(),
	[string]$ExtraArgs = ""
)
$project = Split-Path $PSScriptRoot -Parent
$scriptPath = if ([System.IO.Path]::IsPathRooted($Script)) { $Script } else { Join-Path $project $Script }
$scriptPath = $scriptPath.Replace("\", "/")
if (-not $Log) { $Log = Join-Path $env:TEMP ("ue_" + [System.IO.Path]::GetFileNameWithoutExtension($Script) + ".log") }
foreach ($e in $Env) { $k, $v = $e.Split("=", 2); [Environment]::SetEnvironmentVariable($k, $v, "Process") }
$ueArgs = @("`"$project\CyberWarden.uproject`"", "-ExecutePythonScript=`"$scriptPath`"", "-unattended", "-nop4", "-nosplash", "-NullRHI", "-stdout", "-abslog=`"$Log`"")
if ($ExtraArgs) { $ueArgs += $ExtraArgs }
$p = Start-Process -FilePath "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" -ArgumentList $ueArgs -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput ($Log + ".stdout")
Write-Output ("exit " + $p.ExitCode + "  log: " + $Log)
exit $p.ExitCode
