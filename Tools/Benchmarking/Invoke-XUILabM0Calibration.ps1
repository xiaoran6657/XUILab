[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Main', 'Overhead')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$RunStamp,

    [Parameter(Mandatory = $true)]
    [string]$PlayerPath,
    [string]$ArtifactRoot = '',
    [Parameter(Mandatory = $true)]
    [string]$CandidateId,
    [Parameter(Mandatory = $true)]
    [string]$BuildId,
    [Parameter(Mandatory = $true)]
    [string]$SourceRevision,
    [ValidateRange(1, 3600)]
    [int]$RunTimeoutSeconds = 180,
    [ValidateSet('none', 'prepare_failure', 'ready_timeout', 'required_metric_unavailable', 'sample_shortage', 'cancel', 'case_exception', 'export_failure', 'cleanup_failure', 'focus_loss', 'pause')]
    [string]$DiagnosticFault = 'none'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ArtifactRoot)) {
    $ArtifactRoot = Join-Path $PSScriptRoot '..\..\Artifacts'
}

$resolvedPlayer = (Resolve-Path -LiteralPath $PlayerPath).Path
$resolvedArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path
$protocolVersion = 'xuilab.benchmark.protocol/v1'
$warmupFrames = 300
$measureFrames = 1800
$repeatCount = 5
$summaryProperties = @(
    'schemaVersion', 'runId', 'state', 'failureCode', 'failureReason', 'correctness',
    'measurementValidity', 'performanceComparison', 'processSuccess', 'exitCode',
    'enteredMeasure', 'exportSucceeded', 'cleanupSucceeded', 'sampleCount',
    'p50FrameIntervalMs', 'p95FrameIntervalMs', 'p99FrameIntervalMs',
    'maxFrameIntervalMs', 'overBudgetRatio', 'meanMainThreadNanoseconds',
    'totalGcAllocatedBytes', 'lastSystemUsedMemoryBytes'
)

function Quote-ProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value.Contains('"')) {
        throw "Argument contains an unsupported quote: $Value"
    }

    return '"' + $Value + '"'
}

function New-RunDefinition {
    param(
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$SeriesId,
        [Parameter(Mandatory = $true)][int]$RunIndex,
        [Parameter(Mandatory = $true)][string]$CaseId,
        [Parameter(Mandatory = $true)][int]$TargetFrameRate,
        [Parameter(Mandatory = $true)][bool]$EnableProfilerRecorders
    )

    [pscustomobject]@{
        RunId = $RunId
        SeriesId = $SeriesId
        RunIndex = $RunIndex
        CaseId = $CaseId
        TargetFrameRate = $TargetFrameRate
        EnableProfilerRecorders = $EnableProfilerRecorders
    }
}

