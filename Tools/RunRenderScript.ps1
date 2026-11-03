# Like RunHeadless.ps1 but WITH the GPU (no -NullRHI) and rendering allowed in commandlet mode, for scripts that capture images.
#   powershell -File Tools\RunRenderScript.ps1 -Script Tools\C0_RenderPreview.py [-Log <abs log path>]
param(
	[Parameter(Mandatory = $true)][string]$Script,
	[string]$Log = ""
)
$project = Split-Path $PSScriptRoot -Parent
$scriptPath = if ([System.IO.Path]::IsPathRooted($Script)) { $Script } else { Join-Path $project $Script }
$scriptPath = $scriptPath.Replace("\", "/")
if (-not $Log) { $Log = Join-Path $env:TEMP ("ue_" + [System.IO.Path]::GetFileNameWithoutExtension($Script) + ".log") }
$ueArgs = @("`"$project\CyberWarden.uproject`"", "-ExecutePythonScript=`"$scriptPath`"", "-unattended", "-nop4", "-nosplash", "-AllowCommandletRendering", "-RenderOffScreen", "-stdout", "-abslog=`"$Log`"")
$p = Start-Process -FilePath "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" -ArgumentList $ueArgs -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput ($Log + ".stdout")
Write-Output ("exit " + $p.ExitCode + "  log: " + $Log)
exit $p.ExitCode
