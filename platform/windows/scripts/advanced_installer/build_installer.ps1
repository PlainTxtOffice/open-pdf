#requires -Version 7.3
[CmdletBinding()]
param(
    [string]$ProjectRoot = '../..',
    [string]$SourceDirectory = 'build/standalone/main.dist',
    [string]$PackagingDirectory = 'dev-docs/packaging/advanced_installer',
    [string]$OutputDirectory = 'build/installer',
    [string]$AdvancedInstaller = $env:ADVINST_COM
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Installer input validation.
function Read-InstallerMetadata {
    param([string]$Root)
    $python = Join-Path $Root '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "Missing build interpreter: $python"
    }
    $code = @'
import json, sys, tomllib
from pathlib import Path
config = tomllib.loads(Path(sys.argv[1]).read_text("utf-8"))
project = config["project"]
packaging = config["tool"]["open-pdf"]["packaging"]
print(json.dumps(dict(slug=project["name"], version=project["version"],
                     title=packaging["title"], company=packaging["company-name"])))
'@
    $raw = & $python -X utf8 -c $code (Join-Path $Root 'pyproject.toml')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read packaging metadata from pyproject.toml.' }
    $metadata = $raw | ConvertFrom-Json
    if ($metadata.version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
        throw 'Installer version must have exactly three numeric release fields.'
    }
    $parts = $metadata.version.Split('.') | ForEach-Object { [decimal]$_ }
    if ($parts[0] -gt 255 -or $parts[1] -gt 255 -or $parts[2] -gt 65535) {
        throw 'Installer version exceeds MSI limits: 255.255.65535.'
    }
    if ($metadata.slug -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$' -or
        [string]::IsNullOrWhiteSpace($metadata.title) -or
        [string]::IsNullOrWhiteSpace($metadata.company) -or
        $metadata.title.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) {
        throw 'Invalid project name, packaging title, or company-name.'
    }
    return $metadata
}

function Get-PayloadArchitecture {
    param([string]$Executable)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Missing release executable: $Executable. Run scripts/nuitka/standalone.ps1 first."
    }
    $reader = [IO.BinaryReader]::new([IO.File]::OpenRead($Executable))
    try {
        if ($reader.BaseStream.Length -lt 64 -or $reader.ReadUInt16() -ne 0x5A4D) {
            throw 'Invalid executable DOS header.'
        }
        $reader.BaseStream.Position = 0x3C
        $offset = $reader.ReadUInt32()
        if ($offset -lt 64 -or $offset + 94 -gt $reader.BaseStream.Length) {
            throw 'Invalid executable PE header bounds.'
        }
        $reader.BaseStream.Position = $offset
        if ($reader.ReadUInt32() -ne 0x4550) { throw 'Invalid executable PE signature.' }
        $machine = $reader.ReadUInt16()
        $reader.BaseStream.Position = $offset + 24
        if ($reader.ReadUInt16() -notin @(0x10B, 0x20B)) { throw 'Invalid PE optional header.' }
        $reader.BaseStream.Position = $offset + 92
        if ($reader.ReadUInt16() -ne 2) { throw 'Payload must be the GUI release, not the console debug build.' }
        switch ($machine) {
            0x8664 { return 'x64' }
            0x014C { return 'x86' }
            default { throw ('Unsupported executable architecture: 0x{0:X4}.' -f $machine) }
        }
    }
    finally { $reader.Dispose() }
}

function Assert-PayloadVersion {
    param([string]$Executable, [string]$Version)
    $info = [Diagnostics.FileVersionInfo]::GetVersionInfo($Executable)
    $actual = '{0}.{1}.{2}' -f $info.ProductMajorPart, $info.ProductMinorPart, $info.ProductBuildPart
    if ([version]$actual -ne [version]$Version -or $info.ProductPrivatePart -ne 0) {
        throw "Payload version $actual does not match $Version. Recompile with standalone.ps1."
    }
}

# Persistent installer project validation.
function Get-AipRows {
    param([xml]$Xml, [string]$Component)
    return $Xml.SelectNodes("/DOCUMENT/COMPONENT[@cid='caphyon.advinst.msicomp.$Component']/ROW")
}

function Save-InstallerProject {
    param([xml]$Xml, [string]$Path)
    $settings = [Xml.XmlWriterSettings]::new()
    $settings.Encoding = [Text.UTF8Encoding]::new($false)
    $settings.Indent = $true
    $settings.NewLineChars = "`n"
    $settings.NewLineHandling = [Xml.NewLineHandling]::Replace
    $writer = [Xml.XmlWriter]::Create($Path, $settings)
    try { $Xml.Save($writer) } finally { $writer.Dispose() }
}

