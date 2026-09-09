using System;
using UnityEngine;

namespace XUILab.GradientLab
{
    public enum GradientSubdivisionMode { Fixed, Adaptive }

    public readonly struct GradientSelectionResult
    {
        public readonly int Segments;
        public readonly double EstimatedMaxError;
        public readonly bool QualityLimited;
        public GradientSelectionResult(int segments, double error, float tolerance)
        { Segments=segments; EstimatedMaxError=error; QualityLimited=error>tolerance; }
    }

    /// <summary>Bounds the unquantized gradient function, not arbitrary final pixels or varying base colors.</summary>
    public static class GradientSegmentSelector
    {
        public const string AlgorithmVersion="schlick-greedy-midpoint-v1";
        public const int MaximumSegments=64;
        public const float MinimumTolerance=.00001f;
        public const double NumericMargin=.000002;

        public static void Validate(int minimum, int maximum, float tolerance)
        {
            if(minimum<1 || maximum>MaximumSegments || minimum>maximum)
                throw new ArgumentOutOfRangeException(nameof(minimum));
            if(!GradientFunction.Finite(tolerance) || tolerance<MinimumTolerance || tolerance>1)
                throw new ArgumentOutOfRangeException(nameof(tolerance));
        }

        public static GradientSelectionResult Select(Color start, Color end, float bias, GradientCurve curve,
            int minimum, int maximum, float tolerance, float[] positions, double[] errors)
        {
            Validate(minimum,maximum,tolerance);
            if(positions==null || positions.Length<maximum+1)throw new ArgumentException("Position capacity.",nameof(positions));
            if(errors==null || errors.Length<maximum)throw new ArgumentException("Error capacity.",nameof(errors));
            start=GradientFunction.NormalizeColor(start);end=GradientFunction.NormalizeColor(end);
            bias=GradientFunction.NormalizeBias(bias);
            if(curve!=GradientCurve.Linear && curve!=GradientCurve.Nonlinear)throw new ArgumentOutOfRangeException(nameof(curve));
            double a=curve==GradientCurve.Linear?1:(1-(double)bias)/bias;
            double span=0;
            for(int c=0;c<4;c++)span=Math.Max(span,Math.Abs((double)end[c]-start[c]));
            int count=minimum;
            for(int i=0;i<=count;i++)positions[i]=i/(float)count;
            for(int i=0;i<count;i++)errors[i]=Error(positions[i],positions[i+1],a,span);
            while(true)
            {
                int worst=0;
                for(int i=1;i<count;i++)if(errors[i]>errors[worst])worst=i;
                if(errors[worst]<=tolerance || count==maximum)
                    return new GradientSelectionResult(count,errors[worst],tolerance);
                float midpoint=(positions[worst]+positions[worst+1])*.5f;
                if(midpoint<=positions[worst] || midpoint>=positions[worst+1])
                    return new GradientSelectionResult(count,errors[worst],tolerance);
                for(int i=count;i>=worst+1;i--)positions[i+1]=positions[i];
                for(int i=count-1;i>worst;i--)errors[i+1]=errors[i];
                positions[worst+1]=midpoint;
                errors[worst]=Error(positions[worst],positions[worst+1],a,span);
                errors[worst+1]=Error(positions[worst+1],positions[worst+2],a,span);
                count++;
            }
        }

        private static double Error(double left,double right,double a,double span)
        {
            if(span==0)return 0;
            double dl=a+(1-a)*left,dr=a+(1-a)*right;
            double roots=Math.Sqrt(dl)+Math.Sqrt(dr),width=right-left;
            return span*Math.Abs(a*(a-1))*width*width/(dl*dr*roots*roots)+NumericMargin;
        }
    }
}
