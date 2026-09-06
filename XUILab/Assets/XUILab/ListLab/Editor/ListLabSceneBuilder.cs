using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;

namespace XUILab.ListLab.Editor
{
    public static class ListLabSceneBuilder
    {
        public const string ScenePath = "Assets/XUILab/Scenes/ListLab.unity";
        [MenuItem("XUILab/List Lab/Create demonstration scene")]
        public static void CreateScene() { CreateSceneAt(ScenePath); }
        public static void CreateSceneAt(string targetPath)
        {
            if(string.IsNullOrEmpty(targetPath)||!targetPath.StartsWith("Assets/XUILab/Scenes/",StringComparison.Ordinal)||
                targetPath.Contains("..")||!targetPath.EndsWith(".unity",StringComparison.Ordinal))throw new ArgumentException("Scene must be within the List Lab scene directory.");
            if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling || BuildPipeline.isBuildingPlayer)
                throw new InvalidOperationException("Editor must be idle.");
            for (int i=0;i<SceneManager.sceneCount;i++) if (SceneManager.GetSceneAt(i).isDirty) throw new InvalidOperationException("An open scene is dirty.");
            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(targetPath)) throw new InvalidOperationException("ListLab scene already exists; refusing overwrite.");
            var previous = EditorSceneManager.GetSceneManagerSetup();
            try
            {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var camera = new GameObject("Main Camera", typeof(Camera)); camera.tag = "MainCamera";
                camera.GetComponent<Camera>().clearFlags = CameraClearFlags.SolidColor; camera.GetComponent<Camera>().backgroundColor = new Color(.025f,.045f,.075f);
                var light = new GameObject("Directional Light", typeof(Light)); light.GetComponent<Light>().type = LightType.Directional;
                new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
                new GameObject("ListLabDemo", typeof(ListLabDemo));
                if (!EditorSceneManager.SaveScene(scene,targetPath)) throw new InvalidOperationException("Scene save failed.");
            }
            finally { EditorSceneManager.RestoreSceneManagerSetup(previous); }
        }
    }
}
