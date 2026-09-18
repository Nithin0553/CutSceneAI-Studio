// CutSceneAI Studio Bridge v0.1.0
// Research-grade local editor bridge. It only accepts an explicit allowlist of commands.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Playables;
using UnityEngine.SceneManagement;
using UnityEngine.Timeline;

[InitializeOnLoad]
public static class CutSceneAIStudioBridge
{
    private const string ConfigAssetPath = "Assets/CutSceneAI/Bridge/cutsceneai-bridge.json";
    private const string BridgeVersion = "0.1.0";
    private const double HeartbeatIntervalSeconds = 10.0;
    private const double PollIntervalSeconds = 2.0;

    [Serializable]
    private sealed class Config
    {
        public string bridge_version;
        public string project_id;
        public string backend_url;
        public float poll_interval_seconds = 2.0f;
    }

    [Serializable]
    private sealed class AssetMetadata
    {
        public string asset_type;
        public string animator_path;
        public bool humanoid;
        public int humanoid_bone_count;
        public int blendshape_count;
        public string facial_renderer_path;
        public string class_name;
    }

    [Serializable]
    private sealed class AssetRecord
    {
        public string object_id;
        public string kind;
        public string display_name;
        public string engine_ref;
        public string relative_path;
        public bool verified;
        public AssetMetadata metadata;
    }

    [Serializable]
    private sealed class Heartbeat
    {
        public string agent_id;
        public string engine_version;
        public string adapter_version;
        public string current_scene;
        public int fps;
        public string[] capabilities;
        public AssetRecord[] assets;
        public string[] warnings;
    }

    [Serializable]
    private sealed class BridgeCommand
    {
        public string command_id;
        public string project_id;
        public string engine;
        public string command;
        public string status;
    }

    [Serializable]
    private sealed class PollResponse
    {
        public BridgeCommand command;
    }

    [Serializable]
    private sealed class CommandResult
    {
        public string current_scene;
        public bool is_playing;
        public int scene_actor_count;
        public int playable_director_count;
        public string selected_object;
        public string message;
    }

    [Serializable]
    private sealed class CompleteRequest
    {
        public string agent_id;
        public bool succeeded;
        public CommandResult result;
        public string error;
    }

    private static Config _config;
    private static string _agentId;
    private static bool _requestInFlight;
    private static double _nextHeartbeat;
    private static double _nextPoll;

    static CutSceneAIStudioBridge()
    {
        EditorApplication.update += Tick;
        EditorApplication.delayCall += ReloadConfig;
    }

    [MenuItem("CutSceneAI/Studio Bridge/Reload Configuration")]
    private static void ReloadConfig()
    {
        _config = null;
        _agentId = null;
        if (!File.Exists(ConfigAssetPath))
        {
            Debug.LogWarning(
                "CutSceneAI Studio Bridge: configuration not found at " + ConfigAssetPath);
            return;
        }

        try
        {
            _config = JsonUtility.FromJson<Config>(File.ReadAllText(ConfigAssetPath));
            if (_config == null
                || string.IsNullOrWhiteSpace(_config.project_id)
                || string.IsNullOrWhiteSpace(_config.backend_url))
            {
                throw new InvalidOperationException("Bridge configuration is incomplete.");
            }

            _config.backend_url = _config.backend_url.TrimEnd('/');
            _agentId = Environment.MachineName + ":unity:" + _config.project_id;
            _nextHeartbeat = 0;
            _nextPoll = 0;
            Debug.Log(
                "CutSceneAI Studio Bridge ready for project "
                + _config.project_id
                + " at "
                + _config.backend_url);
        }
        catch (Exception exc)
        {
            _config = null;
            Debug.LogError("CutSceneAI Studio Bridge configuration error: " + exc.Message);
        }
    }

    [MenuItem("CutSceneAI/Studio Bridge/Send Heartbeat Now")]
    private static void SendHeartbeatMenu()
    {
        if (_config == null)
            ReloadConfig();
        if (_config != null && !_requestInFlight)
            SendHeartbeat();
    }

    private static void Tick()
    {
        if (_config == null || _requestInFlight)
            return;

        double now = EditorApplication.timeSinceStartup;
        if (now >= _nextHeartbeat)
        {
            SendHeartbeat();
            return;
        }

        if (now >= _nextPoll)
            PollCommand();
    }

