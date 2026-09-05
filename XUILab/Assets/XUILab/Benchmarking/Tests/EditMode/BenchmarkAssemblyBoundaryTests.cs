using System.Linq;
using NUnit.Framework;

namespace XUILab.Benchmarking.Tests.EditMode
{
    public sealed class BenchmarkAssemblyBoundaryTests
    {
        [Test]
        public void RuntimeAssembly_DoesNotReferenceUnityEditor()
        {
            string[] references = typeof(BenchmarkRunnerHost)
                .Assembly
                .GetReferencedAssemblies()
                .Select(name => name.Name)
                .ToArray();

            Assert.That(references, Has.None.StartsWith("UnityEditor"));
        }

        [Test]
        public void SmokeSceneContract_UsesDomainPathAndStableObjectNames()
        {
            Assert.That(BenchmarkSmokeSceneContract.ScenePath, Does.StartWith("Assets/XUILab/"));
            Assert.That(BenchmarkSmokeSceneContract.RunnerObjectName, Is.Not.Empty);
            Assert.That(BenchmarkSmokeSceneContract.CanvasObjectName, Is.Not.Empty);
            Assert.That(BenchmarkSmokeSceneContract.ImageObjectName, Is.Not.Empty);
        }
    }
}
