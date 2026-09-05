[CmdletBinding()]
param(
    [string]$ArtifactRoot = '',
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z$')][string]$MainStamp,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z$')][string]$OverheadStamp,
    [Parameter(Mandatory = $true)][string]$CandidateId,
    [Parameter(Mandatory = $true)][string]$BuildId,
    [Parameter(Mandatory = $true)][string]$SourceRevision
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ArtifactRoot)) {
    $ArtifactRoot = Join-Path $PSScriptRoot '..\..\Artifacts'
}

$resolvedArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path
$invariantCulture = [Globalization.CultureInfo]::InvariantCulture
$floatStyle = [Globalization.NumberStyles]::Float
$integerStyle = [Globalization.NumberStyles]::Integer
$requiredArtifacts = @('config.json', 'environment.json', 'events.log', 'identity.json', 'report.md', 'samples.csv', 'summary.json')

function Assert-PropertySet {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Context
    )

    $actual = @($Object.PSObject.Properties.Name | Sort-Object)
    $wanted = @($Expected | Sort-Object)
    $missing = @($wanted | Where-Object { $_ -cnotin $actual })
    $extra = @($actual | Where-Object { $_ -cnotin $wanted })
    if ($missing.Count -ne 0 -or $extra.Count -ne 0) {
        $missingText = if ($missing.Count -eq 0) { 'none' } else { $missing -join ', ' }
        $extraText = if ($extra.Count -eq 0) { 'none' } else { $extra -join ', ' }
        throw "$Context has an unexpected property set; missing=[$missingText]; extra=[$extraText]."
    }
}

function Assert-Equal {
    param($Actual, $Expected, [Parameter(Mandatory = $true)][string]$Context)
    if (-not [object]::Equals($Actual, $Expected)) {
        throw "$Context expected '$Expected', found '$Actual'."
    }
}

function Test-JsonFiniteNumber {
    param([AllowNull()]$Value)

    if ($Value -isnot [int] -and $Value -isnot [long] -and $Value -isnot [double] -and $Value -isnot [decimal]) {
        return $false
    }

    $number = [double]$Value
    return -not [double]::IsNaN($number) -and -not [double]::IsInfinity($number)
}

function Assert-JsonValueType {
    param(
        [AllowNull()]$Value,
        [Parameter(Mandatory = $true)]
        [ValidateSet('string', 'integer', 'number', 'boolean', 'object', 'array', 'string-array', 'nullable-number', 'nullable-integer')]
        [string]$ExpectedType,
        [Parameter(Mandatory = $true)][string]$Context
    )

    $valid = switch ($ExpectedType) {
        'string' { $Value -is [string] }
        'integer' { $Value -is [int] -or $Value -is [long] }
        'number' { Test-JsonFiniteNumber -Value $Value }
        'boolean' { $Value -is [bool] }
        'object' { $Value -is [pscustomobject] }
        'array' { $Value -is [object[]] }
        'string-array' {
            if ($Value -isnot [object[]]) { $false }
            else { @($Value | Where-Object { $_ -isnot [string] }).Count -eq 0 }
        }
        'nullable-number' { $null -eq $Value -or (Test-JsonFiniteNumber -Value $Value) }
        'nullable-integer' { $null -eq $Value -or $Value -is [int] -or $Value -is [long] }
    }

    if (-not $valid) {
        $actualType = if ($null -eq $Value) { 'null' } else { $Value.GetType().FullName }
        throw "$Context must be a JSON $ExpectedType; found $actualType."
    }
}

function Convert-StrictDouble {
    param([Parameter(Mandatory = $true)][string]$Text, [Parameter(Mandatory = $true)][string]$Context)
    $value = 0.0
    if (-not [double]::TryParse($Text, $floatStyle, $invariantCulture, [ref]$value) -or
        [double]::IsNaN($value) -or [double]::IsInfinity($value)) {
        throw "$Context is not a finite invariant-culture number: '$Text'."
    }
    return $value
}

function Convert-StrictInt {
    param([Parameter(Mandatory = $true)][string]$Text, [Parameter(Mandatory = $true)][string]$Context)
    $value = 0
    if (-not [int]::TryParse($Text, $integerStyle, $invariantCulture, [ref]$value)) {
        throw "$Context is not an invariant-culture integer: '$Text'."
    }
    return $value
}

function Convert-StrictLong {
    param([Parameter(Mandatory = $true)][string]$Text, [Parameter(Mandatory = $true)][string]$Context)
    $value = [long]0
    if (-not [long]::TryParse($Text, $integerStyle, $invariantCulture, [ref]$value)) {
        throw "$Context is not an invariant-culture long: '$Text'."
    }
    return $value
}

function Assert-Near {
    param(
        [Parameter(Mandatory = $true)][double]$Actual,
        [Parameter(Mandatory = $true)][double]$Expected,
        [Parameter(Mandatory = $true)][double]$Tolerance,
        [Parameter(Mandatory = $true)][string]$Context
    )
    if ([double]::IsNaN($Actual) -or [double]::IsInfinity($Actual) -or
        [double]::IsNaN($Expected) -or [double]::IsInfinity($Expected) -or
        [double]::IsNaN($Tolerance) -or [double]::IsInfinity($Tolerance) -or $Tolerance -lt 0.0) {
        throw "$Context requires finite values and a non-negative tolerance."
    }

    if ([Math]::Abs($Actual - $Expected) -gt $Tolerance) {
        throw "$Context expected $Expected, found $Actual (tolerance $Tolerance)."
    }
}

