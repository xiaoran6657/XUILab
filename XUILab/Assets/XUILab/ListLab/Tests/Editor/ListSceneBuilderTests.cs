using System;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;
using XUILab.ListLab.Editor;

namespace XUILab.ListLab.Tests
{
    public class ListSceneBuilderTests
    {
        [Test] public void BuilderCreatesDistinctSceneRestoresSetupAndRefusesOverwrite()
        {
            string path="Assets/XUILab/Scenes/ListBuilderTest-"+Guid.NewGuid().ToString("N")+".unity";
            var original=EditorSceneManager.GetSceneManagerSetup();
            try
            {
                ListLabSceneBuilder.CreateSceneAt(path);
                Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<SceneAsset>(path));
                var after=EditorSceneManager.GetSceneManagerSetup();Assert.AreEqual(original.Length,after.Length);
                for(int i=0;i<original.Length;i++){Assert.AreEqual(original[i].path,after[i].path);Assert.AreEqual(original[i].isActive,after[i].isActive);}
                string guid=AssetDatabase.AssetPathToGUID(path);
                Assert.Throws<InvalidOperationException>(()=>ListLabSceneBuilder.CreateSceneAt(path));
                Assert.AreEqual(guid,AssetDatabase.AssetPathToGUID(path));
                Assert.Throws<ArgumentException>(()=>ListLabSceneBuilder.CreateSceneAt("Assets/../escape.unity"));
            }
            finally
            {
                EditorSceneManager.RestoreSceneManagerSetup(original);
                AssetDatabase.DeleteAsset(path); // Only this test's unique newly created asset.
            }
        }
    }
}