function Initialize-AipPolicy {
    param([string]$Path)
    [xml]$xml = Get-Content -LiteralPath $Path -Raw
    # AI's new-project template enables backups. This workflow uses version control.
    $backup = $xml.SelectSingleNode('//ROW[@Name="BackUpAipBeforeSave"]')
    if ($null -ne $backup) { $backup.ParentNode.RemoveChild($backup) | Out-Null }
    Save-InstallerProject $xml $Path
}

function Assert-InstallerProject {
    param([string]$Path, $Metadata, [string]$Architecture, [string]$Source)
    [xml]$xml = Get-Content -LiteralPath $Path -Raw
    $props = @{}
    foreach ($row in (Get-AipRows $xml 'MsiPropsComponent')) {
        $props[$row.GetAttribute('Property')] = $row.GetAttribute('Value')
    }
    if ($props.ProductName -ne $Metadata.title -or $props.Manufacturer -ne $Metadata.company -or
        $props.ALLUSERS -ne '1' -or -not $props.UpgradeCode) {
        throw 'AIP product identity or per-machine scope does not match the project.'
    }
    if ($props['AI_UPGRADE'] -eq 'No') { throw 'AIP must enable major upgrades.' }
    $builds = @(Get-AipRows $xml 'BuildComponent' | Where-Object { $_.BuildName -eq 'DefaultBuild' })
    if ($builds.Count -ne 1) { throw 'AIP must contain DefaultBuild.' }
    $build = $builds[0]
    $actualArch = $build.GetAttribute('MsiPackageType')
    if (-not $actualArch) { $actualArch = 'x86' }
    if ($actualArch -ne $Architecture) { throw "AIP architecture $actualArch does not match payload $Architecture." }
    if ($build.GetAttribute('PackageType') -ne '1' -or $build.GetAttribute('FilesInsideExe') -ne 'true') {
        throw 'AIP output must be ExeInside.'
    }
    $prefix = if ($Architecture -eq 'x64') { '[ProgramFiles64Folder]' } else { '[ProgramFilesFolder]' }
    foreach ($entry in @(@('SET_APPDIR', ($prefix + '[Manufacturer]\[ProductName]')),
                         @('SET_SHORTCUTDIR', '[ProgramMenuFolder][ProductName]'))) {
        $action = $xml.SelectSingleNode("//ROW[@Action='$($entry[0])' and @Target]")
        if ($null -eq $action) { throw "Missing AIP action $($entry[0])." }
        $target = $action.GetAttribute('Target')
        foreach ($value in $action.GetAttribute('MultiBuildTarget').Split(';')) {
            if ($value.StartsWith('DefaultBuild:')) { $target = $value.Substring(13) }
        }
        if ($target -ne $entry[1]) { throw "Unexpected AIP folder: $target" }
    }
    $syncs = @(Get-AipRows $xml 'SynchronizedFolderComponent')
    if ($syncs.Count -ne 1 -or $syncs[0].Directory_ -ne 'APPDIR') { throw 'Expected one APPDIR synchronization mapping.' }
    $mapped = [IO.Path]::GetFullPath($syncs[0].SourcePath, (Split-Path $Path))
    if ($mapped.TrimEnd('\') -ne $Source.TrimEnd('\')) {
        throw "AIP source mismatch: $mapped. Update the synchronization mapping deliberately in Advanced Installer."
    }
    $remove = $xml.SelectSingleNode('//COMPONENT[@cid="caphyon.advinst.msicomp.MsiInstExSeqComponent"]/ROW[@Action="RemoveExistingProducts"]')
    if ($null -eq $remove) {
        # Advanced Installer omits default actions from saved AIPs. Read the
        # installed version's sequence fragment instead of assuming its default.
        $installRoot = Split-Path (Split-Path (Split-Path $AdvancedInstaller))
        [xml]$defaults = Get-Content -LiteralPath (Join-Path $installRoot 'fragments/Sequences.aip') -Raw
        $remove = $defaults.SelectSingleNode('//COMPONENT[@cid="caphyon.advinst.msicomp.MsiInstExSeqComponent"]/ROW[@Action="RemoveExistingProducts"]')
    }
    if ($null -eq $remove -or $remove.GetAttribute('Sequence') -ne '1450') {
        throw 'AIP must remove the previous product before installation (sequence 1450).'
    }
    $upgrades = @(Get-AipRows $xml 'MsiUpgradeComponent' | Where-Object { $_.ActionProperty -eq 'OLDPRODUCTS' })
    if ($upgrades.Count -ne 1 -or $upgrades[0].UpgradeCode -ne '[|UpgradeCode]') { throw 'Missing major-upgrade detection.' }
    $file = @(Get-AipRows $xml 'MsiFilesComponent' | Where-Object { $_.FileName.Split('|')[-1] -eq "$($Metadata.title).exe" })
    if ($file.Count -ne 1) { throw 'AIP must contain exactly one application executable.' }
    $component = $xml.SelectSingleNode("//ROW[@Component='$($file[0].Component_)' and @Directory_]")
    if ($null -eq $component -or $component.Directory_ -ne 'APPDIR') { throw 'Executable must be directly in APPDIR.' }
    $shortcuts = @(Get-AipRows $xml 'MsiShortsComponent' | Where-Object {
        $_.Target -eq "[#$($file[0].File)]" -and $_.Directory_ -eq 'SHORTCUTDIR' -and $_.WkDir -eq 'APPDIR'
    })
    if ($shortcuts.Count -ne 1) { throw 'Missing or duplicated application Start menu shortcut.' }
    Assert-AipFiles $xml $Path $Source
}

function Assert-AipFiles {
    param([xml]$Xml, [string]$Path, [string]$Source, [switch]$Complete)
    $sources = @{}
    $destinations = @{}
    foreach ($file in (Get-AipRows $Xml 'MsiFilesComponent')) {
        $sourcePath = [IO.Path]::GetFullPath($file.SourcePath, (Split-Path $Path))
        $component = $Xml.SelectSingleNode("//ROW[@Component='$($file.Component_)' and @Directory_]")
        $directory = $component.Directory_
        $destination = $file.FileName.Split('|')[-1]
        $visited = @{}
        while ($directory -ne 'TARGETDIR') {
            if ($visited.ContainsKey($directory)) { throw 'Cycle in AIP directories.' }
            $visited[$directory] = $true
            $row = $Xml.SelectSingleNode("//ROW[@Directory='$directory' and @Directory_Parent]")
            if ($null -eq $row) { throw "Missing AIP directory $directory." }
            $name = if ($directory -eq 'APPDIR') { 'APPDIR' } else { $row.DefaultDir.Split(':')[0].Split('|')[-1] }
            $destination = "$name\$destination"
            $directory = $row.Directory_Parent
        }
        if ($sources.ContainsKey($sourcePath) -or $destinations.ContainsKey($destination)) {
            throw "Duplicate AIP payload source or destination: $sourcePath -> $destination"
        }
        $sources[$sourcePath] = $destination
        $destinations[$destination] = $true
    }
    if ($Complete) {
        foreach ($file in (Get-ChildItem -LiteralPath $Source -File -Recurse -Force)) {
            $expected = 'APPDIR\' + [IO.Path]::GetRelativePath($Source, $file.FullName)
            if ($sources[$file.FullName] -ne $expected) { throw "Payload is not synchronized correctly: $expected" }
        }
        foreach ($path in $sources.Keys) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Stale AIP file: $path" }
        }
    }
}


