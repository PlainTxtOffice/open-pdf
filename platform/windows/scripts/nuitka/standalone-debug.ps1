#requires -Version 7.3
# Launch the standalone build with console output and no anti-debugger/signing.
[CmdletBinding()]
param(
    [string]$PythonExecutable = '.venv/Scripts/python.exe',
    [string]$OutputDirectory,
    [string]$OutputFilename,
    [switch]$UseCurrentDefaultPaths,
    [switch]$ResetRuntimeDefaults,
    [ValidateSet('msvc', 'clang', 'mingw64')]
    [string]$Compiler = 'clang',
    [string]$MsvcVersion = 'latest',
    [ValidateRange(1, 64)]
    [int]$Jobs = 4,
    [ValidateSet('yes', 'no', 'auto')]
    [string]$Lto = 'no',
    [switch]$LowMemory,
    [switch]$ShowBackendCommands
)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'standalone.ps1') @PSBoundParameters -Console
