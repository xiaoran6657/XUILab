[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$invokeScript = Join-Path $PSScriptRoot 'Invoke-XUILabM0Calibration.ps1'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('XUILab-M0-04-orchestration-' + [Guid]::NewGuid().ToString('N'))
$temporaryRootCreated = $false

function New-ValidSummary {
    param([Parameter(Mandatory = $true)][string]$RunId)

    return [ordered]@{
        schemaVersion = 'xuilab.benchmark.summary/v1'
        runId = $RunId
        state = 'completed'
        failureCode = 'none'
        failureReason = ''
        correctness = 'pass'
        measurementValidity = 'valid'
        performanceComparison = 'not_assessed'
        processSuccess = $true
        exitCode = 0
        enteredMeasure = $true
        exportSucceeded = $true
        cleanupSucceeded = $true
        sampleCount = 1800
        p50FrameIntervalMs = 16.6
        p95FrameIntervalMs = 17.0
        p99FrameIntervalMs = 17.2
        maxFrameIntervalMs = 18.0
        overBudgetRatio = 0.1
        meanMainThreadNanoseconds = $null
        totalGcAllocatedBytes = $null
        lastSystemUsedMemoryBytes = $null
    }
}

function New-FakePlayerSource {
    param([Parameter(Mandatory = $true)][string]$SummaryJson)

    return @"
@echo off
setlocal
set "outputRoot="
set "runId="
:parse
if "%~1"=="" goto write
if /I "%~1"=="--xuilab-output-root" (
  set "outputRoot=%~2"
  shift
  shift
  goto parse
)
if /I "%~1"=="--xuilab-run-id" (
  set "runId=%~2"
  shift
  shift
  goto parse
)
shift
goto parse
:write
if not defined outputRoot exit /b 91
if not defined runId exit /b 92
mkdir "%outputRoot%\%runId%" >nul 2>nul
> "%outputRoot%\%runId%\summary.json" echo $SummaryJson
exit /b 0
"@
}

$scenarios = @(
    [pscustomobject]@{ Name = 'missing-state'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'state'; Mutate = { param($summary) $summary.Remove('state') } },
    [pscustomobject]@{ Name = 'missing-failure-code'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'failureCode'; Mutate = { param($summary) $summary.Remove('failureCode') } },
    [pscustomobject]@{ Name = 'missing-failure-reason'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'failureReason'; Mutate = { param($summary) $summary.Remove('failureReason') } },
    [pscustomobject]@{ Name = 'missing-performance-comparison'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'performanceComparison'; Mutate = { param($summary) $summary.Remove('performanceComparison') } },
    [pscustomobject]@{ Name = 'missing-p99'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'p99FrameIntervalMs'; Mutate = { param($summary) $summary.Remove('p99FrameIntervalMs') } },
    [pscustomobject]@{ Name = 'missing-over-budget'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'overBudgetRatio'; Mutate = { param($summary) $summary.Remove('overBudgetRatio') } },
    [pscustomobject]@{ Name = 'missing-main-thread'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'meanMainThreadNanoseconds'; Mutate = { param($summary) $summary.Remove('meanMainThreadNanoseconds') } },
    [pscustomobject]@{ Name = 'missing-total-gc'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'totalGcAllocatedBytes'; Mutate = { param($summary) $summary.Remove('totalGcAllocatedBytes') } },
    [pscustomobject]@{ Name = 'missing-system-memory'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'lastSystemUsedMemoryBytes'; Mutate = { param($summary) $summary.Remove('lastSystemUsedMemoryBytes') } },
    [pscustomobject]@{ Name = 'extra-summary-property'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'unexpectedField'; Mutate = { param($summary) $summary['unexpectedField'] = $true } },
    [pscustomobject]@{ Name = 'property-name-case'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'P99FrameIntervalMs'; Mutate = { param($summary) $value = $summary.p99FrameIntervalMs; $summary.Remove('p99FrameIntervalMs'); $summary['P99FrameIntervalMs'] = $value } },
    [pscustomobject]@{ Name = 'p99-nan-string'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'p99FrameIntervalMs'; Mutate = { param($summary) $summary.p99FrameIntervalMs = 'NaN' } },
    [pscustomobject]@{ Name = 'p99-infinite-number'; ExpectedPrefix = 'summary_parse_failed:'; ExpectedText = '1e309'; Mutate = { param($summary) $summary.p99FrameIntervalMs = '__XUILAB_POSITIVE_INFINITY__' } },
    [pscustomobject]@{ Name = 'main-thread-string'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'meanMainThreadNanoseconds'; Mutate = { param($summary) $summary.meanMainThreadNanoseconds = 'unavailable' } },
    [pscustomobject]@{ Name = 'main-thread-infinite-number'; ExpectedPrefix = 'summary_parse_failed:'; ExpectedText = '1e309'; Mutate = { param($summary) $summary.meanMainThreadNanoseconds = '__XUILAB_POSITIVE_INFINITY__' } },
    [pscustomobject]@{ Name = 'gc-fraction'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'totalGcAllocatedBytes'; Mutate = { param($summary) $summary.totalGcAllocatedBytes = 1.5 } },
    [pscustomobject]@{ Name = 'system-memory-string'; ExpectedPrefix = 'summary_contract_evaluation_failed:'; ExpectedText = 'lastSystemUsedMemoryBytes'; Mutate = { param($summary) $summary.lastSystemUsedMemoryBytes = 'unavailable' } },
    [pscustomobject]@{ Name = 'failure-code-mismatch'; ExpectedPrefix = 'run_contract_failed '; ExpectedText = 'failure=unexpected_exception'; Mutate = { param($summary) $summary.failureCode = 'unexpected_exception' } },
    [pscustomobject]@{ Name = 'failure-reason-mismatch'; ExpectedPrefix = 'run_contract_failed '; ExpectedText = 'failureReasonEmpty=False'; Mutate = { param($summary) $summary.failureReason = 'unexpected_failure' } },
    [pscustomobject]@{ Name = 'performance-mismatch'; ExpectedPrefix = 'run_contract_failed '; ExpectedText = 'performance=inconclusive'; Mutate = { param($summary) $summary.performanceComparison = 'inconclusive' } },
    [pscustomobject]@{ Name = 'state-case-mismatch'; ExpectedPrefix = 'run_contract_failed '; ExpectedText = 'state=COMPLETED'; Mutate = { param($summary) $summary.state = 'COMPLETED' } }
)

try {
    [void](New-Item -ItemType Directory -Path $temporaryRoot)
    $temporaryRootCreated = $true

    $scenarioIndex = 0
    foreach ($scenario in $scenarios) {
        $runStamp = [DateTime]::UtcNow.AddSeconds($scenarioIndex).ToString('yyyyMMddTHHmmssZ')
        $scenarioIndex++
        $runId = "m0-04-cal-main-idle-r1-$runStamp"
        $artifactRoot = Join-Path $temporaryRoot ('Artifacts-' + $scenario.Name)
        $fakePlayer = Join-Path $temporaryRoot ('FakeBenchmarkPlayer-' + $scenario.Name + '.cmd')
        [void](New-Item -ItemType Directory -Path $artifactRoot)

        $summary = New-ValidSummary -RunId $runId
        & $scenario.Mutate $summary
        $summaryJson = $summary | ConvertTo-Json -Depth 4 -Compress
        $summaryJson = $summaryJson.Replace('"__XUILAB_POSITIVE_INFINITY__"', '1e309')
        $fakePlayerSource = New-FakePlayerSource -SummaryJson $summaryJson
        [IO.File]::WriteAllText($fakePlayer, $fakePlayerSource, [Text.Encoding]::ASCII)

        $savedErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $invokeScript `
            -Mode Main -RunStamp $runStamp -PlayerPath $fakePlayer -ArtifactRoot $artifactRoot `
            -CandidateId 'm0-04-orchestration-test' -BuildId 'fake-player-test' `
            -SourceRevision 'workspace-test' -RunTimeoutSeconds 10 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $savedErrorActionPreference

        if ($exitCode -eq 0) {
            throw "Scenario '$($scenario.Name)' unexpectedly succeeded."
        }

        $expectedSidecarPath = Join-Path $artifactRoot ($runId + '-orchestration-failure.json')
        $sidecars = @(Get-ChildItem -LiteralPath $artifactRoot -Filter '*-orchestration-failure.json' -File -Force)
        if ($sidecars.Count -ne 1 -or -not (Test-Path -LiteralPath $expectedSidecarPath -PathType Leaf) -or
            $sidecars[0].FullName -ne $expectedSidecarPath) {
            throw "Scenario '$($scenario.Name)' produced $($sidecars.Count) sidecars, expected exactly one. Output: $($output -join [Environment]::NewLine)"
        }
        $runDirectory = Join-Path $artifactRoot $runId
        $nestedSidecars = @()
        if (Test-Path -LiteralPath $runDirectory -PathType Container) {
            $nestedSidecars = @(Get-ChildItem -LiteralPath $runDirectory -Filter '*-orchestration-failure.json' -File -Recurse -Force)
        }
        if ($nestedSidecars.Count -ne 0) {
            throw "Scenario '$($scenario.Name)' wrote a sidecar inside the run directory."
        }

        $sidecar = Get-Content -Raw -LiteralPath $sidecars[0].FullName | ConvertFrom-Json
        if ([string]$sidecar.reason -notlike ($scenario.ExpectedPrefix + '*') -or
            [string]$sidecar.reason -notlike ('*' + $scenario.ExpectedText + '*')) {
            throw "Scenario '$($scenario.Name)' produced unexpected reason: $($sidecar.reason)"
        }
        if ($sidecar.runId -ne $runId -or $sidecar.exitCode -ne 0 -or $sidecar.timedOut -ne $false) {
            throw "Scenario '$($scenario.Name)' sidecar identity or process terminal fields are incorrect."
        }

        Write-Host "PASS orchestration-rejected=$($scenario.Name) reason=$($sidecar.reason)"
    }

    $validStamp = [DateTime]::UtcNow.AddSeconds($scenarioIndex + 1).ToString('yyyyMMddTHHmmssZ')
    $validArtifactRoot = Join-Path $temporaryRoot 'Artifacts-valid-summary'
    $validFakePlayer = Join-Path $temporaryRoot 'FakeBenchmarkPlayer-valid-summary.cmd'
    [void](New-Item -ItemType Directory -Path $validArtifactRoot)
    $validSummary = New-ValidSummary -RunId '%runId%'
    $validJson = $validSummary | ConvertTo-Json -Depth 4 -Compress
    [IO.File]::WriteAllText($validFakePlayer, (New-FakePlayerSource -SummaryJson $validJson), [Text.Encoding]::ASCII)

    $validOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $invokeScript `
        -Mode Main -RunStamp $validStamp -PlayerPath $validFakePlayer -ArtifactRoot $validArtifactRoot `
        -CandidateId 'm0-04-orchestration-test' -BuildId 'fake-player-test' `
        -SourceRevision 'workspace-test' -RunTimeoutSeconds 10 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Complete valid summaries were unexpectedly rejected: $($validOutput -join [Environment]::NewLine)"
    }
    $validSidecars = @(Get-ChildItem -LiteralPath $validArtifactRoot -Filter '*-orchestration-failure.json' -File -Force)
    $validSummaries = @(Get-ChildItem -LiteralPath $validArtifactRoot -Filter 'summary.json' -File -Recurse -Force)
    if ($validSidecars.Count -ne 0 -or $validSummaries.Count -ne 10) {
        throw "Valid summary matrix produced $($validSidecars.Count) sidecars and $($validSummaries.Count) summaries; expected 0 and 10."
    }
    Write-Host 'PASS orchestration-accepted=complete-valid-summary runs=10 sidecars=0'

    Write-Host "COMPLETE orchestration valid=1 negative-scenarios=$($scenarios.Count)"
}
finally {
    $resolvedTemporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $systemTempPrefix = $resolvedSystemTemp + [IO.Path]::DirectorySeparatorChar
    if ($temporaryRootCreated -and
        $resolvedTemporaryRoot.StartsWith($systemTempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedTemporaryRoot -PathType Container)) {
        $temporaryItem = Get-Item -LiteralPath $resolvedTemporaryRoot -Force
        if (($temporaryItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing to recursively delete reparse-point temporary root: $resolvedTemporaryRoot"
        }
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}