function Get-Percentile {
    param(
        [Parameter(Mandatory = $true)][double[]]$Values,
        [Parameter(Mandatory = $true)][ValidateRange(0.0, 1.0)][double]$Percentile
    )

    if ($Values.Count -eq 0) {
        throw 'Percentile requires at least one value.'
    }

    $sorted = @($Values | Sort-Object)
    if ($sorted.Count -eq 1) {
        return [double]$sorted[0]
    }

    $position = ($sorted.Count - 1) * $Percentile
    $lower = [int][Math]::Floor($position)
    $upper = [int][Math]::Ceiling($position)
    if ($lower -eq $upper) {
        return [double]$sorted[$lower]
    }

    $weight = $position - $lower
    return [double]$sorted[$lower] + (([double]$sorted[$upper] - [double]$sorted[$lower]) * $weight)
}

function Get-Distribution {
    param([Parameter(Mandatory = $true)][double[]]$Values)

    $median = Get-Percentile -Values $Values -Percentile 0.5
    $deviations = @($Values | ForEach-Object { [Math]::Abs($_ - $median) })
    $q1 = Get-Percentile -Values $Values -Percentile 0.25
    $q3 = Get-Percentile -Values $Values -Percentile 0.75

    [ordered]@{
        median = $median
        minimum = [double](($Values | Measure-Object -Minimum).Minimum)
        maximum = [double](($Values | Measure-Object -Maximum).Maximum)
        mad = Get-Percentile -Values $deviations -Percentile 0.5
        iqr = $q3 - $q1
    }
}