function Invoke-InstallerCli {
    param([string[]]$CliArguments)
    & $AdvancedInstaller @CliArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Advanced Installer failed with exit code $LASTEXITCODE ($($CliArguments[0]))."
    }
}

$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot, $PSScriptRoot)
$SourceDirectory = [IO.Path]::GetFullPath($SourceDirectory, $ProjectRoot).TrimEnd('\')
$PackagingDirectory = [IO.Path]::GetFullPath($PackagingDirectory, $ProjectRoot)
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory, $ProjectRoot)
$AdvancedInstaller = ([string]$AdvancedInstaller).Trim().Trim('"')
if (-not $AdvancedInstaller) { throw 'Set ADVINST_COM or pass -AdvancedInstaller with the installed AdvancedInstaller.com path.' }
$AdvancedInstaller = [IO.Path]::GetFullPath($AdvancedInstaller, $ProjectRoot)
if ([IO.Path]::GetFileName($AdvancedInstaller) -ne 'AdvancedInstaller.com' -or
    -not (Test-Path -LiteralPath $AdvancedInstaller -PathType Leaf)) {
    throw "Advanced Installer CLI not found: $AdvancedInstaller"
}
$metadata = Read-InstallerMetadata $ProjectRoot
$executableName = "$($metadata.title).exe"
$executable = Join-Path $SourceDirectory $executableName
$architecture = Get-PayloadArchitecture $executable
Assert-PayloadVersion $executable $metadata.version
foreach ($required in @('python3.dll', 'PySide6/QtWidgets.pyd')) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourceDirectory $required) -PathType Leaf)) {
        throw "Missing standalone dependency $required. Supply the complete release .dist folder, not a onefile executable."
    }
}
foreach ($destination in @($PackagingDirectory, $OutputDirectory)) {
    if ($destination -eq $SourceDirectory -or $destination.StartsWith($SourceDirectory + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Packaging and output directories must be outside the payload.'
    }
}
& (Join-Path $ProjectRoot 'scripts/nuitka/validate_release.ps1') -DistPath $SourceDirectory
if ($LASTEXITCODE -ne 0) { throw 'Release payload validation failed.' }
$projectFile = Join-Path $PackagingDirectory "$($metadata.slug).aip"
$buildName = 'DefaultBuild'
if (-not (Test-Path -LiteralPath $projectFile)) {
    [IO.Directory]::CreateDirectory($PackagingDirectory) | Out-Null
    $initialProject = Join-Path $PackagingDirectory ('.initial-' + [guid]::NewGuid() + '.aip')
    Invoke-InstallerCli @('/newproject', $initialProject, '-type', 'professional', '-lang', 'en')
    Initialize-AipPolicy $initialProject
    $programFiles = if ($architecture -eq 'x64') { '[ProgramFiles64Folder]' } else { '[ProgramFilesFolder]' }
    $commands = @(
        @('/SetProperty', "ProductName=$($metadata.title)"),
        @('/SetProperty', "Manufacturer=$($metadata.company)"),
        @('/SetProperty', 'ALLUSERS=1'),
        @('/SetPackageType', $architecture, '-buildname', $buildName),
        @('/SetAppdir', '-buildname', $buildName, '-path', ($programFiles + '[Manufacturer]\[ProductName]')),
        @('/SetShortcutdir', '-buildname', $buildName, '-path', '[ProgramMenuFolder][ProductName]'),
        @('/NewSync', 'APPDIR', $SourceDirectory, '-existingfiles', 'keep'),
        @('/RefreshSync', 'APPDIR'),
        @('/NewShortcut', '-name', $metadata.title, '-dir', 'SHORTCUTDIR', '-target', "APPDIR\$executableName", '-wkdir', 'APPDIR'),
        @('/SetOutputType', 'ExeInside', '-buildname', $buildName)
    )
    foreach ($command in $commands) { Invoke-InstallerCli (@('/edit', $initialProject) + $command) }
    Assert-InstallerProject $initialProject $metadata $architecture $SourceDirectory
    [IO.File]::Move($initialProject, $projectFile)
}
Assert-InstallerProject $projectFile $metadata $architecture $SourceDirectory
Invoke-InstallerCli @('/edit', $projectFile, '/RefreshSync', 'APPDIR')
[xml]$project = Get-Content -LiteralPath $projectFile -Raw
Assert-AipFiles $project $projectFile $SourceDirectory -Complete
$packageName = "$($metadata.slug)-$($metadata.version)-$architecture-setup.exe"
Invoke-InstallerCli @('/edit', $projectFile, '/SetVersion', $metadata.version)
Invoke-InstallerCli @('/edit', $projectFile, '/SetPackageName', $packageName, '-buildname', $buildName)
Invoke-InstallerCli @('/edit', $projectFile, '/SetOutputLocation', '-buildname', $buildName, '-path', $OutputDirectory)
$artifact = Join-Path $OutputDirectory $packageName
$previousWrite = if (Test-Path -LiteralPath $artifact) { (Get-Item -LiteralPath $artifact).LastWriteTimeUtc } else { $null }
$started = [DateTime]::UtcNow
Invoke-InstallerCli @('/rebuild', $projectFile, '-buildslist', $buildName)
if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) { throw "Installer was not produced: $artifact" }
$result = Get-Item -LiteralPath $artifact
if ($result.Length -eq 0 -or $result.LastWriteTimeUtc -lt $started -or $result.LastWriteTimeUtc -eq $previousWrite) {
    throw "Installer was not refreshed by this build: $artifact"
}
[xml]$project = Get-Content -LiteralPath $projectFile -Raw
Save-InstallerProject $project $projectFile
Write-Host "AIP: $projectFile"
Write-Host "Installer: $artifact"
Write-Host "Signature: $((Get-AuthenticodeSignature -LiteralPath $artifact).Status)"
