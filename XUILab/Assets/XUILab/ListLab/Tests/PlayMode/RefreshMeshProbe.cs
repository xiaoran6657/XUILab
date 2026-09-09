using System.Collections.Generic;
using UnityEngine.UI;

namespace XUILab.ListLab.Tests
{
    // Diagnostic observer only: never changes the VertexHelper.
    public sealed class RefreshMeshProbe : BaseMeshEffect
    {
        public int Calls { get; private set; }
        public int LastVertices { get; private set; } = -1;
        public readonly List<int> Indices = new List<int>();
        public override void ModifyMesh(VertexHelper mesh)
        {
            if (!IsActive()) return;
            Calls++;
            var cell=GetComponentInParent<ListCell>();
            Indices.Add(cell?cell.Index:-1);
            LastVertices = mesh.currentVertCount;
        }
        public void ResetObservation() { Calls = 0; LastVertices = -1; Indices.Clear(); }
    }
}

