using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace XUILab.Benchmarking.Editor
{
    public static class BenchmarkBuildMenu
    {
        private const string SmokeMenuPath = "XUILab/Benchmarking/Build Development Smoke Player";
        private const string RunnerMenuPath = "XUILab/Benchmarking/Build Development Runner Player";
        private const string EditorRunMenuPath = "XUILab/Benchmarking/Run Editor Idle Smoke";

        [MenuItem(EditorRunMenuPath)]
        public static void RunEditorIdleSmoke()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                throw new InvalidOperationException("Stop Play Mode before starting an Editor benchmark run.");
            }

            if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().isDirty)
            {
                throw new InvalidOperationException("Save the active scene before starting an Editor benchmark run.");
            }

            string repositoryRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
            string runId = $"m0-04-editor-idle-{DateTime.UtcNow:yyyyMMddTHHmmssZ}";
            var config = new BenchmarkRunConfig
            {
                runId = runId,
                tier = "editor-playmode",
                caseId = "idle",
                warmupFrames = 30,
                measureFrames = 120,
                sampleCapacity = 120,
                outputDirectory = Path.Combine(repositoryRoot, "Artifacts"),
                candidateId = "m0-04-workspace-dirty",
                buildId = "editor-playmode",
                sourceRevision = "workspace-dirty",
                dirty = true,
                quitWhenDone = false
            };

            string error = config.Validate();
            if (error != null)
            {
                throw new InvalidOperationException("Editor benchmark config invalid: " + error);
            }

            EditorSceneManager.OpenScene(BenchmarkSmokeSceneContract.ScenePath);
            File.WriteAllText(BenchmarkCommandLine.EditorRequestPath, JsonUtility.ToJson(config, true));
            Debug.Log($"XUILab editor benchmark requested runId={runId} output={config.outputDirectory}");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(SmokeMenuPath)]
        public static void BuildDevelopmentSmokePlayer()
        {
            BuildDevelopmentPlayer("m0-02-smoke-dev", "XUILab-M0-Smoke.exe");
        }

        [MenuItem(RunnerMenuPath)]
        public static void BuildDevelopmentRunnerPlayer()
        {
            BuildDevelopmentPlayer("m0-04-runner-dev", "XUILab-M0-Runner.exe");
        }

        private static void BuildDevelopmentPlayer(string buildPrefix, string executableName)
        {
            ScriptingImplementation backend = PlayerSettings.GetScriptingBackend(BuildTargetGroup.Standalone);
            if (backend != ScriptingImplementation.Mono2x)
            {
                throw new InvalidOperationException("M0 Development benchmark builds require the Mono scripting backend.");
            }

            string repositoryRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
            string buildId = $"{buildPrefix}-{DateTime.UtcNow:yyyyMMddTHHmmssZ}";
            string outputPath = Path.Combine(
                repositoryRoot,
                "Artifacts",
                buildId,
                "build",
                executableName);

            Directory.CreateDirectory(Path.GetDirectoryName(outputPath));

            var options = new BuildPlayerOptions
            {
                scenes = new[] { BenchmarkSmokeSceneContract.ScenePath },
                locationPathName = outputPath,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.Development | BuildOptions.AllowDebugging
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            BuildSummary summary = report.summary;

            var summaryRecord = new BuildSummaryRecord
            {
                buildId = buildId,
                result = summary.result.ToString(),
                backend = backend.ToString(),
                totalErrors = (int)summary.totalErrors,
                totalWarnings = (int)summary.totalWarnings,
                totalSizeBytes = checked((long)summary.totalSize),
                totalTimeSeconds = summary.totalTime.TotalSeconds,
                outputPath = outputPath,
                unityVersion = Application.unityVersion,
                createdUtc = DateTime.UtcNow.ToString("O")
            };
            File.WriteAllText(
                Path.Combine(repositoryRoot, "Artifacts", buildId, "build-summary.json"),
                JsonUtility.ToJson(summaryRecord, true));

            Debug.Log(
                $"XUILab benchmark build id={buildId} result={summary.result} backend={backend} " +
                $"errors={summary.totalErrors} warnings={summary.totalWarnings} " +
                $"size={summary.totalSize} output={outputPath}");

            if (summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    $"XUILab smoke build failed with result {summary.result} and {summary.totalErrors} errors.");
            }
        }

        [Serializable]
        private sealed class BuildSummaryRecord
        {
            public string schemaVersion = "xuilab.build.summary/v1";
            public string buildId;
            public string result;
            public string backend;
            public int totalErrors;
            public int totalWarnings;
            public long totalSizeBytes;
            public double totalTimeSeconds;
            public string outputPath;
            public string unityVersion;
            public string createdUtc;
        }
    }
}