function Get-RequiredSummaryProperty {
    param(
        [Parameter(Mandatory = $true)]$Summary,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $property = $Summary.PSObject.Properties[$Name]
    if ($null -eq $property) {
        throw "summary is missing required property '$Name'."
    }
    return $property.Value
}

function Assert-SummaryPropertySet {
    param([Parameter(Mandatory = $true)]$Summary)

    $actual = @($Summary.PSObject.Properties.Name | Sort-Object)
    $expected = @($summaryProperties | Sort-Object)
    $missing = @($expected | Where-Object { $_ -cnotin $actual })
    $extra = @($actual | Where-Object { $_ -cnotin $expected })
    if ($missing.Count -ne 0 -or $extra.Count -ne 0) {
        $missingText = if ($missing.Count -eq 0) { 'none' } else { $missing -join ', ' }
        $extraText = if ($extra.Count -eq 0) { 'none' } else { $extra -join ', ' }
        throw "summary property set mismatch; missing=[$missingText]; extra=[$extraText]."
    }
}

function Assert-SummaryValueType {
    param(
        [AllowNull()]$Value,
        [Parameter(Mandatory = $true)][ValidateSet('string', 'boolean', 'integer', 'number', 'nullable-number', 'nullable-integer')][string]$ExpectedType,
        [Parameter(Mandatory = $true)][string]$Context
    )

    $valid = switch ($ExpectedType) {
        'string' { $Value -is [string] }
        'boolean' { $Value -is [bool] }
        'integer' { $Value -is [int] -or $Value -is [long] }
        'number' {
            if ($Value -isnot [int] -and $Value -isnot [long] -and $Value -isnot [double] -and $Value -isnot [decimal]) { $false }
            else {
                $number = [double]$Value
                -not [double]::IsNaN($number) -and -not [double]::IsInfinity($number)
            }
        }
        'nullable-number' {
            if ($null -eq $Value) { $true }
            elseif ($Value -isnot [int] -and $Value -isnot [long] -and $Value -isnot [double] -and $Value -isnot [decimal]) { $false }
            else {
                $number = [double]$Value
                -not [double]::IsNaN($number) -and -not [double]::IsInfinity($number)
            }
        }
        'nullable-integer' {
            $null -eq $Value -or $Value -is [int] -or $Value -is [long]
        }
    }

    if (-not $valid) {
        $actualType = if ($null -eq $Value) { 'null' } else { $Value.GetType().FullName }
        throw "$Context must be a JSON $ExpectedType; found $actualType."
    }
}

function Write-OrchestrationFailureSidecar {
    param(
        [Parameter(Mandatory = $true)]$Definition,
        [Parameter(Mandatory = $true)][string]$Reason,
        [Parameter(Mandatory = $true)][string]$PlayerLog,
        [Parameter(Mandatory = $true)][datetime]$StartedUtc,
        [Nullable[int]]$ProcessId,
        [Nullable[int]]$ExitCode,
        [bool]$TimedOut = $false
    )

    $sidecarPath = Join-Path $resolvedArtifactRoot ($Definition.RunId + '-orchestration-failure.json')
    if (Test-Path -LiteralPath $sidecarPath) {
        throw "Refusing to overwrite orchestration failure sidecar: $sidecarPath"
    }

    $record = [ordered]@{
        schemaVersion = 'xuilab.benchmark.orchestration-failure/v1'
        runId = $Definition.RunId
        reason = $Reason
        timedOut = $TimedOut
        processId = if ($null -eq $ProcessId) { $null } else { [int]$ProcessId }
        exitCode = if ($null -eq $ExitCode) { $null } else { [int]$ExitCode }
        startedUtc = $StartedUtc.ToString('O')
        observedUtc = [DateTime]::UtcNow.ToString('O')
        timeoutSeconds = $RunTimeoutSeconds
        playerPath = $resolvedPlayer
        playerLog = $PlayerLog
        expectedRunDirectory = (Join-Path $resolvedArtifactRoot $Definition.RunId)
        candidateId = $CandidateId
        buildId = $BuildId
        sourceRevision = $SourceRevision
        diagnosticFault = $DiagnosticFault
    }

    $json = $record | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($sidecarPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return $sidecarPath
}

function Invoke-BenchmarkRun {
    param([Parameter(Mandatory = $true)]$Definition)

    $runDirectory = Join-Path $resolvedArtifactRoot $Definition.RunId
    if (Test-Path -LiteralPath $runDirectory) {
        throw "Refusing to overwrite existing run directory: $runDirectory"
    }

    $playerLog = Join-Path $resolvedArtifactRoot ($Definition.RunId + '-player.log')
    if (Test-Path -LiteralPath $playerLog) {
        throw "Refusing to overwrite existing Player log: $playerLog"
    }

    $arguments = @(
        '-screen-fullscreen', '0',
        '-screen-width', '960',
        '-screen-height', '540',
        '-logFile', (Quote-ProcessArgument $playerLog),
        '--xuilab-run',
        '--xuilab-quit',
        '--xuilab-output-root', (Quote-ProcessArgument $resolvedArtifactRoot),
        '--xuilab-run-id', $Definition.RunId,
        '--xuilab-series-id', $Definition.SeriesId,
        '--xuilab-run-index', ([string]$Definition.RunIndex),
        '--xuilab-repeat-count', ([string]$repeatCount),
        '--xuilab-protocol-version', $protocolVersion,
        '--xuilab-case', $Definition.CaseId,
        '--xuilab-warmup-frames', ([string]$warmupFrames),
        '--xuilab-measure-frames', ([string]$measureFrames),
        '--xuilab-sample-capacity', ([string]$measureFrames),
        '--xuilab-ready-timeout-frames', '300',
        '--xuilab-frame-budget-ms', '16.6666667',
        '--xuilab-target-frame-rate', ([string]$Definition.TargetFrameRate),
        '--xuilab-vsync-count', '0',
        '--xuilab-candidate-id', $CandidateId,
        '--xuilab-build-id', $BuildId,
        '--xuilab-source-revision', $SourceRevision
    )

    if ($Definition.CaseId -eq 'known-load') {
        $arguments += @('--xuilab-cpu-iterations', '4000000', '--xuilab-allocation-bytes', '32768')
    }

    if (-not $Definition.EnableProfilerRecorders) {
        $arguments += '--xuilab-disable-profiler-recorders'
    }

    if ($DiagnosticFault -ne 'none') {
        $arguments += @('--xuilab-fault', $DiagnosticFault)
    }

    Write-Host "START run=$($Definition.RunId) case=$($Definition.CaseId) target=$($Definition.TargetFrameRate) recorders=$($Definition.EnableProfilerRecorders)"
    $startedUtc = [DateTime]::UtcNow
    try {
        $process = Start-Process -FilePath $resolvedPlayer -ArgumentList $arguments -WindowStyle Hidden -PassThru
    }
    catch {
        $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason ('process_start_failed: ' + $_.Exception.Message) -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $null -ExitCode $null
        throw "Player process could not start; sidecar=$sidecar"
    }

    $exited = $process.WaitForExit($RunTimeoutSeconds * 1000)
    if (-not $exited) {
        $launchedPid = $process.Id
        $terminationError = $null
        try {
            Stop-Process -Id $launchedPid -Force -ErrorAction Stop
        }
        catch {
            $terminationError = $_.Exception.Message
        }
        $terminated = $process.WaitForExit(10000)
        $process.Refresh()
        if (-not $terminated -or -not $process.HasExited) {
            $reason = 'wall_clock_timeout_termination_failed'
            if (-not [string]::IsNullOrWhiteSpace($terminationError)) {
                $reason += ': ' + $terminationError
            }
            $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason $reason -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $launchedPid -ExitCode $null -TimedOut $true
            throw "Run exceeded wall-clock timeout and launched PID $launchedPid could not be confirmed exited: $($Definition.RunId); sidecar=$sidecar"
        }
        $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason 'wall_clock_timeout_process_terminated' -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $launchedPid -ExitCode $process.ExitCode -TimedOut $true
        throw "Run exceeded wall-clock timeout and launched PID $launchedPid was terminated: $($Definition.RunId); sidecar=$sidecar"
    }

    $process.Refresh()

    $summaryPath = Join-Path $runDirectory 'summary.json'
    if (-not (Test-Path -LiteralPath $summaryPath)) {
        $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason 'summary_missing' -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $process.Id -ExitCode $process.ExitCode
        throw "Run produced no summary.json: $($Definition.RunId); process exit=$($process.ExitCode); sidecar=$sidecar"
    }

    try {
        $summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
    }
    catch {
        $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason ('summary_parse_failed: ' + $_.Exception.Message) -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $process.Id -ExitCode $process.ExitCode
        throw "Run summary could not be parsed: $($Definition.RunId); sidecar=$sidecar"
    }

    try {
        Assert-SummaryPropertySet -Summary $summary
        $summarySchema = Get-RequiredSummaryProperty -Summary $summary -Name 'schemaVersion'
        $summaryRunId = Get-RequiredSummaryProperty -Summary $summary -Name 'runId'
        $summaryState = Get-RequiredSummaryProperty -Summary $summary -Name 'state'
        $summaryFailureCode = Get-RequiredSummaryProperty -Summary $summary -Name 'failureCode'
        $summaryFailureReason = Get-RequiredSummaryProperty -Summary $summary -Name 'failureReason'
        $summaryCorrectness = Get-RequiredSummaryProperty -Summary $summary -Name 'correctness'
        $summaryValidity = Get-RequiredSummaryProperty -Summary $summary -Name 'measurementValidity'
        $summaryPerformance = Get-RequiredSummaryProperty -Summary $summary -Name 'performanceComparison'
        $summaryProcessSuccess = Get-RequiredSummaryProperty -Summary $summary -Name 'processSuccess'
        $summaryExitCode = Get-RequiredSummaryProperty -Summary $summary -Name 'exitCode'
        $summaryEnteredMeasure = Get-RequiredSummaryProperty -Summary $summary -Name 'enteredMeasure'
        $summaryExportSucceeded = Get-RequiredSummaryProperty -Summary $summary -Name 'exportSucceeded'
        $summaryCleanupSucceeded = Get-RequiredSummaryProperty -Summary $summary -Name 'cleanupSucceeded'
        $summarySampleCount = Get-RequiredSummaryProperty -Summary $summary -Name 'sampleCount'
        $summaryP50 = Get-RequiredSummaryProperty -Summary $summary -Name 'p50FrameIntervalMs'
        $summaryP95 = Get-RequiredSummaryProperty -Summary $summary -Name 'p95FrameIntervalMs'
        $summaryP99 = Get-RequiredSummaryProperty -Summary $summary -Name 'p99FrameIntervalMs'
        $summaryMax = Get-RequiredSummaryProperty -Summary $summary -Name 'maxFrameIntervalMs'
        $summaryOverBudget = Get-RequiredSummaryProperty -Summary $summary -Name 'overBudgetRatio'
        $summaryMeanMainThread = Get-RequiredSummaryProperty -Summary $summary -Name 'meanMainThreadNanoseconds'
        $summaryTotalGc = Get-RequiredSummaryProperty -Summary $summary -Name 'totalGcAllocatedBytes'
        $summaryLastSystemMemory = Get-RequiredSummaryProperty -Summary $summary -Name 'lastSystemUsedMemoryBytes'

        foreach ($entry in @(
            @($summarySchema, 'schemaVersion'), @($summaryRunId, 'runId'), @($summaryState, 'state'),
            @($summaryFailureCode, 'failureCode'), @($summaryFailureReason, 'failureReason'),
            @($summaryCorrectness, 'correctness'), @($summaryValidity, 'measurementValidity'),
            @($summaryPerformance, 'performanceComparison')
        )) {
            Assert-SummaryValueType -Value $entry[0] -ExpectedType 'string' -Context "summary.$($entry[1])"
        }
        foreach ($entry in @(
            @($summaryProcessSuccess, 'processSuccess'), @($summaryEnteredMeasure, 'enteredMeasure'),
            @($summaryExportSucceeded, 'exportSucceeded'), @($summaryCleanupSucceeded, 'cleanupSucceeded')
        )) {
            Assert-SummaryValueType -Value $entry[0] -ExpectedType 'boolean' -Context "summary.$($entry[1])"
        }
        Assert-SummaryValueType -Value $summaryExitCode -ExpectedType 'integer' -Context 'summary.exitCode'
        Assert-SummaryValueType -Value $summarySampleCount -ExpectedType 'integer' -Context 'summary.sampleCount'
        Assert-SummaryValueType -Value $summaryP50 -ExpectedType 'nullable-number' -Context 'summary.p50FrameIntervalMs'
        Assert-SummaryValueType -Value $summaryP95 -ExpectedType 'nullable-number' -Context 'summary.p95FrameIntervalMs'
        Assert-SummaryValueType -Value $summaryP99 -ExpectedType 'nullable-number' -Context 'summary.p99FrameIntervalMs'
        Assert-SummaryValueType -Value $summaryMax -ExpectedType 'nullable-number' -Context 'summary.maxFrameIntervalMs'
        Assert-SummaryValueType -Value $summaryOverBudget -ExpectedType 'nullable-number' -Context 'summary.overBudgetRatio'
        Assert-SummaryValueType -Value $summaryMeanMainThread -ExpectedType 'nullable-number' -Context 'summary.meanMainThreadNanoseconds'
        Assert-SummaryValueType -Value $summaryTotalGc -ExpectedType 'nullable-integer' -Context 'summary.totalGcAllocatedBytes'
        Assert-SummaryValueType -Value $summaryLastSystemMemory -ExpectedType 'nullable-integer' -Context 'summary.lastSystemUsedMemoryBytes'

        $success = $process.ExitCode -eq 0 -and
            $summarySchema -ceq 'xuilab.benchmark.summary/v1' -and
            $summaryRunId -ceq $Definition.RunId -and
            $summaryState -ceq 'completed' -and
            $summaryFailureCode -ceq 'none' -and
            $summaryFailureReason -ceq '' -and
            $summaryCorrectness -ceq 'pass' -and
            $summaryValidity -ceq 'valid' -and
            $summaryPerformance -ceq 'not_assessed' -and
            $summaryProcessSuccess -eq $true -and
            $summaryExitCode -eq 0 -and
            $summaryEnteredMeasure -eq $true -and
            $summaryExportSucceeded -eq $true -and
            $summaryCleanupSucceeded -eq $true -and
            $summarySampleCount -eq $measureFrames

        if ($success) {
            Assert-SummaryValueType -Value $summaryP50 -ExpectedType 'number' -Context 'summary.p50FrameIntervalMs'
            Assert-SummaryValueType -Value $summaryP95 -ExpectedType 'number' -Context 'summary.p95FrameIntervalMs'
            Assert-SummaryValueType -Value $summaryP99 -ExpectedType 'number' -Context 'summary.p99FrameIntervalMs'
            Assert-SummaryValueType -Value $summaryMax -ExpectedType 'number' -Context 'summary.maxFrameIntervalMs'
            Assert-SummaryValueType -Value $summaryOverBudget -ExpectedType 'number' -Context 'summary.overBudgetRatio'
        }
    }
    catch {
        $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason ('summary_contract_evaluation_failed: ' + $_.Exception.Message) -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $process.Id -ExitCode $process.ExitCode
        throw "Run summary contract could not be evaluated: $($Definition.RunId); sidecar=$sidecar"
    }

    if (-not $success) {
        $failureReasonEmpty = [string]::IsNullOrEmpty([string]$summaryFailureReason)
        $reason = "run_contract_failed process=$($process.ExitCode) state=$summaryState failure=$summaryFailureCode failureReasonEmpty=$failureReasonEmpty correctness=$summaryCorrectness validity=$summaryValidity performance=$summaryPerformance summaryExit=$summaryExitCode samples=$summarySampleCount"
        $sidecar = Write-OrchestrationFailureSidecar -Definition $Definition -Reason $reason -PlayerLog $playerLog -StartedUtc $startedUtc -ProcessId $process.Id -ExitCode $process.ExitCode
        throw "Run contract failed: $($Definition.RunId); sidecar=$sidecar"
    }

    Write-Host "PASS run=$($Definition.RunId) samples=$summarySampleCount p50=$summaryP50 p95=$summaryP95 p99=$summaryP99 max=$summaryMax overBudget=$summaryOverBudget"
}

$runs = [System.Collections.Generic.List[object]]::new()

if ($Mode -eq 'Main') {
    # Frozen interleaved order: ABBA, ABBA, AB. RunIndex is per Case, not global.
    $mainOrder = @(
        @('idle', 1), @('known-load', 1), @('known-load', 2), @('idle', 2),
        @('idle', 3), @('known-load', 3), @('known-load', 4), @('idle', 4),
        @('idle', 5), @('known-load', 5)
    )

    foreach ($entry in $mainOrder) {
        $caseId = [string]$entry[0]
        $runIndex = [int]$entry[1]
        $caseSlug = if ($caseId -eq 'known-load') { 'load4m' } else { 'idle' }
        $runId = "m0-04-cal-main-$caseSlug-r$runIndex-$RunStamp"
        $runs.Add((New-RunDefinition -RunId $runId -SeriesId 'm0-04-calibration-main-60fps' -RunIndex $runIndex -CaseId $caseId -TargetFrameRate 60 -EnableProfilerRecorders $true))
    }
}
else {
    # Frozen interleaved order: ABBA, ABBA, AB. Both sides use the uncapped idle Case.
    $overheadOrder = @(
        @($true, 1), @($false, 1), @($false, 2), @($true, 2),
        @($true, 3), @($false, 3), @($false, 4), @($true, 4),
        @($true, 5), @($false, 5)
    )

    foreach ($entry in $overheadOrder) {
        $recordersEnabled = [bool]$entry[0]
        $runIndex = [int]$entry[1]
        $modeSlug = if ($recordersEnabled) { 'on' } else { 'off' }
        $runId = "m0-04-cal-overhead-$modeSlug-r$runIndex-$RunStamp"
        $runs.Add((New-RunDefinition -RunId $runId -SeriesId 'm0-04-calibration-overhead-uncapped' -RunIndex $runIndex -CaseId 'idle' -TargetFrameRate -1 -EnableProfilerRecorders $recordersEnabled))
    }
}

foreach ($run in $runs) {
    Invoke-BenchmarkRun -Definition $run
}

Write-Host "COMPLETE mode=$Mode runs=$($runs.Count) protocol=$protocolVersion"
