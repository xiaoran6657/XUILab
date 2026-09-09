using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;

namespace XUILab.GradientLab.Editor
{
    public static class GradientLabSceneBuilder
    {
        public const string ScenePath="Assets/XUILab/Scenes/GradientLab.unity";
        [MenuItem("XUILab/Gradient Lab/Create demonstration scene")]
        public static void CreateScene()
        {
            if(EditorApplication.isPlayingOrWillChangePlaymode||EditorApplication.isCompiling||BuildPipeline.isBuildingPlayer)throw new InvalidOperationException("Editor must be idle.");
            if(PrefabStageUtility.GetCurrentPrefabStage()!=null)throw new InvalidOperationException("Close prefab stage first.");
            for(int i=0;i<SceneManager.sceneCount;i++)if(SceneManager.GetSceneAt(i).isDirty)throw new InvalidOperationException("Open scene is dirty.");
            if(AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath))throw new InvalidOperationException("Refusing to overwrite existing GradientLab scene.");
            var previous=EditorSceneManager.GetSceneManagerSetup();
            try
            {
                var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                var camera=new GameObject("Main Camera",typeof(Camera));camera.tag="MainCamera";camera.GetComponent<Camera>().clearFlags=CameraClearFlags.SolidColor;camera.GetComponent<Camera>().backgroundColor=new Color(.025f,.045f,.075f);
                new GameObject("Directional Light",typeof(Light)).GetComponent<Light>().type=LightType.Directional;
                new GameObject("EventSystem",typeof(EventSystem),typeof(StandaloneInputModule));new GameObject("GradientLabDemo",typeof(GradientLabDemo));
                if(!EditorSceneManager.SaveScene(scene,ScenePath))throw new InvalidOperationException("Save failed.");
            }
            finally{EditorSceneManager.RestoreSceneManagerSetup(previous);}
        }
    }
}
