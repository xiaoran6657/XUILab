[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ArtifactRoot,
    [Parameter(Mandatory = $true)][string]$MainStamp,
    [Parameter(Mandatory = $true)][string]$OverheadStamp,
    [Parameter(Mandatory = $true)][string]$CandidateId,
    [Parameter(Mandatory = $true)][string]$BuildId,
    [Parameter(Mandatory = $true)][string]$SourceRevision
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$sourceRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path
$verifier = Join-Path $PSScriptRoot 'Get-XUILabM0CalibrationSummary.ps1'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('XUILab-M0-04-verifier-' + [Guid]::NewGuid().ToString('N'))
$expectedRunNames = [Collections.Generic.List[string]]::new()
foreach ($index in 1..5) {
    $expectedRunNames.Add("m0-04-cal-main-idle-r$index-$MainStamp")
    $expectedRunNames.Add("m0-04-cal-main-load4m-r$index-$MainStamp")
    $expectedRunNames.Add("m0-04-cal-overhead-on-r$index-$OverheadStamp")
    $expectedRunNames.Add("m0-04-cal-overhead-off-r$index-$OverheadStamp")
}

function Write-JsonNoBom {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)]$Value)
    $json = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Update-ConfigHash {
    param([Parameter(Mandatory = $true)][string]$RunDirectory)
    $configPath = Join-Path $RunDirectory 'config.json'
    $identityPath = Join-Path $RunDirectory 'identity.json'
    $identity = Get-Content -Raw -LiteralPath $identityPath | ConvertFrom-Json
    $identity.configSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash
    Write-JsonNoBom -Path $identityPath -Value $identity
}

function New-EvidenceCopy {
    param([Parameter(Mandatory = $true)][string]$Name)
    $destination = Join-Path $temporaryRoot $Name
    [void](New-Item -ItemType Directory -Path $destination)
    foreach ($runName in $expectedRunNames) {
        $source = Join-Path $sourceRoot $runName
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "Missing source evidence directory: $source"
        }
        Copy-Item -LiteralPath $source -Destination $destination -Recurse
        $runDirectory = Join-Path $destination $runName
        $configPath = Join-Path $runDirectory 'config.json'
        $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
        $config.outputDirectory = $destination
        Write-JsonNoBom -Path $configPath -Value $config
        Update-ConfigHash -RunDirectory $runDirectory
    }
    return $destination
}

function Invoke-Verifier {
    param([Parameter(Mandatory = $true)][string]$EvidenceRoot)
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verifier `
        -ArtifactRoot $EvidenceRoot -MainStamp $MainStamp -OverheadStamp $OverheadStamp `
        -CandidateId $CandidateId -BuildId $BuildId -SourceRevision $SourceRevision 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $savedErrorActionPreference
    [pscustomobject]@{ ExitCode = $exitCode; Output = ($output -join [Environment]::NewLine) }
}

function Assert-Rejected {
    param([Parameter(Mandatory = $true)][string]$Name, [Parameter(Mandatory = $true)][scriptblock]$Mutation)
    $evidenceRoot = New-EvidenceCopy -Name $Name
    & $Mutation $evidenceRoot
    $result = Invoke-Verifier -EvidenceRoot $evidenceRoot
    if ($result.ExitCode -eq 0) {
        throw "Negative verifier scenario '$Name' was incorrectly accepted."
    }
    Write-Host "PASS rejected=$Name"
}

