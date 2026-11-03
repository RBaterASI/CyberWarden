# Builds the CyberWarden editor target. Run before any headless UnrealEditor-Cmd script (a stale module makes those fail).
#   powershell -File Tools\BuildCpp.ps1            (Development Editor build)
# Requires: Visual Studio 2022 Build Tools (MSVC 14.44 >= 35211) + Windows SDK 22621 + .NET Framework 4.8 SDK.
param([string]$Configuration = "Development")
$project = Join-Path (Split-Path $PSScriptRoot -Parent) "CyberWarden.uproject"
& "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" CyberWardenEditor Win64 $Configuration "-project=$project" -WaitMutex -NoHotReload
exit $LASTEXITCODE