function Get-ArtifactSetHash {
    param([Parameter(Mandatory = $true)][string]$RunDirectory)

    $lines = foreach ($fileName in $requiredArtifacts) {
        $file = Join-Path $RunDirectory $fileName
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash
        $fileName + '|' + $hash
    }

    $payload = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n") + "`n")
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($payload))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

function New-ExpectedRun {
    param(
        [string]$RunId,
        [string]$Group,
        [string]$SeriesId,
        [int]$RunIndex,
        [string]$CaseId,
        [int]$TargetFrameRate,
        [bool]$EnableProfilerRecorders,
        [int]$CpuIterations,
        [int]$AllocationBytes
    )
    [pscustomobject]@{
        RunId = $RunId
        Group = $Group
        SeriesId = $SeriesId
        RunIndex = $RunIndex
        CaseId = $CaseId
        TargetFrameRate = $TargetFrameRate
        EnableProfilerRecorders = $EnableProfilerRecorders
        CpuIterations = $CpuIterations
        AllocationBytes = $AllocationBytes
    }
}

$expectedRuns = [Collections.Generic.List[object]]::new()
foreach ($index in 1..5) {
    $expectedRuns.Add((New-ExpectedRun -RunId "m0-04-cal-main-idle-r$index-$MainStamp" -Group 'idle-60fps' -SeriesId 'm0-04-calibration-main-60fps' -RunIndex $index -CaseId 'idle' -TargetFrameRate 60 -EnableProfilerRecorders $true -CpuIterations 0 -AllocationBytes 0))
    $expectedRuns.Add((New-ExpectedRun -RunId "m0-04-cal-main-load4m-r$index-$MainStamp" -Group 'known-load-60fps' -SeriesId 'm0-04-calibration-main-60fps' -RunIndex $index -CaseId 'known-load' -TargetFrameRate 60 -EnableProfilerRecorders $true -CpuIterations 4000000 -AllocationBytes 32768))
    $expectedRuns.Add((New-ExpectedRun -RunId "m0-04-cal-overhead-on-r$index-$OverheadStamp" -Group 'recorders-on-uncapped' -SeriesId 'm0-04-calibration-overhead-uncapped' -RunIndex $index -CaseId 'idle' -TargetFrameRate -1 -EnableProfilerRecorders $true -CpuIterations 0 -AllocationBytes 0))
    $expectedRuns.Add((New-ExpectedRun -RunId "m0-04-cal-overhead-off-r$index-$OverheadStamp" -Group 'recorders-off-uncapped' -SeriesId 'm0-04-calibration-overhead-uncapped' -RunIndex $index -CaseId 'idle' -TargetFrameRate -1 -EnableProfilerRecorders $false -CpuIterations 0 -AllocationBytes 0))
}

$actualDirectoryNames = @(
    Get-ChildItem -LiteralPath $resolvedArtifactRoot -Directory -Force |
        Where-Object { $_.Name -like "m0-04-cal-main-*-$MainStamp" -or $_.Name -like "m0-04-cal-overhead-*-$OverheadStamp" } |
        Select-Object -ExpandProperty Name |
        Sort-Object
)
$expectedDirectoryNames = @($expectedRuns.RunId | Sort-Object)
if (@(Compare-Object -CaseSensitive -ReferenceObject $expectedDirectoryNames -DifferenceObject $actualDirectoryNames).Count -ne 0) {
    throw "Calibration directory set does not match the frozen 20-run matrix. Expected $($expectedDirectoryNames.Count), found $($actualDirectoryNames.Count)."
}

$configProperties = @('schemaVersion','protocolVersion','runId','seriesId','runIndex','plannedRepeatCount','tier','caseId','caseVersion','seed','warmupFrames','measureFrames','sampleCapacity','readyTimeoutFrames','frameBudgetMs','targetFrameRate','vSyncCount','enableProfilerRecorders','requiredMetrics','optionalMetrics','cpuIterationsPerFrame','allocationBytesPerFrame','outputDirectory','candidateId','buildId','sourceRevision','dirty','quitWhenDone','faultPlan')
$faultProperties = @('mode','triggerMeasureFrame','shortageSampleCount')
$environmentProperties = @('schemaVersion','tier','unityVersion','operatingSystem','processorType','processorCount','graphicsDeviceName','graphicsDeviceType','graphicsDeviceVersion','screenWidth','screenHeight','qualityLevel','vSyncCount','targetFrameRate','scriptingBackend','buildType','metricCapabilities')
$capabilityProperties = @('name','category','unit','required','status','reason')
$identityProperties = @('schemaVersion','runId','candidateId','buildId','sourceRevision','dirty','runnerVersion','configSha256','createdUtc')
$summaryProperties = @('schemaVersion','runId','state','failureCode','failureReason','correctness','measurementValidity','performanceComparison','processSuccess','exitCode','enteredMeasure','exportSucceeded','cleanupSucceeded','sampleCount','p50FrameIntervalMs','p95FrameIntervalMs','p99FrameIntervalMs','maxFrameIntervalMs','overBudgetRatio','meanMainThreadNanoseconds','totalGcAllocatedBytes','lastSystemUsedMemoryBytes')
$csvHeader = 'sample_index,unity_frame,elapsed_ms,frame_interval_ms,main_thread_ns,gc_allocated_bytes,system_used_memory_bytes'
$environmentFingerprints = [Collections.Generic.List[string]]::new()

$runs = foreach ($expected in $expectedRuns) {
    $directory = Join-Path $resolvedArtifactRoot $expected.RunId
    $children = @(Get-ChildItem -LiteralPath $directory -Force)
    if (@($children | Where-Object { -not $_.PSIsContainer }).Count -ne 7 -or @($children | Where-Object { $_.PSIsContainer }).Count -ne 0) {
        throw "$($expected.RunId) must contain exactly seven files and no child directories."
    }
    $actualFiles = @($children | Where-Object { -not $_.PSIsContainer } | Select-Object -ExpandProperty Name | Sort-Object)
    if (@(Compare-Object -CaseSensitive -ReferenceObject $requiredArtifacts -DifferenceObject $actualFiles).Count -ne 0) {
        throw "$($expected.RunId) contains missing or extra artifacts: $($actualFiles -join ', ')."
    }

    $configPath = Join-Path $directory 'config.json'
    $environmentPath = Join-Path $directory 'environment.json'
    $identityPath = Join-Path $directory 'identity.json'
    $summaryPath = Join-Path $directory 'summary.json'
    $csvPath = Join-Path $directory 'samples.csv'
    $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $environment = Get-Content -Raw -LiteralPath $environmentPath | ConvertFrom-Json
    $identity = Get-Content -Raw -LiteralPath $identityPath | ConvertFrom-Json
    $summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json

    Assert-JsonValueType -Value $config -ExpectedType 'object' -Context "$($expected.RunId) config"
    Assert-JsonValueType -Value $environment -ExpectedType 'object' -Context "$($expected.RunId) environment"
    Assert-JsonValueType -Value $identity -ExpectedType 'object' -Context "$($expected.RunId) identity"
    Assert-JsonValueType -Value $summary -ExpectedType 'object' -Context "$($expected.RunId) summary"
    Assert-PropertySet -Object $config -Expected $configProperties -Context "$($expected.RunId) config"
    Assert-JsonValueType -Value $config.faultPlan -ExpectedType 'object' -Context "$($expected.RunId) faultPlan"
    Assert-PropertySet -Object $config.faultPlan -Expected $faultProperties -Context "$($expected.RunId) faultPlan"
    Assert-PropertySet -Object $environment -Expected $environmentProperties -Context "$($expected.RunId) environment"
    Assert-PropertySet -Object $identity -Expected $identityProperties -Context "$($expected.RunId) identity"
    Assert-PropertySet -Object $summary -Expected $summaryProperties -Context "$($expected.RunId) summary"

    foreach ($name in @('schemaVersion','protocolVersion','runId','seriesId','tier','caseId','caseVersion','outputDirectory','candidateId','buildId','sourceRevision')) {
        Assert-JsonValueType -Value $config.$name -ExpectedType 'string' -Context "$($expected.RunId) config.$name"
    }
    foreach ($name in @('runIndex','plannedRepeatCount','seed','warmupFrames','measureFrames','sampleCapacity','readyTimeoutFrames','targetFrameRate','vSyncCount','cpuIterationsPerFrame','allocationBytesPerFrame')) {
        Assert-JsonValueType -Value $config.$name -ExpectedType 'integer' -Context "$($expected.RunId) config.$name"
    }
    Assert-JsonValueType -Value $config.frameBudgetMs -ExpectedType 'number' -Context "$($expected.RunId) config.frameBudgetMs"
    foreach ($name in @('enableProfilerRecorders','dirty','quitWhenDone')) {
        Assert-JsonValueType -Value $config.$name -ExpectedType 'boolean' -Context "$($expected.RunId) config.$name"
    }
    Assert-JsonValueType -Value $config.requiredMetrics -ExpectedType 'string-array' -Context "$($expected.RunId) config.requiredMetrics"
    Assert-JsonValueType -Value $config.optionalMetrics -ExpectedType 'string-array' -Context "$($expected.RunId) config.optionalMetrics"
    Assert-JsonValueType -Value $config.faultPlan.mode -ExpectedType 'string' -Context "$($expected.RunId) faultPlan.mode"
    Assert-JsonValueType -Value $config.faultPlan.triggerMeasureFrame -ExpectedType 'integer' -Context "$($expected.RunId) faultPlan.triggerMeasureFrame"
    Assert-JsonValueType -Value $config.faultPlan.shortageSampleCount -ExpectedType 'integer' -Context "$($expected.RunId) faultPlan.shortageSampleCount"

    foreach ($name in @('schemaVersion','runId','candidateId','buildId','sourceRevision','runnerVersion','configSha256','createdUtc')) {
        Assert-JsonValueType -Value $identity.$name -ExpectedType 'string' -Context "$($expected.RunId) identity.$name"
    }
    Assert-JsonValueType -Value $identity.dirty -ExpectedType 'boolean' -Context "$($expected.RunId) identity.dirty"

    foreach ($name in @('schemaVersion','tier','unityVersion','operatingSystem','processorType','graphicsDeviceName','graphicsDeviceType','graphicsDeviceVersion','qualityLevel','scriptingBackend','buildType')) {
        Assert-JsonValueType -Value $environment.$name -ExpectedType 'string' -Context "$($expected.RunId) environment.$name"
    }
    foreach ($name in @('processorCount','screenWidth','screenHeight','vSyncCount','targetFrameRate')) {
        Assert-JsonValueType -Value $environment.$name -ExpectedType 'integer' -Context "$($expected.RunId) environment.$name"
    }
    Assert-JsonValueType -Value $environment.metricCapabilities -ExpectedType 'array' -Context "$($expected.RunId) environment.metricCapabilities"

    foreach ($name in @('schemaVersion','runId','state','failureCode','failureReason','correctness','measurementValidity','performanceComparison')) {
        Assert-JsonValueType -Value $summary.$name -ExpectedType 'string' -Context "$($expected.RunId) summary.$name"
    }
    foreach ($name in @('processSuccess','enteredMeasure','exportSucceeded','cleanupSucceeded')) {
        Assert-JsonValueType -Value $summary.$name -ExpectedType 'boolean' -Context "$($expected.RunId) summary.$name"
    }
    foreach ($name in @('exitCode','sampleCount')) {
        Assert-JsonValueType -Value $summary.$name -ExpectedType 'integer' -Context "$($expected.RunId) summary.$name"
    }
    foreach ($name in @('p50FrameIntervalMs','p95FrameIntervalMs','p99FrameIntervalMs','maxFrameIntervalMs','overBudgetRatio')) {
        Assert-JsonValueType -Value $summary.$name -ExpectedType 'number' -Context "$($expected.RunId) summary.$name"
    }
    Assert-JsonValueType -Value $summary.meanMainThreadNanoseconds -ExpectedType 'nullable-number' -Context "$($expected.RunId) summary.meanMainThreadNanoseconds"
    Assert-JsonValueType -Value $summary.totalGcAllocatedBytes -ExpectedType 'nullable-integer' -Context "$($expected.RunId) summary.totalGcAllocatedBytes"
    Assert-JsonValueType -Value $summary.lastSystemUsedMemoryBytes -ExpectedType 'nullable-integer' -Context "$($expected.RunId) summary.lastSystemUsedMemoryBytes"

    Assert-Equal $config.schemaVersion 'xuilab.benchmark.config/v1' "$($expected.RunId) config.schemaVersion"
    Assert-Equal $config.protocolVersion 'xuilab.benchmark.protocol/v1' "$($expected.RunId) config.protocolVersion"
    Assert-Equal $config.runId $expected.RunId "$($expected.RunId) config.runId"
    Assert-Equal $config.seriesId $expected.SeriesId "$($expected.RunId) config.seriesId"
    Assert-Equal ([int]$config.runIndex) $expected.RunIndex "$($expected.RunId) config.runIndex"
    Assert-Equal ([int]$config.plannedRepeatCount) 5 "$($expected.RunId) config.plannedRepeatCount"
    Assert-Equal $config.tier 'windows-development-player' "$($expected.RunId) config.tier"
    Assert-Equal $config.caseId $expected.CaseId "$($expected.RunId) config.caseId"
    Assert-Equal $config.caseVersion '1' "$($expected.RunId) config.caseVersion"
    Assert-Equal ([int]$config.seed) 1337 "$($expected.RunId) config.seed"
    Assert-Equal ([int]$config.warmupFrames) 300 "$($expected.RunId) config.warmupFrames"
    Assert-Equal ([int]$config.measureFrames) 1800 "$($expected.RunId) config.measureFrames"
    Assert-Equal ([int]$config.sampleCapacity) 1800 "$($expected.RunId) config.sampleCapacity"
    Assert-Equal ([int]$config.readyTimeoutFrames) 300 "$($expected.RunId) config.readyTimeoutFrames"
    Assert-Near ([double]$config.frameBudgetMs) 16.6666667 0.00000001 "$($expected.RunId) config.frameBudgetMs"
    Assert-Equal ([int]$config.targetFrameRate) $expected.TargetFrameRate "$($expected.RunId) config.targetFrameRate"
    Assert-Equal ([int]$config.vSyncCount) 0 "$($expected.RunId) config.vSyncCount"
    Assert-Equal ([bool]$config.enableProfilerRecorders) $expected.EnableProfilerRecorders "$($expected.RunId) config.enableProfilerRecorders"
    Assert-Equal (@($config.requiredMetrics).Count) 1 "$($expected.RunId) required metric count"
    Assert-Equal ([string]$config.requiredMetrics[0]) 'Frame Interval' "$($expected.RunId) required metric"
    Assert-Equal ((@($config.optionalMetrics) -join '|')) 'Main Thread|GC Allocated In Frame|System Used Memory' "$($expected.RunId) optional metrics"
    Assert-Equal ([int]$config.cpuIterationsPerFrame) $expected.CpuIterations "$($expected.RunId) config.cpuIterationsPerFrame"
    Assert-Equal ([int]$config.allocationBytesPerFrame) $expected.AllocationBytes "$($expected.RunId) config.allocationBytesPerFrame"
    Assert-Equal ([IO.Path]::GetFullPath([string]$config.outputDirectory).TrimEnd('\','/')) $resolvedArtifactRoot.TrimEnd('\','/') "$($expected.RunId) config.outputDirectory"
    Assert-Equal $config.candidateId $CandidateId "$($expected.RunId) config.candidateId"
    Assert-Equal $config.buildId $BuildId "$($expected.RunId) config.buildId"
    Assert-Equal $config.sourceRevision $SourceRevision "$($expected.RunId) config.sourceRevision"
    Assert-Equal ([bool]$config.dirty) $true "$($expected.RunId) config.dirty"
    Assert-Equal ([bool]$config.quitWhenDone) $true "$($expected.RunId) config.quitWhenDone"
    Assert-Equal $config.faultPlan.mode 'none' "$($expected.RunId) faultPlan.mode"
    Assert-Equal ([int]$config.faultPlan.triggerMeasureFrame) 0 "$($expected.RunId) faultPlan.triggerMeasureFrame"
    Assert-Equal ([int]$config.faultPlan.shortageSampleCount) 1 "$($expected.RunId) faultPlan.shortageSampleCount"

    Assert-Equal $identity.schemaVersion 'xuilab.benchmark.identity/v1' "$($expected.RunId) identity.schemaVersion"
    Assert-Equal $identity.runId $expected.RunId "$($expected.RunId) identity.runId"
    Assert-Equal $identity.candidateId $CandidateId "$($expected.RunId) identity.candidateId"
    Assert-Equal $identity.buildId $BuildId "$($expected.RunId) identity.buildId"
    Assert-Equal $identity.sourceRevision $SourceRevision "$($expected.RunId) identity.sourceRevision"
    Assert-Equal ([bool]$identity.dirty) $true "$($expected.RunId) identity.dirty"
    Assert-Equal $identity.runnerVersion '1' "$($expected.RunId) identity.runnerVersion"
    Assert-Equal $identity.configSha256 (Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash "$($expected.RunId) identity.configSha256"
    $createdUtc = [DateTime]::MinValue
    if (-not [DateTime]::TryParse([string]$identity.createdUtc, $invariantCulture, [Globalization.DateTimeStyles]::RoundtripKind, [ref]$createdUtc)) {
        throw "$($expected.RunId) identity.createdUtc is not round-trip time."
    }

    Assert-Equal $environment.schemaVersion 'xuilab.benchmark.environment/v1' "$($expected.RunId) environment.schemaVersion"
    Assert-Equal $environment.tier 'windows-development-player' "$($expected.RunId) environment.tier"
    Assert-Equal $environment.unityVersion '2022.3.45f1c1' "$($expected.RunId) environment.unityVersion"
    Assert-Equal $environment.graphicsDeviceType 'Direct3D11' "$($expected.RunId) environment.graphicsDeviceType"
    Assert-Equal ([int]$environment.screenWidth) 960 "$($expected.RunId) environment.screenWidth"
    Assert-Equal ([int]$environment.screenHeight) 540 "$($expected.RunId) environment.screenHeight"
    Assert-Equal $environment.qualityLevel 'High Fidelity' "$($expected.RunId) environment.qualityLevel"
    Assert-Equal ([int]$environment.vSyncCount) 0 "$($expected.RunId) environment.vSyncCount"
    Assert-Equal ([int]$environment.targetFrameRate) $expected.TargetFrameRate "$($expected.RunId) environment.targetFrameRate"
    Assert-Equal $environment.scriptingBackend 'mono' "$($expected.RunId) environment.scriptingBackend"
    Assert-Equal $environment.buildType 'development' "$($expected.RunId) environment.buildType"
    $capabilities = @($environment.metricCapabilities)
    Assert-Equal $capabilities.Count 4 "$($expected.RunId) metric capability count"
    foreach ($capability in $capabilities) {
        Assert-JsonValueType -Value $capability -ExpectedType 'object' -Context "$($expected.RunId) metric capability"
        Assert-PropertySet -Object $capability -Expected $capabilityProperties -Context "$($expected.RunId) metric capability"
        foreach ($name in @('name','category','unit','status','reason')) {
            Assert-JsonValueType -Value $capability.$name -ExpectedType 'string' -Context "$($expected.RunId) metric capability.$name"
        }
        Assert-JsonValueType -Value $capability.required -ExpectedType 'boolean' -Context "$($expected.RunId) metric capability.required"
    }
    $frameCapability = @($capabilities | Where-Object name -CEQ 'Frame Interval')
    Assert-Equal $frameCapability.Count 1 "$($expected.RunId) Frame Interval capability count"
    Assert-Equal ([bool]$frameCapability[0].required) $true "$($expected.RunId) Frame Interval required"
    Assert-Equal $frameCapability[0].category 'BuiltIn' "$($expected.RunId) Frame Interval category"
    Assert-Equal $frameCapability[0].unit 'Milliseconds' "$($expected.RunId) Frame Interval unit"
    Assert-Equal $frameCapability[0].status 'available' "$($expected.RunId) Frame Interval status"
    Assert-Equal $frameCapability[0].reason '' "$($expected.RunId) Frame Interval reason"
    Assert-Equal ((@($capabilities | Where-Object name -CNE 'Frame Interval' | Select-Object -ExpandProperty name | Sort-Object) -join '|')) 'GC Allocated In Frame|Main Thread|System Used Memory' "$($expected.RunId) optional capability names"
    $optionalSpecs = @{
        'Main Thread' = @('Internal', 'TimeNanoseconds')
        'GC Allocated In Frame' = @('Memory', 'Bytes')
        'System Used Memory' = @('Memory', 'Bytes')
    }
    foreach ($name in $optionalSpecs.Keys) {
        $optionalCapability = @($capabilities | Where-Object name -CEQ $name)
        Assert-Equal $optionalCapability.Count 1 "$($expected.RunId) $name capability count"
        Assert-Equal $optionalCapability[0].required $false "$($expected.RunId) $name required"
        Assert-Equal $optionalCapability[0].category $optionalSpecs[$name][0] "$($expected.RunId) $name category"
        if ($optionalCapability[0].status -cne 'available' -and $optionalCapability[0].status -cne 'unavailable') {
            throw "$($expected.RunId) $name status must be available or unavailable."
        }
        if ($optionalCapability[0].status -ceq 'available') {
            Assert-Equal $optionalCapability[0].unit $optionalSpecs[$name][1] "$($expected.RunId) $name unit"
            Assert-Equal $optionalCapability[0].reason '' "$($expected.RunId) $name available reason"
        }
        else {
            if ($optionalCapability[0].unit -cne $optionalSpecs[$name][1] -and $optionalCapability[0].unit -cne 'unknown') {
                throw "$($expected.RunId) $name unavailable unit is unsupported."
            }
            if ([string]::IsNullOrWhiteSpace($optionalCapability[0].reason)) {
                throw "$($expected.RunId) $name unavailable capability requires a reason."
            }
        }
    }
    $environmentFingerprints.Add((@(
        $environment.unityVersion, $environment.operatingSystem, $environment.processorType, $environment.processorCount,
        $environment.graphicsDeviceName, $environment.graphicsDeviceType, $environment.graphicsDeviceVersion,
        $environment.screenWidth, $environment.screenHeight, $environment.qualityLevel,
        $environment.scriptingBackend, $environment.buildType, $environment.tier
    ) -join '|'))

    Assert-Equal $summary.schemaVersion 'xuilab.benchmark.summary/v1' "$($expected.RunId) summary.schemaVersion"
    Assert-Equal $summary.runId $expected.RunId "$($expected.RunId) summary.runId"
    Assert-Equal $summary.state 'completed' "$($expected.RunId) summary.state"
    Assert-Equal $summary.failureCode 'none' "$($expected.RunId) summary.failureCode"
    Assert-Equal $summary.failureReason '' "$($expected.RunId) summary.failureReason"
    Assert-Equal $summary.correctness 'pass' "$($expected.RunId) summary.correctness"
    Assert-Equal $summary.measurementValidity 'valid' "$($expected.RunId) summary.measurementValidity"
    Assert-Equal $summary.performanceComparison 'not_assessed' "$($expected.RunId) summary.performanceComparison"
    Assert-Equal ([bool]$summary.processSuccess) $true "$($expected.RunId) summary.processSuccess"
    Assert-Equal ([int]$summary.exitCode) 0 "$($expected.RunId) summary.exitCode"
    Assert-Equal ([bool]$summary.enteredMeasure) $true "$($expected.RunId) summary.enteredMeasure"
    Assert-Equal ([bool]$summary.exportSucceeded) $true "$($expected.RunId) summary.exportSucceeded"
    Assert-Equal ([bool]$summary.cleanupSucceeded) $true "$($expected.RunId) summary.cleanupSucceeded"
    Assert-Equal ([int]$summary.sampleCount) 1800 "$($expected.RunId) summary.sampleCount"

    $csvLines = @(Get-Content -LiteralPath $csvPath)
    Assert-Equal $csvLines.Count 1801 "$($expected.RunId) CSV line count"
    Assert-Equal $csvLines[0] $csvHeader "$($expected.RunId) CSV header"
    $csvRows = @(Import-Csv -LiteralPath $csvPath)
    Assert-Equal $csvRows.Count 1800 "$($expected.RunId) CSV row count"
    $intervals = [Collections.Generic.List[double]]::new()
    $mainThreadValues = [Collections.Generic.List[long]]::new()
    $gcValues = [Collections.Generic.List[long]]::new()
    $memoryValues = [Collections.Generic.List[long]]::new()
    $elapsedSum = 0.0
    $previousUnityFrame = $null
    $overBudgetCount = 0
    for ($i = 0; $i -lt $csvRows.Count; $i++) {
        $row = $csvRows[$i]
        Assert-Equal (Convert-StrictInt ([string]$row.sample_index) "$($expected.RunId) row $i sample_index") $i "$($expected.RunId) row $i sample_index"
        $unityFrame = Convert-StrictInt ([string]$row.unity_frame) "$($expected.RunId) row $i unity_frame"
        if ($null -ne $previousUnityFrame -and $unityFrame -ne ($previousUnityFrame + 1)) {
            throw "$($expected.RunId) unity_frame is not consecutive at sample $i."
        }
        $previousUnityFrame = $unityFrame
        $elapsed = Convert-StrictDouble ([string]$row.elapsed_ms) "$($expected.RunId) row $i elapsed_ms"
        $interval = Convert-StrictDouble ([string]$row.frame_interval_ms) "$($expected.RunId) row $i frame_interval_ms"
        if ($interval -lt 0.0 -or $elapsed -lt 0.0) {
            throw "$($expected.RunId) contains a negative frame interval or elapsed time at sample $i."
        }
        $elapsedSum += $interval
        Assert-Near $elapsed $elapsedSum 0.0001 "$($expected.RunId) row $i cumulative elapsed_ms"
        $intervals.Add($interval)
        if ($interval -gt 16.6666667) { $overBudgetCount++ }
        if (-not [string]::IsNullOrEmpty([string]$row.main_thread_ns)) { $mainThreadValues.Add((Convert-StrictLong ([string]$row.main_thread_ns) "$($expected.RunId) row $i main_thread_ns")) }
        if (-not [string]::IsNullOrEmpty([string]$row.gc_allocated_bytes)) { $gcValues.Add((Convert-StrictLong ([string]$row.gc_allocated_bytes) "$($expected.RunId) row $i gc_allocated_bytes")) }
        if (-not [string]::IsNullOrEmpty([string]$row.system_used_memory_bytes)) { $memoryValues.Add((Convert-StrictLong ([string]$row.system_used_memory_bytes) "$($expected.RunId) row $i system_used_memory_bytes")) }
    }

    foreach ($optionalSet in @($mainThreadValues, $gcValues, $memoryValues)) {
        if ($optionalSet.Count -ne 0 -and $optionalSet.Count -ne 1800) {
            throw "$($expected.RunId) has a partially populated optional metric column."
        }
    }
    $optionalSamples = @{
        'Main Thread' = $mainThreadValues
        'GC Allocated In Frame' = $gcValues
        'System Used Memory' = $memoryValues
    }
    foreach ($name in $optionalSamples.Keys) {
        $optionalCapability = @($capabilities | Where-Object name -EQ $name)[0]
        $expectedStatus = if ($optionalSamples[$name].Count -eq 0) { 'unavailable' } else { 'available' }
        Assert-Equal $optionalCapability.status $expectedStatus "$($expected.RunId) $name status versus CSV"
        if ($expectedStatus -eq 'available') {
            Assert-Equal $optionalCapability.reason '' "$($expected.RunId) $name reason versus CSV"
        }
        elseif ([string]::IsNullOrWhiteSpace($optionalCapability.reason)) {
            throw "$($expected.RunId) $name unavailable capability requires a reason."
        }
    }
    $computedP50 = Get-Percentile -Values $intervals.ToArray() -Percentile 0.5
    $computedP95 = Get-Percentile -Values $intervals.ToArray() -Percentile 0.95
    $computedP99 = Get-Percentile -Values $intervals.ToArray() -Percentile 0.99
    $computedMax = [double](($intervals | Measure-Object -Maximum).Maximum)
    $computedOverBudget = $overBudgetCount / 1800.0
    Assert-Near ([double]$summary.p50FrameIntervalMs) $computedP50 0.000001 "$($expected.RunId) summary p50"
    Assert-Near ([double]$summary.p95FrameIntervalMs) $computedP95 0.000001 "$($expected.RunId) summary p95"
    Assert-Near ([double]$summary.p99FrameIntervalMs) $computedP99 0.000001 "$($expected.RunId) summary p99"
    Assert-Near ([double]$summary.maxFrameIntervalMs) $computedMax 0.000001 "$($expected.RunId) summary max"
    Assert-Near ([double]$summary.overBudgetRatio) $computedOverBudget 0.000001 "$($expected.RunId) summary overBudgetRatio"
    if ($mainThreadValues.Count -eq 0) {
        if ($null -ne $summary.meanMainThreadNanoseconds) { throw "$($expected.RunId) summary main-thread value must be null when CSV is empty." }
    }
    else {
        Assert-Near ([double]$summary.meanMainThreadNanoseconds) ([double](($mainThreadValues | Measure-Object -Average).Average)) 0.000001 "$($expected.RunId) summary meanMainThreadNanoseconds"
    }
    if ($gcValues.Count -eq 0) {
        if ($null -ne $summary.totalGcAllocatedBytes) { throw "$($expected.RunId) summary GC value must be null when CSV is empty." }
    }
    else {
        Assert-Equal ([long]$summary.totalGcAllocatedBytes) ([long](($gcValues | Measure-Object -Sum).Sum)) "$($expected.RunId) summary totalGcAllocatedBytes"
    }
    if ($memoryValues.Count -eq 0) {
        if ($null -ne $summary.lastSystemUsedMemoryBytes) { throw "$($expected.RunId) summary memory value must be null when CSV is empty." }
    }
    else {
        Assert-Equal ([long]$summary.lastSystemUsedMemoryBytes) $memoryValues[$memoryValues.Count - 1] "$($expected.RunId) summary lastSystemUsedMemoryBytes"
    }

    [pscustomobject][ordered]@{
        runId = $expected.RunId
        group = $expected.Group
        runIndex = $expected.RunIndex
        candidateId = $identity.candidateId
        buildId = $identity.buildId
        sourceRevision = $identity.sourceRevision
        configSha256 = $identity.configSha256
        artifactSetSha256 = Get-ArtifactSetHash -RunDirectory $directory
        p50FrameIntervalMs = [double]$summary.p50FrameIntervalMs
        p95FrameIntervalMs = [double]$summary.p95FrameIntervalMs
        p99FrameIntervalMs = [double]$summary.p99FrameIntervalMs
        maxFrameIntervalMs = [double]$summary.maxFrameIntervalMs
        overBudgetRatio = [double]$summary.overBudgetRatio
    }
}

$fingerprints = @($environmentFingerprints | Sort-Object -Unique)
if ($fingerprints.Count -ne 1) {
    throw "Calibration runs do not share one hardware/environment fingerprint; found $($fingerprints.Count)."
}

$expectedGroups = @('idle-60fps', 'known-load-60fps', 'recorders-on-uncapped', 'recorders-off-uncapped')
$aggregates = foreach ($groupName in $expectedGroups) {
    $groupRuns = @($runs | Where-Object group -EQ $groupName | Sort-Object runIndex)
    Assert-Equal $groupRuns.Count 5 "$groupName repeat count"
    Assert-Equal (($groupRuns.runIndex -join ',')) '1,2,3,4,5' "$groupName run indexes"
    [pscustomobject][ordered]@{
        group = $groupName
        repeatCount = $groupRuns.Count
        p50FrameIntervalMs = Get-Distribution -Values @($groupRuns.p50FrameIntervalMs)
        p95FrameIntervalMs = Get-Distribution -Values @($groupRuns.p95FrameIntervalMs)
        p99FrameIntervalMs = Get-Distribution -Values @($groupRuns.p99FrameIntervalMs)
        maxFrameIntervalMs = Get-Distribution -Values @($groupRuns.maxFrameIntervalMs)
        overBudgetRatio = Get-Distribution -Values @($groupRuns.overBudgetRatio)
    }
}

[pscustomobject][ordered]@{
    schemaVersion = 'xuilab.benchmark.calibration-summary/v1'
    protocolVersion = 'xuilab.benchmark.protocol/v1'
    percentileMethod = 'linear interpolation at (n - 1) * p'
    aggregateMethod = 'per-run statistics; median, min, max, MAD, IQR; no frame concatenation'
    candidateId = $CandidateId
    buildId = $BuildId
    sourceRevision = $SourceRevision
    environmentFingerprint = $fingerprints[0]
    mainStamp = $MainStamp
    overheadStamp = $OverheadStamp
    runCount = $runs.Count
    aggregates = @($aggregates)
    runs = @($runs | Sort-Object group, runIndex)
} | ConvertTo-Json -Depth 8
