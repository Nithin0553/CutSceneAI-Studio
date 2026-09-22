// CutSceneAI research benchmark scene authoring utility.
// Creates a controlled Unity hallway source scene for scene-conditioned performance experiments.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class CutSceneAIHallwayBenchmarkSetup
{
    private const string ScenePath =
        "Assets/CutSceneAI/Research/Scenes/SC_HallwaySource.unity";
    private const string GuardPrefabPath =
        "Assets/Starter Assets/Runtime/SpaceRobotKyle/Prefabs/RobotKyle.prefab";

    [MenuItem("CutSceneAI/Research/Create Hallway Source Scene")]
    public static void CreateHallwaySourceScene()
    {
        if (EditorApplication.isPlaying)
            throw new InvalidOperationException(
                "Exit Play Mode before creating the CutSceneAI hallway source scene.");

        GameObject guardPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(GuardPrefabPath);
        if (guardPrefab == null)
            throw new InvalidOperationException(
                "Required RobotKyle prefab was not found at: " + GuardPrefabPath);

        EnsureFolder(ScenePath);
        Scene scene = EditorSceneManager.NewScene(
            NewSceneSetup.EmptyScene,
            NewSceneMode.Single);

        GameObject environment = Root("HallwayEnvironment", scene);
        GameObject architecture = ChildRoot("Architecture", environment.transform, scene);
        GameObject props = ChildRoot("Props", environment.transform, scene);
        GameObject characters = ChildRoot("Characters", environment.transform, scene);
        GameObject lighting = ChildRoot("Lighting", environment.transform, scene);

        // Controlled 6 m x 14 m hallway. Unity +Z/-Z is converted by the
        // bridge into the canonical right-handed CutSceneAI coordinate space.
        CreateCube(
            "Floor",
            architecture.transform,
            new Vector3(0f, -0.10f, 0f),
            Quaternion.identity,
            new Vector3(6f, 0.20f, 14f),
            true);
        CreateCube(
            "LeftWall",
            architecture.transform,
            new Vector3(-3f, 1.5f, 0f),
            Quaternion.identity,
            new Vector3(0.20f, 3f, 14f),
            true);
        CreateCube(
            "RightWall",
            architecture.transform,
            new Vector3(3f, 1.5f, 0f),
            Quaternion.identity,
            new Vector3(0.20f, 3f, 14f),
            true);
        CreateCube(
            "EndWall",
            architecture.transform,
            new Vector3(0f, 1.5f, -7f),
            Quaternion.identity,
            new Vector3(6f, 3f, 0.20f),
            true);
        CreateCube(
            "RearWall",
            architecture.transform,
            new Vector3(0f, 1.5f, 7f),
            Quaternion.identity,
            new Vector3(6f, 3f, 0.20f),
            true);
        CreateCube(
            "Ceiling",
            architecture.transform,
            new Vector3(0f, 3.1f, 0f),
            Quaternion.identity,
            new Vector3(6f, 0.20f, 14f),
            true);

        // The door is an explicit semantic target on the right side of the hallway.
        CreateCube(
            "Door_01",
            props.transform,
            new Vector3(2.85f, 1.10f, -1.0f),
            Quaternion.identity,
            new Vector3(0.12f, 2.20f, 1.20f),
            false);

        GameObject table = CreateCube(
            "Table",
            props.transform,
            new Vector3(-2.15f, 0.45f, -1.6f),
            Quaternion.identity,
            new Vector3(1.20f, 0.90f, 0.70f),
            true);
        CreateCube(
            "Book",
            props.transform,
            table.transform.position + new Vector3(0f, 0.53f, 0f),
            Quaternion.Euler(0f, 18f, 0f),
            new Vector3(0.34f, 0.06f, 0.24f),
            false);
        CreateCube(
            "StorageCrate",
            props.transform,
            new Vector3(-2.35f, 0.35f, 2.4f),
            Quaternion.Euler(0f, -12f, 0f),
            new Vector3(0.80f, 0.70f, 0.80f),
            true);

        GameObject guard = (GameObject)PrefabUtility.InstantiatePrefab(guardPrefab, scene);
        guard.name = "Guard";
        guard.transform.SetParent(characters.transform, false);
        guard.transform.SetPositionAndRotation(
            new Vector3(0f, 0f, 5f),
            Quaternion.Euler(0f, 180f, 0f));
        foreach (MonoBehaviour behaviour in guard.GetComponentsInChildren<MonoBehaviour>(true))
            behaviour.enabled = false;

        GameObject keyLight = new GameObject("Hallway_KeyLight");
        SceneManager.MoveGameObjectToScene(keyLight, scene);
        keyLight.transform.SetParent(lighting.transform, false);
        keyLight.transform.rotation = Quaternion.Euler(48f, -28f, 0f);
        Light directional = keyLight.AddComponent<Light>();
        directional.type = LightType.Directional;
        directional.intensity = 0.85f;

        GameObject practical = new GameObject("Door_PracticalLight");
        SceneManager.MoveGameObjectToScene(practical, scene);
        practical.transform.SetParent(lighting.transform, false);
        practical.transform.position = new Vector3(1.7f, 2.35f, -1.0f);
        Light point = practical.AddComponent<Light>();
        point.type = LightType.Point;
        point.range = 5f;
        point.intensity = 2.2f;

        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Selection.activeGameObject = guard;
        EditorGUIUtility.PingObject(guard);
        SceneView.lastActiveSceneView?.FrameSelected();

        Debug.Log(
            "CUTSCENEAI_HALLWAY_SOURCE_SCENE=PASS\n"
            + "SCENE=" + ScenePath + "\n"
            + "GUARD=" + guard.transform.position + " yaw=180\n"
            + "DOOR=(2.85, 1.10, -1.00)");
    }

    private static GameObject Root(string name, Scene scene)
    {
        GameObject value = new GameObject(name);
        SceneManager.MoveGameObjectToScene(value, scene);
        return value;
    }

    private static GameObject ChildRoot(string name, Transform parent, Scene scene)
    {
        GameObject value = Root(name, scene);
        value.transform.SetParent(parent, false);
        return value;
    }

    private static GameObject CreateCube(
        string name,
        Transform parent,
        Vector3 position,
        Quaternion rotation,
        Vector3 scale,
        bool isStatic)
    {
        GameObject value = GameObject.CreatePrimitive(PrimitiveType.Cube);
        value.name = name;
        value.transform.SetParent(parent, false);
        value.transform.SetPositionAndRotation(position, rotation);
        value.transform.localScale = scale;
        value.isStatic = isStatic;
        return value;
    }

    private static void EnsureFolder(string assetPath)
    {
        string directory = Path.GetDirectoryName(assetPath).Replace('\\', '/');
        string[] parts = directory.Split('/');
        string current = parts[0];
        foreach (string part in parts.Skip(1))
        {
            string next = current + "/" + part;
            if (!AssetDatabase.IsValidFolder(next))
                AssetDatabase.CreateFolder(current, part);
            current = next;
        }
    }
}