try {
    [void](New-Item -ItemType Directory -Path $temporaryRoot)

    $validRoot = New-EvidenceCopy -Name 'valid'
    $valid = Invoke-Verifier -EvidenceRoot $validRoot
    if ($valid.ExitCode -ne 0) {
        throw "Untampered evidence copy was rejected:`n$($valid.Output)"
    }
    Write-Host 'PASS accepted=untampered-copy'

    Assert-Rejected -Name 'csv-corruption' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $csvPath = Join-Path $run 'samples.csv'
        $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $csvPath)
        $columns = $lines[1].Split(',')
        $columns[3] = '999.0'
        $lines[1] = $columns -join ','
        [IO.File]::WriteAllLines($csvPath, $lines, [Text.UTF8Encoding]::new($false))
    }

    Assert-Rejected -Name 'config-mismatch' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $configPath = Join-Path $run 'config.json'
        $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
        $config.warmupFrames = 299
        Write-JsonNoBom -Path $configPath -Value $config
        Update-ConfigHash -RunDirectory $run
    }

    Assert-Rejected -Name 'summary-corruption' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-load4m-r1-$MainStamp"
        $summaryPath = Join-Path $run 'summary.json'
        $summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
        $summary.p95FrameIntervalMs = 0
        Write-JsonNoBom -Path $summaryPath -Value $summary
    }

    Assert-Rejected -Name 'summary-nan-string-type' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $summaryPath = Join-Path $run 'summary.json'
        $summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
        $summary.p50FrameIntervalMs = 'NaN'
        Write-JsonNoBom -Path $summaryPath -Value $summary
    }

    Assert-Rejected -Name 'summary-boolean-string-type' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $summaryPath = Join-Path $run 'summary.json'
        $summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
        $summary.processSuccess = 'false'
        Write-JsonNoBom -Path $summaryPath -Value $summary
    }

    Assert-Rejected -Name 'summary-property-name-case' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $summaryPath = Join-Path $run 'summary.json'
        $json = [IO.File]::ReadAllText($summaryPath)
        $mutated = $json.Replace('"p99FrameIntervalMs":', '"P99FrameIntervalMs":')
        if ($mutated -ceq $json) {
            throw 'Could not mutate summary property-name case.'
        }
        [IO.File]::WriteAllText($summaryPath, $mutated, [Text.UTF8Encoding]::new($false))
    }

    Assert-Rejected -Name 'config-integer-string-type' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $configPath = Join-Path $run 'config.json'
        $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
        $config.warmupFrames = '300'
        Write-JsonNoBom -Path $configPath -Value $config
        Update-ConfigHash -RunDirectory $run
    }

    Assert-Rejected -Name 'identity-hash-mismatch' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $identityPath = Join-Path $run 'identity.json'
        $identity = Get-Content -Raw -LiteralPath $identityPath | ConvertFrom-Json
        $identity.configSha256 = '0000000000000000000000000000000000000000000000000000000000000000'
        Write-JsonNoBom -Path $identityPath -Value $identity
    }

    Assert-Rejected -Name 'duplicate-run-index' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r2-$MainStamp"
        $configPath = Join-Path $run 'config.json'
        $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
        $config.runIndex = 1
        Write-JsonNoBom -Path $configPath -Value $config
        Update-ConfigHash -RunDirectory $run
    }

    Assert-Rejected -Name 'environment-mismatch' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-overhead-on-r1-$OverheadStamp"
        $environmentPath = Join-Path $run 'environment.json'
        $environment = Get-Content -Raw -LiteralPath $environmentPath | ConvertFrom-Json
        $environment.screenWidth = 959
        Write-JsonNoBom -Path $environmentPath -Value $environment
    }

    Assert-Rejected -Name 'optional-capability-status-reason-mismatch' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-main-idle-r1-$MainStamp"
        $environmentPath = Join-Path $run 'environment.json'
        $environment = Get-Content -Raw -LiteralPath $environmentPath | ConvertFrom-Json
        $environment.metricCapabilities[1].status = 'available'
        $environment.metricCapabilities[1].reason = ''
        Write-JsonNoBom -Path $environmentPath -Value $environment
    }

    Assert-Rejected -Name 'extra-artifact' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-overhead-off-r1-$OverheadStamp"
        [IO.File]::WriteAllText((Join-Path $run 'unexpected.txt'), 'tamper', [Text.UTF8Encoding]::new($false))
    }

    Assert-Rejected -Name 'hidden-extra-artifact' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-overhead-off-r1-$OverheadStamp"
        $hiddenPath = Join-Path $run 'hidden-tamper.txt'
        [IO.File]::WriteAllText($hiddenPath, 'tamper', [Text.UTF8Encoding]::new($false))
        [IO.File]::SetAttributes($hiddenPath, [IO.FileAttributes]::Hidden)
    }

    Assert-Rejected -Name 'missing-run-index' -Mutation {
        param($root)
        $run = Join-Path $root "m0-04-cal-overhead-off-r5-$OverheadStamp"
        Remove-Item -LiteralPath $run -Recurse -Force
    }

    Write-Host 'COMPLETE verifier negative scenarios=14 valid=1'
}
finally {
    $resolvedTemporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase) -and
        $resolvedTemporaryRoot -ne $resolvedSystemTemp -and
        (Test-Path -LiteralPath $resolvedTemporaryRoot)) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}