    private static void SendHeartbeat()
    {
        Heartbeat heartbeat = BuildHeartbeat();
        string url =
            _config.backend_url
            + "/api/v1/studio/projects/"
            + Uri.EscapeDataString(_config.project_id)
            + "/bridge/heartbeat";

        SendJson(
            "POST",
            url,
            JsonUtility.ToJson(heartbeat),
            request =>
            {
                _nextHeartbeat =
                    EditorApplication.timeSinceStartup + HeartbeatIntervalSeconds;
                _nextPoll = EditorApplication.timeSinceStartup + PollIntervalSeconds;
                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning(
                        "CutSceneAI Studio Bridge heartbeat failed: " + request.error);
                }
            });
    }

    private static void PollCommand()
    {
        string url =
            _config.backend_url
            + "/api/v1/studio/projects/"
            + Uri.EscapeDataString(_config.project_id)
            + "/bridge/poll?agent_id="
            + Uri.EscapeDataString(_agentId);

        SendJson(
            "GET",
            url,
            null,
            request =>
            {
                _nextPoll = EditorApplication.timeSinceStartup + PollIntervalSeconds;
                if (request.result != UnityWebRequest.Result.Success)
                    return;

                PollResponse response = JsonUtility.FromJson<PollResponse>(
                    request.downloadHandler.text);
                if (response != null && response.command != null)
                    ExecuteCommand(response.command);
            });
    }

    private static void ExecuteCommand(BridgeCommand command)
    {
        bool succeeded = true;
        string error = null;
        CommandResult result;

        try
        {
            switch (command.command)
            {
                case "refresh_manifest":
                    _nextHeartbeat = 0;
                    result = BuildReadback("Manifest refresh scheduled.");
                    break;
                case "focus_preview":
                    result = FocusPreview();
                    break;
                case "play_preview":
                    EditorApplication.isPlaying = true;
                    result = BuildReadback("Unity Play Mode requested.");
                    break;
                case "stop_preview":
                    EditorApplication.isPlaying = false;
                    result = BuildReadback("Unity Play Mode stop requested.");
                    break;
                case "save":
                    AssetDatabase.SaveAssets();
                    EditorSceneManager.SaveOpenScenes();
                    result = BuildReadback("Open scenes and assets saved.");
                    break;
                case "readback":
                    result = BuildReadback("Unity editor readback captured.");
                    break;
                default:
                    throw new InvalidOperationException(
                        "Unsupported bridge command: " + command.command);
            }
        }
        catch (Exception exc)
        {
            succeeded = false;
            error = exc.ToString();
            result = BuildReadback("Command failed.");
        }

        CompleteRequest completion = new CompleteRequest
        {
            agent_id = _agentId,
            succeeded = succeeded,
            result = result,
            error = error,
        };
        string url =
            _config.backend_url
            + "/api/v1/studio/projects/"
            + Uri.EscapeDataString(_config.project_id)
            + "/bridge/commands/"
            + Uri.EscapeDataString(command.command_id)
            + "/complete";

        if (_requestInFlight)
        {
            EditorApplication.delayCall += () => CompleteCommand(url, completion);
        }
        else
        {
            CompleteCommand(url, completion);
        }
    }

    private static void CompleteCommand(string url, CompleteRequest completion)
    {
        if (_requestInFlight)
        {
            EditorApplication.delayCall += () => CompleteCommand(url, completion);
            return;
        }

        SendJson(
            "POST",
            url,
            JsonUtility.ToJson(completion),
            request =>
            {
                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning(
                        "CutSceneAI Studio Bridge command completion failed: "
                        + request.error);
                }
            });
    }

    private static CommandResult FocusPreview()
    {
        PlayableDirector director = UnityEngine.Object
            .FindObjectsByType<PlayableDirector>(FindObjectsSortMode.None)
            .FirstOrDefault(item => item.playableAsset is TimelineAsset);
        if (director == null)
            throw new InvalidOperationException(
                "No Timeline PlayableDirector exists in the active editor scene.");

        Selection.activeGameObject = director.gameObject;
        EditorGUIUtility.PingObject(director.gameObject);
        SceneView.lastActiveSceneView?.FrameSelected();
        return BuildReadback("Timeline director selected in the editor.");
    }

    private static CommandResult BuildReadback(string message)
    {
        Scene scene = SceneManager.GetActiveScene();
        GameObject[] roots = scene.IsValid() ? scene.GetRootGameObjects() : Array.Empty<GameObject>();
        PlayableDirector[] directors = UnityEngine.Object.FindObjectsByType<PlayableDirector>(
            FindObjectsSortMode.None);
        return new CommandResult
        {
            current_scene = scene.IsValid() ? scene.path : string.Empty,
            is_playing = EditorApplication.isPlaying,
            scene_actor_count = roots.Length,
            playable_director_count = directors.Length,
            selected_object = Selection.activeObject == null
                ? string.Empty
                : Selection.activeObject.name,
            message = message,
        };
    }

    private static Heartbeat BuildHeartbeat()
    {
        Scene scene = SceneManager.GetActiveScene();
        List<AssetRecord> assets = new List<AssetRecord>();

        if (scene.IsValid())
        {
            foreach (GameObject root in scene.GetRootGameObjects().Take(200))
            {
                assets.Add(RecordForObject(
                    root,
                    "scene_actor",
                    root.name,
                    GlobalObjectId.GetGlobalObjectIdSlow(root).ToString(),
                    scene.path,
                    true));
            }
        }

        string[] prefabGuids = AssetDatabase.FindAssets("t:Prefab").Take(300).ToArray();
        foreach (string guid in prefabGuids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (prefab == null)
                continue;
            assets.Add(RecordForObject(
                prefab,
                "prefab",
                prefab.name,
                path,
                path,
                true));
        }

        int fps = 24;
        PlayableDirector director = UnityEngine.Object
            .FindObjectsByType<PlayableDirector>(FindObjectsSortMode.None)
            .FirstOrDefault(item => item.playableAsset is TimelineAsset);
        if (director != null && director.playableAsset is TimelineAsset timeline)
            fps = Math.Max(1, (int)Math.Round(timeline.editorSettings.frameRate));

        return new Heartbeat
        {
            agent_id = _agentId,
            engine_version = Application.unityVersion,
            adapter_version = BridgeVersion,
            current_scene = scene.IsValid() ? scene.path : null,
            fps = fps,
            capabilities = new[]
            {
                "bridge:v0.1",
                "verified-project-objects",
                "humanoid-scan",
                "blendshape-scan",
                "timeline",
                "editor-command-queue",
                "readback",
            },
            assets = assets.ToArray(),
            warnings = Array.Empty<string>(),
        };
    }

    private static AssetRecord RecordForObject(
        GameObject root,
        string kind,
        string displayName,
        string engineRef,
        string relativePath,
        bool verified)
    {
        Animator animator = root.GetComponentInChildren<Animator>(true);
        bool humanoid =
            animator != null
            && animator.avatar != null
            && animator.avatar.isValid
            && animator.avatar.isHuman;
        int mappedBones = 0;
        if (humanoid)
        {
            for (int index = 0; index < (int)HumanBodyBones.LastBone; index++)
            {
                if (animator.GetBoneTransform((HumanBodyBones)index) != null)
                    mappedBones++;
            }
        }

        SkinnedMeshRenderer face = root
            .GetComponentsInChildren<SkinnedMeshRenderer>(true)
            .OrderByDescending(item => item.sharedMesh == null ? 0 : item.sharedMesh.blendShapeCount)
            .FirstOrDefault();
        int blendshapes =
            face == null || face.sharedMesh == null ? 0 : face.sharedMesh.blendShapeCount;

        return new AssetRecord
        {
            object_id = engineRef,
            kind = kind,
            display_name = displayName,
            engine_ref = engineRef,
            relative_path = relativePath ?? string.Empty,
            verified = verified,
            metadata = new AssetMetadata
            {
                asset_type = kind,
                animator_path = animator == null ? string.Empty : RelativePath(root.transform, animator.transform),
                humanoid = humanoid,
                humanoid_bone_count = mappedBones,
                blendshape_count = blendshapes,
                facial_renderer_path = face == null ? string.Empty : RelativePath(root.transform, face.transform),
                class_name = root.GetType().Name,
            },
        };
    }

    private static string RelativePath(Transform root, Transform target)
    {
        if (target == null || target == root)
            return string.Empty;
        List<string> parts = new List<string>();
        Transform current = target;
        while (current != null && current != root)
        {
            parts.Add(current.name);
            current = current.parent;
        }
        parts.Reverse();
        return string.Join("/", parts);
    }

    private static void SendJson(
        string method,
        string url,
        string body,
        Action<UnityWebRequest> completed)
    {
        _requestInFlight = true;
        UnityWebRequest request = new UnityWebRequest(url, method);
        request.downloadHandler = new DownloadHandlerBuffer();
        if (body != null)
        {
            request.uploadHandler = new UploadHandlerRaw(
                System.Text.Encoding.UTF8.GetBytes(body));
            request.SetRequestHeader("Content-Type", "application/json");
        }

        UnityWebRequestAsyncOperation operation = request.SendWebRequest();
        operation.completed += _ =>
        {
            try
            {
                completed(request);
            }
            catch (Exception exc)
            {
                Debug.LogError("CutSceneAI Studio Bridge request callback failed: " + exc);
            }
            finally
            {
                request.Dispose();
                _requestInFlight = false;
            }
        };
    }
}
