using System;

namespace XUILab.Benchmarking
{
    public interface IBenchmarkCase
    {
        string Id { get; }
        bool IsReady { get; }
        void Prepare(BenchmarkRunConfig config);
        void TickWarmup(int frameIndex);
        void BeginMeasure();
        void TickMeasure(int frameIndex);
        void EndMeasure();
        BenchmarkCaseValidation Validate();
        void Cleanup();
    }

    public interface IBenchmarkCaseFactory
    {
        IBenchmarkCase Create(BenchmarkRunConfig config);
    }

    public sealed class BenchmarkCaseFactory : IBenchmarkCaseFactory
    {
        public IBenchmarkCase Create(BenchmarkRunConfig config)
        {
            if (config.caseId == "idle")
            {
                return new IdleBenchmarkCase();
            }

            if (config.caseId == "known-load")
            {
                return new KnownLoadBenchmarkCase();
            }

            throw new InvalidOperationException("Unknown benchmark case: " + config.caseId);
        }
    }

    public sealed class IdleBenchmarkCase : IBenchmarkCase
    {
        private bool prepared;
        private bool cleaned;
        private int measuredFrames;

        public string Id { get { return "idle"; } }
        public bool IsReady { get { return prepared && !cleaned; } }

        public void Prepare(BenchmarkRunConfig config)
        {
            prepared = true;
            cleaned = false;
            measuredFrames = 0;
        }

        public void TickWarmup(int frameIndex) { }
        public void BeginMeasure() { }

        public void TickMeasure(int frameIndex)
        {
            measuredFrames++;
        }

        public void EndMeasure() { }

        public BenchmarkCaseValidation Validate()
        {
            return prepared && measuredFrames > 0
                ? BenchmarkCaseValidation.Pass()
                : BenchmarkCaseValidation.Fail("Idle case did not execute measured frames.");
        }

        public void Cleanup()
        {
            if (cleaned)
            {
                return;
            }

            cleaned = true;
        }
    }

    public sealed class KnownLoadBenchmarkCase : IBenchmarkCase
    {
        private int cpuIterations;
        private int allocationBytes;
        private int measuredFrames;
        private uint checksum;
        private byte[] retainedAllocation;
        private bool prepared;
        private bool cleaned;

        public string Id { get { return "known-load"; } }
        public bool IsReady { get { return prepared && !cleaned; } }

        public void Prepare(BenchmarkRunConfig config)
        {
            cpuIterations = config.cpuIterationsPerFrame;
            allocationBytes = config.allocationBytesPerFrame;
            measuredFrames = 0;
            checksum = (uint)config.seed;
            retainedAllocation = null;
            prepared = true;
            cleaned = false;
        }

        public void TickWarmup(int frameIndex)
        {
            ExecuteLoad(frameIndex);
        }

        public void BeginMeasure() { }

        public void TickMeasure(int frameIndex)
        {
            ExecuteLoad(frameIndex);
            measuredFrames++;
        }

        public void EndMeasure() { }

        public BenchmarkCaseValidation Validate()
        {
            if (!prepared || measuredFrames <= 0)
            {
                return BenchmarkCaseValidation.Fail("Known-load case did not execute measured frames.");
            }

            if (cpuIterations == 0 && allocationBytes == 0)
            {
                return BenchmarkCaseValidation.Fail("Known-load case requires CPU iterations or allocation bytes.");
            }

            return BenchmarkCaseValidation.Pass();
        }

        public void Cleanup()
        {
            if (cleaned)
            {
                return;
            }

            retainedAllocation = null;
            cleaned = true;
        }

        private void ExecuteLoad(int frameIndex)
        {
            uint value = checksum ^ (uint)frameIndex;
            for (int i = 0; i < cpuIterations; i++)
            {
                value = (value * 1664525u) + 1013904223u;
                value ^= value >> 13;
            }

            checksum = value;

            if (allocationBytes > 0)
            {
                retainedAllocation = new byte[allocationBytes];
                retainedAllocation[0] = (byte)value;
            }
        }
    }
}
