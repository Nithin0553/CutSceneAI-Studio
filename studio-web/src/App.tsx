import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BadgeCheck,
  Blocks,
  Box,
  Braces,
  Check,
  ChevronRight,
  CircleAlert,
  CircleDot,
  Clapperboard,
  Download,
  FileJson2,
  Film,
  FlaskConical,
  FolderKanban,
  Gauge,
  HardDrive,
  Link2,
  LoaderCircle,
  MonitorPlay,
  PackageCheck,
  Play,
  RefreshCw,
  ScanSearch,
  Server,
  Settings2,
  Sparkles,
  Unplug,
  Waypoints,
  Wrench,
} from "lucide-react";
import "./styles.css";

type Json = Record<string, any>;
type View = "studio" | "projects" | "evidence";
type Engine = "unity" | "unreal";
type Busy =
  | ""
  | "connect"
  | "scan"
  | "generate"
  | "bindings"
  | "performance"
  | "realization"
  | "export"
  | "edit"
  | "bridge";

const DEFAULT_PROMPT =
  "A guard walks through an abandoned hallway, hears a noise, stops, turns toward a door, and quietly asks who is there.";

async function apiJson(path: string, init?: RequestInit) {
  const response = await fetch(path, init);
  const raw = await response.text();
  let body: any = raw;
  try {
    body = raw ? JSON.parse(raw) : null;
  } catch {
    // Text responses are returned as-is.
  }
  if (!response.ok) {
    const message =
      body?.detail ||
      body?.message ||
      body?.code ||
      "Request failed with HTTP " + response.status;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return body;
}

function postJson(path: string, body: unknown) {
  return apiJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function Pill({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  children: React.ReactNode;
}) {
  return <span className={"pill pill-" + tone}>{children}</span>;
}

function Step({
  index,
  title,
  detail,
  state,
}: {
  index: number;
  title: string;
  detail: string;
  state: "done" | "active" | "pending" | "blocked";
}) {
  return (
    <div className={"flow-step flow-" + state}>
      <div className="flow-index">
        {state === "done" ? <Check size={13} /> : String(index).padStart(2, "0")}
      </div>
      <div className="flow-copy">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </div>
  );
}

function App() {
  const [view, setView] = useState<View>("studio");
  const [health, setHealth] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [busy, setBusy] = useState<Busy>("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [capabilities, setCapabilities] = useState<Json[]>([]);
  const [research, setResearch] = useState<Json | null>(null);
  const [projects, setProjects] = useState<Json[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");

  const [connectEngine, setConnectEngine] = useState<Engine>("unity");
  const [connectName, setConnectName] = useState("");
  const [connectPath, setConnectPath] = useState("");
  const [engineExecutable, setEngineExecutable] = useState("");

  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [cir, setCir] = useState<Json | null>(null);
  const [validation, setValidation] = useState<Json | null>(null);
  const [storyboard, setStoryboard] = useState("");
  const [directorMeta, setDirectorMeta] = useState<Json | null>(null);

  const [bindingOptions, setBindingOptions] = useState<Json | null>(null);
  const [bindings, setBindings] = useState<Record<string, string>>({});
  const [bindingManifest, setBindingManifest] = useState<Json | null>(null);

  const [performancePlan, setPerformancePlan] = useState<Json | null>(null);
  const [performanceReadiness, setPerformanceReadiness] = useState<Json | null>(null);
  const [performanceRun, setPerformanceRun] = useState<Json | null>(null);
  const [realization, setRealization] = useState<Json | null>(null);
  const [editInstruction, setEditInstruction] = useState("");
  const [cirHistory, setCirHistory] = useState<Json[]>([]);
  const [currentRevisionId, setCurrentRevisionId] = useState("");
  const [revisionCount, setRevisionCount] = useState(0);
  const [bridgeCommands, setBridgeCommands] = useState<Json[]>([]);
  const [bridgeActivity, setBridgeActivity] = useState<Json | null>(null);

  const selectedProject = useMemo(
    () => projects.find((item) => item.project_id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );

  const selectedBindings = useMemo(
    () =>
      Object.entries(bindings)
        .filter(([, value]) => Boolean(value))
        .map(([cir_id, project_object_id]) => ({ cir_id, project_object_id })),
    [bindings],
  );

  const requiredRoles = useMemo(
    () => (bindingOptions?.roles || []).filter((item: Json) => item.required),
    [bindingOptions],
  );

  const requiredBound = useMemo(
    () =>
      requiredRoles.length > 0 &&
      requiredRoles.every((item: Json) => Boolean(bindings[item.cir_id])),
    [requiredRoles, bindings],
  );

  const missingCapabilities = useMemo(
    () => capabilities.filter((item) => item.blocking),
    [capabilities],
  );

  useEffect(() => {
    refreshBootstrap();

    const timer = window.setInterval(() => {
      apiJson("/api/v1/studio/projects")
        .then((value) => setProjects(value || []))
        .catch(() => {
          // Main health state is handled by refreshBootstrap and explicit actions.
        });
    }, 5000);

    return () => window.clearInterval(timer);
  }, []);

  async function refreshBootstrap() {
    try {
      const [healthResult, capabilityResult, projectResult, researchResult] =
        await Promise.all([
          apiJson("/health"),
          apiJson("/api/v1/studio/capabilities"),
          apiJson("/api/v1/studio/projects"),
          apiJson("/api/v1/research/s02"),
        ]);
      setHealth(healthResult.status === "ok" ? "online" : "offline");
      setCapabilities(capabilityResult.capabilities || []);
      setProjects(projectResult || []);
      setResearch(researchResult);
      apiJson("/api/v1/studio/performance/readiness")
        .then((value) => setPerformanceReadiness(value))
        .catch(() => setPerformanceReadiness(null));
      if (!selectedProjectId && projectResult?.length) {
        setSelectedProjectId(projectResult[0].project_id);
      }
    } catch (exc) {
      setHealth("offline");
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function persistCirRevision(
    nextCir: Json,
    source: "generation" | "edit" | "restore" | "import",
    instruction?: string,
    parentRevisionId?: string,
  ) {
    if (!selectedProjectId) return null;
    const revision = await postJson("/api/v1/studio/revisions", {
      project_id: selectedProjectId,
      project: nextCir,
      source,
      parent_revision_id: parentRevisionId || null,
      instruction: instruction || null,
    });
    setCurrentRevisionId(revision.revision_id);
    try {
      const revisions = await apiJson(
        "/api/v1/studio/projects/" + selectedProjectId + "/revisions",
      );
      setRevisionCount(revisions?.length || 0);
    } catch {
      // Revision creation already succeeded; count is informational.
    }
    return revision;
  }

  async function connectProject() {
    setBusy("connect");
    setError("");
    setNotice("");
    try {
      const record = await postJson("/api/v1/studio/projects/connect", {
        engine: connectEngine,
        project_path: connectPath,
        display_name: connectName || null,
        engine_executable: engineExecutable || null,
      });
      const nextProjects = [
        ...projects.filter((item) => item.project_id !== record.project_id),
        record,
      ];
      setProjects(nextProjects);
      setSelectedProjectId(record.project_id);
      setConnectName("");
      setNotice(
        "Project connected. Filesystem preflight completed; engine-native verification is shown separately.",
      );
      setView("studio");
      if (cir) {
        await loadBindingOptions(cir, record.project_id);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function scanSelectedProject() {
    if (!selectedProject) return;
    setBusy("scan");
    setError("");
    try {
      const record = await postJson(
        "/api/v1/studio/projects/" + selectedProject.project_id + "/scan",
        {},
      );
      setProjects((items) =>
        items.map((item) =>
          item.project_id === record.project_id ? record : item,
        ),
      );
      setNotice("Targeted project preflight refreshed.");
      if (cir) {
        await loadBindingOptions(cir, record.project_id);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function generateScene() {
    setBusy("generate");
    setError("");
    setNotice("");
    setCir(null);
    setValidation(null);
    setStoryboard("");
    setBindingOptions(null);
    setBindings({});
    setBindingManifest(null);
    setPerformancePlan(null);
    setPerformanceRun(null);
    setRealization(null);

    try {
      const director = await postJson("/api/v1/director/generate", { prompt });
      const nextCir = director.project;

      const [validated, storyboardResponse] = await Promise.all([
        postJson("/api/v1/cir/validate", nextCir),
        fetch("/api/v1/preview/storyboard.svg", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextCir),
        }),
      ]);

      if (!storyboardResponse.ok) {
        throw new Error(await storyboardResponse.text());
      }

      setCir(nextCir);
      setValidation(validated);
      setStoryboard(await storyboardResponse.text());
      setDirectorMeta({
        provider: director.provider,
        model: director.model,
        request_id: director.request_id,
      });

      if (selectedProjectId) {
        await persistCirRevision(nextCir, "generation");
        await loadBindingOptions(nextCir, selectedProjectId);
      }

      setNotice(
        "CIR generated, validated, and stored as an immutable revision. Review project bindings before realization.",
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function editScene() {
    if (!cir || editInstruction.trim().length < 5) return;
    setBusy("edit");
    setError("");
    setNotice("");
    try {
      const director = await postJson("/api/v1/director/edit", {
        project: cir,
        instruction: editInstruction.trim(),
      });
      const nextCir = director.project;
      const [validated, storyboardResponse] = await Promise.all([
        postJson("/api/v1/cir/validate", nextCir),
        fetch("/api/v1/preview/storyboard.svg", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextCir),
        }),
      ]);
      if (!storyboardResponse.ok) {
        throw new Error(await storyboardResponse.text());
      }

      setCirHistory((items) => [...items, cir]);
      setCir(nextCir);
      setValidation(validated);
      setStoryboard(await storyboardResponse.text());
      setDirectorMeta({
        provider: director.provider,
        model: director.model,
        request_id: director.request_id,
      });
      setEditInstruction("");
      setBindingManifest(null);
      setPerformancePlan(null);
      setPerformanceRun(null);
      setRealization(null);
      if (selectedProjectId) {
        let parentRevisionId = currentRevisionId;
        if (!parentRevisionId) {
          const imported = await persistCirRevision(cir, "import");
          parentRevisionId = imported?.revision_id || "";
        }
        await persistCirRevision(
          nextCir,
          "edit",
          editInstruction.trim(),
          parentRevisionId,
        );
        await loadBindingOptions(nextCir, selectedProjectId);
      }
      setNotice(
        "CIR revision validated and persisted. Downstream bindings and generated performance were invalidated for safe regeneration.",
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function undoLastEdit() {
    if (!selectedProjectId || !currentRevisionId) return;
    setBusy("edit");
    setError("");
    try {
      const current = await apiJson(
        "/api/v1/studio/projects/" +
          selectedProjectId +
          "/revisions/" +
          currentRevisionId,
      );
      if (!current.parent_revision_id) {
        setNotice("This CIR revision has no parent revision to restore.");
        return;
      }
      const previousRevision = await apiJson(
        "/api/v1/studio/projects/" +
          selectedProjectId +
          "/revisions/" +
          current.parent_revision_id,
      );
      const previous = previousRevision.project;
      const [validated, storyboardResponse] = await Promise.all([
        postJson("/api/v1/cir/validate", previous),
        fetch("/api/v1/preview/storyboard.svg", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(previous),
        }),
      ]);
      if (!storyboardResponse.ok) {
        throw new Error(await storyboardResponse.text());
      }
      setCir(previous);
      setValidation(validated);
      setStoryboard(await storyboardResponse.text());
      setCurrentRevisionId(previousRevision.revision_id);
      setCirHistory((items) => items.slice(0, -1));
      setBindingManifest(null);
      setPerformancePlan(null);
      setPerformanceRun(null);
      setRealization(null);
      await loadBindingOptions(previous, selectedProjectId);
      setNotice("Previous persisted CIR revision restored.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function installEngineBridge() {
    if (!selectedProject) return;
    setBusy("bridge");
    setError("");
    try {
      const result = await postJson(
        "/api/v1/studio/projects/" +
          selectedProject.project_id +
          "/bridge/install",
        {},
      );
      setNotice(result.message);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function refreshBridgeCommands() {
    if (!selectedProject) return;
    try {
      const result = await apiJson(
        "/api/v1/studio/projects/" +
          selectedProject.project_id +
          "/bridge/commands",
      );
      setBridgeCommands(result || []);
    } catch {
      setBridgeCommands([]);
    }
  }

  async function waitForBridgeCommand(
    projectId: string,
    commandId: string,
    timeoutMs = 90000,
  ) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const command = await apiJson(
        "/api/v1/studio/projects/" +
          projectId +
          "/bridge/commands/" +
          commandId,
      );
      setBridgeCommands((items) => [
        command,
        ...items.filter((item) => item.command_id !== command.command_id),
      ]);
      setBridgeActivity(command);
      if (command.status === "succeeded") {
        await refreshBootstrap();
        return command;
      }
      if (command.status === "failed") {
        throw new Error(command.error || "Engine command failed.");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    }
    throw new Error(
      "Engine command did not complete within 90 seconds. It remains preserved in the bridge queue.",
    );
  }

  async function sendBridgeCommand(command: string) {
    if (!selectedProject) {
      setError("Select a target project before sending an engine command.");
      return;
    }

    setBusy("bridge");
    setError("");
    setBridgeActivity({
      command,
      status: "checking",
      message: "Checking the latest editor heartbeat…",
    });

    try {
      const liveProjects = await apiJson("/api/v1/studio/projects");
      setProjects(liveProjects || []);
      const liveProject = (liveProjects || []).find(
        (item: Json) => item.project_id === selectedProject.project_id,
      );
      if (!liveProject?.manifest?.bridge_connected) {
        throw new Error(
          "Unity/Unreal bridge is not live right now. Keep the editor open and wait for a fresh heartbeat.",
        );
      }

      const queued = await postJson(
        "/api/v1/studio/projects/" +
          selectedProject.project_id +
          "/bridge/commands",
        { command, payload: {} },
      );
      setBridgeActivity({
        ...queued,
        message: "Command queued. Waiting for the editor to execute it…",
      });
      setNotice(
        "Engine command queued: " + queued.command + " (" + queued.command_id + ")",
      );

      const completed = await waitForBridgeCommand(
        selectedProject.project_id,
        queued.command_id,
      );
      setBridgeActivity({
        ...completed,
        message:
          completed.result?.message || "Editor readback returned successfully.",
      });
      setNotice(
        "Engine command completed: " +
          completed.command +
          ". " +
          (completed.result?.message || "Editor readback returned successfully."),
      );
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      setBridgeActivity({
        command,
        status: "failed",
        message,
      });
      setError(message);
    } finally {
      setBusy("");
    }
  }

  async function loadBindingOptions(nextCir = cir, projectId = selectedProjectId) {
    if (!nextCir || !projectId) return;
    setBusy("bindings");
    try {
      const result = await postJson("/api/v1/studio/bindings/options", {
        project_id: projectId,
        project: nextCir,
      });
      setBindingOptions(result);

      const suggested: Record<string, string> = {};
      for (const role of result.roles || []) {
        const candidate = role.candidates?.[0];
        if (candidate && candidate.score > 0) {
          suggested[role.cir_id] = candidate.project_object_id;
        }
      }
      setBindings(suggested);
      setBindingManifest(null);
    } finally {
      setBusy("");
    }
  }

  async function validateBindings() {
    if (!cir || !selectedProject) return;
    setBusy("bindings");
    setError("");
    try {
      const result = await postJson("/api/v1/studio/bindings/validate", {
        project_id: selectedProject.project_id,
        project: cir,
        bindings: selectedBindings,
      });
      setBindingManifest(result);
      if (result.valid) {
        setNotice("Required character bindings are complete.");
      } else {
        setNotice("Some required character roles still need a project binding.");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function preparePerformance() {
    if (!cir) return;
    setBusy("performance");
    setError("");
    try {
      const [plan, readiness] = await Promise.all([
        postJson("/api/v1/studio/performance/plan", {
          project: cir,
          experiment_seed: 20260812,
        }),
        apiJson("/api/v1/studio/performance/readiness"),
      ]);
      setPerformancePlan(plan);
      setPerformanceReadiness(readiness);
      setPerformanceRun(null);
      setNotice(
        readiness.ready
          ? "Generation plan is ready and all required providers are configured."
          : "Generation plan is ready, but at least one required provider still needs configuration.",
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function generatePerformance() {
    if (!cir || !performanceReadiness?.ready) return;
    setBusy("performance");
    setError("");
    setNotice("Generating and packaging performance evidence…");
    try {
      const run = await postJson("/api/v1/studio/performance/generate", {
        project: cir,
        experiment_seed: 20260812,
        voices: {},
      });
      setPerformanceRun(run);
      if (run.status === "succeeded") {
        setNotice(
          "Generated Performance Package completed and its bundle hash was recorded.",
        );
      } else {
        setError(run.error || "Generated performance failed.");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function downloadPerformanceBundle() {
    if (!performanceRun?.run_id || performanceRun.status !== "succeeded") return;
    setBusy("export");
    setError("");
    try {
      const response = await fetch(
        "/api/v1/studio/performance/runs/" +
          performanceRun.run_id +
          "/bundle",
      );
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download =
        "cutsceneai-performance-" + performanceRun.run_id + ".zip";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function compileRealization() {
    if (!cir || !selectedProject) return;
    setBusy("realization");
    setError("");
    try {
      const result = await postJson("/api/v1/studio/realization/plan", {
        project_id: selectedProject.project_id,
        project: cir,
        bindings: selectedBindings,
      });
      setRealization(result);
      setNotice(
        result.ready
          ? "Bound engine-native adapter plan compiled."
          : "Realization is blocked by unresolved required bindings.",
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function downloadImporter() {
    if (!cir || !selectedProject) return;
    setBusy("export");
    setError("");
    try {
      const response = await fetch("/api/v1/studio/realization/importer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: selectedProject.project_id,
          project: cir,
          bindings: selectedBindings,
        }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download =
        selectedProject.engine === "unity"
          ? "CutSceneAI-Unity-Importer.cs"
          : "cutsceneai-unreal-import.py";
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(
        "Bound importer generated for inspection or manual execution.",
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  async function executeRealizationInEngine() {
    if (
      !cir ||
      !selectedProject ||
      !realizationReady ||
      performanceRun?.status !== "succeeded"
    ) {
      return;
    }
    setBusy("bridge");
    setError("");
    try {
      const queued = await postJson(
        "/api/v1/studio/performance/runs/" +
          performanceRun.run_id +
          "/realize",
        {
          project_id: selectedProject.project_id,
          project: cir,
          bindings: selectedBindings,
        },
      );
      const omissions = queued.payload?.omitted_facial_actor_binding_ids || [];
      setNotice(
        "Verified Generated Performance Package staged and queued for native " +
          selectedProject.engine +
          " realization: " +
          queued.command_id +
          (omissions.length
            ? ". Facial tracks omitted for target-capability-unavailable actors: " +
              omissions.join(", ")
            : ". Full requested facial capability is available."),
      );
      const completed = await waitForBridgeCommand(
        selectedProject.project_id,
        queued.command_id,
        120000,
      );
      setNotice(
        "Native " +
          selectedProject.engine +
          " realization completed. " +
          (completed.result?.message || "The editor returned successful readback.") +
          (omissions.length
            ? " Declared facial omissions: " + omissions.join(", ") + "."
            : ""),
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy("");
    }
  }

  function downloadCir() {
    if (!cir) return;
    const blob = new Blob([JSON.stringify(cir, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = (cir.id || "cutsceneai-project") + ".cir.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function resetGeneration() {
    setCir(null);
    setValidation(null);
    setStoryboard("");
    setDirectorMeta(null);
    setBindingOptions(null);
    setBindings({});
    setBindingManifest(null);
    setPerformancePlan(null);
    setPerformanceRun(null);
    setRealization(null);
    setEditInstruction("");
    setCirHistory([]);
    setCurrentRevisionId("");
    setRevisionCount(0);
    setBridgeCommands([]);
    setError("");
    setNotice("");
  }

  const projectConnected = Boolean(selectedProject);
  const cirReady = Boolean(cir && validation);
  const bindingsReady = Boolean(bindingManifest?.valid || requiredBound);
  const performancePlanReady = Boolean(performancePlan);
  const performanceGenerated = performanceRun?.status === "succeeded";
  const realizationReady = Boolean(realization?.ready);

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand brand-button" onClick={() => setView("studio")}>
          <span className="brand-mark">
            <Clapperboard size={20} />
          </span>
          <span className="brand-copy">
            <strong>CutSceneAI</strong>
            <small>Studio V3</small>
          </span>
        </button>

        <nav className="nav-tabs" aria-label="Primary">
          <button
            className={view === "studio" ? "nav-active" : ""}
            onClick={() => setView("studio")}
          >
            <Sparkles size={15} /> Studio
          </button>
          <button
            className={view === "projects" ? "nav-active" : ""}
            onClick={() => setView("projects")}
          >
            <FolderKanban size={15} /> Projects
          </button>
          <button
            className={view === "evidence" ? "nav-active" : ""}
            onClick={() => setView("evidence")}
          >
            <FlaskConical size={15} /> Evidence
          </button>
        </nav>

        <div className={"server-state state-" + health}>
          <Server size={14} />
          {health === "online"
            ? "Local API connected"
            : health === "checking"
              ? "Checking API"
              : "API offline"}
        </div>
      </header>

      {view === "studio" && (
        <main className="studio-layout">
          <aside className="flow-sidebar">
            <div className="sidebar-kicker">V3 WORKFLOW</div>
            <h2>Cutscene pipeline</h2>
            <p>
              Cinematic intent stays engine-independent until project binding and
              realization.
            </p>

            <div className="flow-list">
              <Step
                index={1}
                title="Connect project"
                detail="Unity or Unreal"
                state={projectConnected ? "done" : "active"}
              />
              <Step
                index={2}
                title="Create CIR"
                detail="Natural language → validated intent"
                state={cirReady ? "done" : projectConnected ? "active" : "pending"}
              />
              <Step
                index={3}
                title="Bind roles"
                detail="CIR roles → project objects"
                state={
                  bindingsReady
                    ? "done"
                    : cirReady
                      ? "active"
                      : "pending"
                }
              />
              <Step
                index={4}
                title="Plan performance"
                detail="Body + face + camera requests"
                state={
                  performanceGenerated
                    ? "done"
                    : bindingsReady
                      ? "active"
                      : "pending"
                }
              />
              <Step
                index={5}
                title="Realize"
                detail="Compile engine-native timeline"
                state={
                  realizationReady
                    ? "done"
                    : performanceGenerated
                      ? "active"
                      : "pending"
                }
              />
              <Step
                index={6}
                title="Preview in engine"
                detail="Authoritative interactive preview"
                state={
                  realizationReady && selectedProject?.manifest?.bridge_connected
                    ? "active"
                    : realizationReady
                      ? "blocked"
                      : "pending"
                }
              />
              <Step
                index={7}
                title="Edit + verify"
                detail="CIR patch, readback, parity"
                state={cirHistory.length > 0 ? "active" : cirReady ? "active" : "pending"}
              />
            </div>

            <button className="text-button" onClick={resetGeneration}>
              <RefreshCw size={14} /> Start a new generation
            </button>
          </aside>

          <section className="studio-main">
            <div className="page-heading">
              <div>
                <span className="eyebrow">STUDIO</span>
                <h1>Create a portable cutscene</h1>
                <p>
                  Connect a target project, describe cinematic intent, bind roles,
                  then compile the same validated representation toward Unity or
                  Unreal.
                </p>
              </div>
              <Pill tone={selectedProject?.manifest?.bridge_connected ? "success" : "warning"}>
                {selectedProject?.manifest?.bridge_connected ? (
                  <><Link2 size={13} /> Engine bridge connected</>
                ) : (
                  <><Unplug size={13} /> Engine bridge pending</>
                )}
              </Pill>
            </div>

            {error && (
              <div className="banner banner-error">
                <CircleAlert size={17} />
                <span>{error}</span>
              </div>
            )}
            {notice && (
              <div className="banner banner-info">
                <CircleDot size={17} />
                <span>{notice}</span>
              </div>
            )}

            <section className="stage-card">
              <div className="stage-header">
                <div className="stage-number">01</div>
                <div>
                  <h2>Target project</h2>
                  <p>
                    Select the project CutSceneAI will bind and compile against.
                  </p>
                </div>
                <button className="quiet-button" onClick={() => setView("projects")}>
                  Manage projects
                </button>
              </div>

              {selectedProject ? (
                <div className="connected-project">
                  <div className={"engine-logo " + selectedProject.engine}>
                    {selectedProject.engine === "unity" ? "◆" : "U"}
                  </div>
                  <div className="project-summary">
                    <strong>{selectedProject.display_name}</strong>
                    <span>{selectedProject.project_path}</span>
                    <div className="inline-meta">
                      <Pill tone="info">{selectedProject.engine}</Pill>
                      <span>
                        {selectedProject.manifest.engine_version || "version unknown"}
                      </span>
                      <span>
                        {selectedProject.manifest.assets?.length || 0} discovered objects
                      </span>
                    </div>
                  </div>
                  <select
                    className="compact-select"
                    value={selectedProjectId}
                    onChange={(event) => {
                      setSelectedProjectId(event.target.value);
                      if (cir) {
                        loadBindingOptions(cir, event.target.value);
                      }
                    }}
                  >
                    {projects.map((item) => (
                      <option key={item.project_id} value={item.project_id}>
                        {item.display_name}
                      </option>
                    ))}
                  </select>
                  <div className="project-action-stack">
                    <button
                      className="secondary-button"
                      onClick={scanSelectedProject}
                      disabled={busy === "scan"}
                    >
                      {busy === "scan" ? (
                        <LoaderCircle className="spin" size={15} />
                      ) : (
                        <ScanSearch size={15} />
                      )}
                      Refresh scan
                    </button>
                    <button
                      className="secondary-button"
                      onClick={installEngineBridge}
                      disabled={busy === "bridge"}
                    >
                      {busy === "bridge" ? (
                        <LoaderCircle className="spin" size={15} />
                      ) : (
                        <Link2 size={15} />
                      )}
                      Install bridge
                    </button>
                  </div>
                </div>
              ) : (
                <div className="empty-inline">
                  <HardDrive size={20} />
                  <div>
                    <strong>No project connected</strong>
                    <span>
                      Add a Unity or Unreal project before generating a final
                      engine-bound result.
                    </span>
                  </div>
                  <button
                    className="primary-button"
                    onClick={() => setView("projects")}
                  >
                    Connect project
                  </button>
                </div>
              )}

              {selectedProject?.manifest?.warnings?.length > 0 && (
                <div className="warning-stack">
                  {selectedProject?.manifest?.warnings.slice(0, 2).map((warning: string) => (
                    <div className="mini-warning" key={warning}>
                      <CircleAlert size={14} />
                      <span>{warning}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="stage-card">
              <div className="stage-header">
                <div className="stage-number">02</div>
                <div>
                  <h2>Describe the scene</h2>
                  <p>
                    The Director creates semantic roles, beats, actions, dialogue,
                    emotion, timing and camera intent.
                  </p>
                </div>
                {validation && <Pill tone="success"><BadgeCheck size={13} /> CIR valid</Pill>}
              </div>

              <textarea
                className="prompt-box"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Describe the scene, performances, dialogue, mood and cinematic intent..."
                minLength={20}
                maxLength={8000}
              />
              <div className="prompt-actions">
                <span>{prompt.length} / 8000</span>
                <button
                  className="primary-button"
                  onClick={generateScene}
                  disabled={
                    busy === "generate" ||
                    prompt.trim().length < 20 ||
                    !projectConnected
                  }
                >
                  {busy === "generate" ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Sparkles size={16} />
                  )}
                  Generate CIR
                </button>
              </div>

              {!projectConnected && (
                <div className="gate-note">
                  <Link2 size={16} />
                  <div>
                    <strong>Connect a target project first</strong>
                    <span>
                      V3 begins with project connection and capability discovery so
                      generated roles can be resolved against the selected Unity or
                      Unreal project.
                    </span>
                  </div>
                </div>
              )}

              {directorMeta && (
                <div className="meta-line">
                  <span>Provider <b>{directorMeta.provider}</b></span>
                  <span>Model <b>{directorMeta.model}</b></span>
                  {directorMeta.request_id && (
                    <span>Request <b>{String(directorMeta.request_id).slice(0, 12)}</b></span>
                  )}
                </div>
              )}

              {cirReady && (
                <div className="cir-result">
                  <div className="cir-stats">
                    <div><span>Scenes</span><strong>{validation?.summary?.scene_count ?? 0}</strong></div>
                    <div><span>Beats</span><strong>{validation?.summary?.beat_count ?? 0}</strong></div>
                    <div><span>Shots</span><strong>{validation?.summary?.shot_count ?? 0}</strong></div>
                    <div><span>Schema</span><strong>{validation?.schema_version ?? "—"}</strong></div>
                  </div>
                  <button className="secondary-button" onClick={downloadCir}>
                    <Download size={15} /> CIR JSON
                  </button>
                </div>
              )}
            </section>

            {cirReady && (
              <section className="stage-card">
                <div className="stage-header">
                  <div className="stage-number">03</div>
                  <div>
                    <h2>Bind cinematic roles</h2>
                    <p>
                      Generic CIR identities stay separate from engine-specific
                      objects. Manual selection is the reliable baseline.
                    </p>
                  </div>
                  {bindingsReady && <Pill tone="success"><Link2 size={13} /> Required roles bound</Pill>}
                </div>

                {!selectedProject ? (
                  <div className="empty-inline">
                    <Unplug size={20} />
                    <div>
                      <strong>Connect a project to bind roles</strong>
                      <span>The CIR remains valid and engine-independent.</span>
                    </div>
                  </div>
                ) : busy === "bindings" && !bindingOptions ? (
                  <div className="loading-row">
                    <LoaderCircle className="spin" size={17} /> Discovering binding candidates
                  </div>
                ) : (
                  <div className="binding-table">
                    {(bindingOptions?.roles || []).map((role: Json) => (
                      <div className="binding-row" key={role.cir_id}>
                        <div className="role-info">
                          <span className="role-kind">{role.kind}</span>
                          <strong>{role.label}</strong>
                          <code>{role.cir_id}</code>
                          {role.description && <small>{role.description}</small>}
                        </div>
                        <ChevronRight size={15} />
                        <div className="binding-control">
                          <select
                            value={bindings[role.cir_id] || ""}
                            onChange={(event) => {
                              setBindings((value) => ({
                                ...value,
                                [role.cir_id]: event.target.value,
                              }));
                              setBindingManifest(null);
                              setRealization(null);
                            }}
                          >
                            <option value="">
                              {role.required ? "Select required object…" : "Leave unbound / select…"}
                            </option>
                            {(role.candidates || []).map((candidate: Json) => (
                              <option
                                key={candidate.project_object_id}
                                value={candidate.project_object_id}
                              >
                                {candidate.display_name +
                                  " · " +
                                  candidate.kind +
                                  (candidate.verified ? " · verified" : "")}
                              </option>
                            ))}
                          </select>
                          {bindings[role.cir_id] && (
                            <small>
                              {role.candidates.find(
                                (candidate: Json) =>
                                  candidate.project_object_id === bindings[role.cir_id],
                              )?.engine_ref || ""}
                            </small>
                          )}
                        </div>
                        <Pill tone={role.required ? "warning" : "neutral"}>
                          {role.required ? "Required" : "Optional"}
                        </Pill>
                      </div>
                    ))}
                  </div>
                )}

                {selectedProject && bindingOptions && (
                  <div className="stage-actions">
                    <button
                      className="secondary-button"
                      onClick={() => loadBindingOptions()}
                      disabled={busy === "bindings"}
                    >
                      <RefreshCw size={15} /> Refresh suggestions
                    </button>
                    <button
                      className="primary-button"
                      onClick={validateBindings}
                      disabled={busy === "bindings"}
                    >
                      <BadgeCheck size={15} /> Validate bindings
                    </button>
                  </div>
                )}
              </section>
            )}

            {cirReady && (
              <section className="stage-card">
                <div className="stage-header">
                  <div className="stage-number">04</div>
                  <div>
                    <h2>Generated performance plan</h2>
                    <p>
                      Compile exact body, facial and camera generation requests
                      before any engine-specific realization.
                    </p>
                  </div>
                  {performancePlanReady && <Pill tone="success"><PackageCheck size={13} /> Plan prepared</Pill>}
                </div>

                {performancePlan ? (
                  <>
                    <div className="modality-grid">
                      <div className="modality">
                        <Blocks size={18} />
                        <span>Body motion</span>
                        <strong>{performancePlan.body_requests?.length || 0} requests</strong>
                      </div>
                      <div className="modality">
                        <Activity size={18} />
                        <span>Facial</span>
                        <strong>{performancePlan.facial_requests?.length || 0} requests</strong>
                      </div>
                      <div className="modality">
                        <Film size={18} />
                        <span>Camera</span>
                        <strong>{performancePlan.camera_requests?.length || 0} requests</strong>
                      </div>
                      <div className="modality">
                        <Gauge size={18} />
                        <span>Timebase</span>
                        <strong>{performancePlan.fps} fps</strong>
                      </div>
                    </div>

                    <div className="provider-grid">
                      {(performanceReadiness?.providers || []).map((provider: Json) => (
                        <div className="provider-row" key={provider.modality}>
                          <div>
                            <strong>{provider.modality}</strong>
                            <span>{provider.provider} · {provider.model}</span>
                          </div>
                          <Pill
                            tone={
                              !provider.configured || provider.reachable === false
                                ? "danger"
                                : provider.reachable === true
                                  ? "success"
                                  : "info"
                            }
                          >
                            {!provider.configured
                              ? provider.reachable === false
                                ? "offline"
                                : "not configured"
                              : provider.reachable === true
                                ? provider.health_status || "ready"
                                : "configured"}
                          </Pill>
                        </div>
                      ))}
                    </div>

                    {performanceReadiness?.blocking_issues?.length > 0 && (
                      <div className="warning-stack">
                        {(performanceReadiness?.blocking_issues || []).map((item: string) => (
                          <div className="mini-warning" key={item}>
                            <CircleAlert size={14} />
                            <span>{item}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="stage-actions">
                      {performanceRun?.status === "succeeded" && (
                        <button
                          className="secondary-button"
                          onClick={downloadPerformanceBundle}
                          disabled={busy === "export"}
                        >
                          <Download size={15} /> Performance bundle
                        </button>
                      )}
                      <button
                        className="primary-button"
                        onClick={generatePerformance}
                        disabled={
                          busy === "performance" ||
                          !performanceReadiness?.ready ||
                          performanceRun?.status === "succeeded"
                        }
                      >
                        {busy === "performance" ? (
                          <LoaderCircle className="spin" size={15} />
                        ) : (
                          <Sparkles size={15} />
                        )}
                        {performanceRun?.status === "succeeded"
                          ? "Performance generated"
                          : "Generate performance"}
                      </button>
                    </div>

                    {performanceRun && (
                      <div className="run-evidence">
                        <div>
                          <span>Run</span>
                          <code>{performanceRun.run_id}</code>
                        </div>
                        <div>
                          <span>Status</span>
                          <strong>{performanceRun.status}</strong>
                        </div>
                        <div>
                          <span>Bundle SHA-256</span>
                          <code>{performanceRun.bundle_sha256 || "not produced"}</code>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="empty-inline">
                    <Waypoints size={20} />
                    <div>
                      <strong>No generation plan prepared yet</strong>
                      <span>
                        This step creates deterministic provider requests, hashes and
                        seeds before inference begins.
                      </span>
                    </div>
                    <button
                      className="primary-button"
                      onClick={preparePerformance}
                      disabled={busy === "performance" || !bindingsReady}
                    >
                      {busy === "performance" ? (
                        <LoaderCircle className="spin" size={15} />
                      ) : (
                        <Waypoints size={15} />
                      )}
                      Prepare performance
                    </button>
                  </div>
                )}
              </section>
            )}

            {cirReady && selectedProject && (
              <section className="stage-card">
                <div className="stage-header">
                  <div className="stage-number">05</div>
                  <div>
                    <h2>Native realization for {selectedProject.engine === "unity" ? "Unity" : "Unreal Engine"}</h2>
                    <p>
                      Compile the bound adapter plan, then realize the verified
                      Generated Performance Package as editable native engine assets.
                    </p>
                  </div>
                  {realizationReady && <Pill tone="success"><Braces size={13} /> Adapter plan ready</Pill>}
                </div>

                {realization?.blocking_issues?.length > 0 && (
                  <div className="warning-stack">
                    {realization?.blocking_issues.map((item: string) => (
                      <div className="mini-warning" key={item}>
                        <CircleAlert size={14} /> <span>{item}</span>
                      </div>
                    ))}
                  </div>
                )}

                {realizationReady ? (
                  <>
                    <div className="realization-summary">
                      <div>
                        <span>Engine</span>
                        <strong>{selectedProject.engine}</strong>
                      </div>
                      <div>
                        <span>Adapter warnings</span>
                        <strong>{realization?.warnings?.length || 0}</strong>
                      </div>
                      <div>
                        <span>Bridge</span>
                        <strong>
                          {selectedProject.manifest.bridge_connected
                            ? "connected"
                            : "not connected"}
                        </strong>
                      </div>
                    </div>
                    <div className="stage-actions">
                      <button
                        className="secondary-button"
                        onClick={downloadImporter}
                        disabled={busy === "export"}
                      >
                        <Download size={15} /> Download bound importer
                      </button>
                      <button
                        className="primary-button"
                        onClick={executeRealizationInEngine}
                        disabled={
                          busy === "bridge" ||
                          !selectedProject.manifest.bridge_connected ||
                          !performanceGenerated
                        }
                        title={
                          !selectedProject.manifest.bridge_connected
                            ? "Open the project and wait for the local bridge heartbeat"
                            : !performanceGenerated
                              ? "Generate a verified performance package first"
                              : "Stage and execute the verified native performance importer"
                        }
                      >
                        {busy === "bridge" ? (
                          <LoaderCircle className="spin" size={15} />
                        ) : (
                          <MonitorPlay size={15} />
                        )}
                        Build native performance
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="empty-inline">
                    <Braces size={20} />
                    <div>
                      <strong>Compile a bound adapter plan</strong>
                      <span>
                        Required character bindings must be complete. Optional
                        project objects may remain explicit warnings.
                      </span>
                    </div>
                    <button
                      className="primary-button"
                      onClick={compileRealization}
                      disabled={busy === "realization" || !bindingsReady}
                    >
                      {busy === "realization" ? (
                        <LoaderCircle className="spin" size={15} />
                      ) : (
                        <Braces size={15} />
                      )}
                      Compile realization
                    </button>
                  </div>
                )}
              </section>
            )}

            <section className="preview-grid">
              <div className="stage-card preview-card">
                <div className="stage-header compact">
                  <div>
                    <h2>Planning storyboard</h2>
                    <p>Useful before engine realization; not the authoritative 3D preview.</p>
                  </div>
                  <Film size={18} />
                </div>
                {storyboard ? (
                  <div
                    className="storyboard"
                    dangerouslySetInnerHTML={{ __html: storyboard }}
                  />
                ) : (
                  <div className="preview-empty">
                    <Play size={22} />
                    <span>Generate CIR to view the deterministic storyboard.</span>
                  </div>
                )}
              </div>

              <div className="stage-card preview-card authority-card">
                <div className="stage-header compact">
                  <div>
                    <h2>Authoritative preview</h2>
                    <p>Per V3, the interactive result belongs in the connected engine.</p>
                  </div>
                  <MonitorPlay size={18} />
                </div>
                <div className="authority-body">
                  <div className={"engine-logo large " + (selectedProject?.engine || "unity")}>
                    {selectedProject?.engine === "unreal" ? "U" : "◆"}
                  </div>
                  <strong>
                    {selectedProject?.engine === "unreal"
                      ? "Unreal Sequencer / editor viewport"
                      : "Unity Timeline / Game view"}
                  </strong>
                  <span>
                    {selectedProject?.manifest?.bridge_connected
                      ? "The local editor bridge is connected. Use these controls to focus, play, save and read back the authoritative engine state."
                      : "Install the local editor bridge, then open the project. The engine will heartbeat into Studio without exposing a remote control port."}
                  </span>
                  {bridgeActivity && (
                    <div className={"bridge-activity bridge-" + bridgeActivity.status}>
                      {busy === "bridge" &&
                      bridgeActivity.status !== "succeeded" &&
                      bridgeActivity.status !== "failed" ? (
                        <LoaderCircle className="spin" size={14} />
                      ) : bridgeActivity.status === "succeeded" ? (
                        <BadgeCheck size={14} />
                      ) : bridgeActivity.status === "failed" ? (
                        <CircleAlert size={14} />
                      ) : (
                        <CircleDot size={14} />
                      )}
                      <div>
                        <strong>
                          {String(bridgeActivity.command || "engine command").replaceAll(
                            "_",
                            " ",
                          )}
                          {" · "}
                          {bridgeActivity.status || "pending"}
                        </strong>
                        <span>
                          {bridgeActivity.message ||
                            bridgeActivity.result?.message ||
                            "Waiting for editor response…"}
                        </span>
                      </div>
                    </div>
                  )}
                  <div className="bridge-controls">
                    {!selectedProject?.manifest?.bridge_connected ? (
                      <button
                        className="secondary-button"
                        onClick={installEngineBridge}
                        disabled={!selectedProject || busy === "bridge"}
                      >
                        <Link2 size={15} /> Install local bridge
                      </button>
                    ) : (
                      <>
                        <button
                          className="secondary-button"
                          onClick={() => sendBridgeCommand("focus_preview")}
                          disabled={busy === "bridge"}
                        >
                          <MonitorPlay size={15} /> Focus
                        </button>
                        <button
                          className="secondary-button"
                          onClick={() => sendBridgeCommand("play_preview")}
                          disabled={busy === "bridge"}
                        >
                          <Play size={15} /> Play
                        </button>
                        <button
                          className="secondary-button"
                          onClick={() => sendBridgeCommand("readback")}
                          disabled={busy === "bridge"}
                        >
                          {busy === "bridge" &&
                          bridgeActivity?.command === "readback" ? (
                            <LoaderCircle className="spin" size={15} />
                          ) : (
                            <ScanSearch size={15} />
                          )}{" "}
                          Readback
                        </button>
                        <button
                          className="secondary-button"
                          onClick={() => sendBridgeCommand("save")}
                          disabled={busy === "bridge"}
                        >
                          <PackageCheck size={15} /> Save
                        </button>
                      </>
                    )}
                  </div>
                  {selectedProject?.manifest?.bridge_last_seen_utc && (
                    <small className="bridge-last-seen">
                      Last engine heartbeat:{" "}
                      {new Date(
                        selectedProject.manifest.bridge_last_seen_utc,
                      ).toLocaleTimeString()}
                    </small>
                  )}
                </div>
              </div>
            </section>

            {cirReady && (
              <section className="stage-card edit-stage">
                <div className="stage-header">
                  <div className="stage-number">07</div>
                  <div>
                    <h2>Revise with natural language</h2>
                    <p>
                      Each edit creates a new validated CIR revision and invalidates
                      downstream artifacts that may depend on changed semantics.
                    </p>
                  </div>
                  <Pill tone={revisionCount ? "info" : "neutral"}>
                    {revisionCount} persisted revision{revisionCount === 1 ? "" : "s"}
                  </Pill>
                </div>
                <textarea
                  className="edit-box"
                  value={editInstruction}
                  onChange={(event) => setEditInstruction(event.target.value)}
                  placeholder='Example: "Hold the final close-up two seconds longer and make the guard more hesitant."'
                  minLength={5}
                  maxLength={4000}
                />
                <div className="stage-actions">
                  <button
                    className="secondary-button"
                    onClick={undoLastEdit}
                    disabled={busy === "edit" || !currentRevisionId}
                  >
                    <RefreshCw size={15} /> Undo last CIR edit
                  </button>
                  <button
                    className="primary-button"
                    onClick={editScene}
                    disabled={
                      busy === "edit" || editInstruction.trim().length < 5
                    }
                  >
                    {busy === "edit" ? (
                      <LoaderCircle className="spin" size={15} />
                    ) : (
                      <Sparkles size={15} />
                    )}
                    Apply validated edit
                  </button>
                </div>
                <div className="gate-note">
                  <Wrench size={16} />
                  <div>
                    <strong>Dependency-safe behavior</strong>
                    <span>
                      Editing already preserves CIR validity and invalidates stale
                      bindings/performance/realization. Fine-grained dependency-local
                      regeneration will replace this conservative full downstream
                      invalidation after the provider executor is connected.
                    </span>
                  </div>
                </div>
              </section>
            )}
          </section>
        </main>
      )}

      {view === "projects" && (
        <main className="page-container">
          <div className="page-heading">
            <div>
              <span className="eyebrow">PROJECTS</span>
              <h1>Connect an engine project</h1>
              <p>
                V3 separates cinematic identities from project-specific actors and
                assets. Project discovery is intentionally scoped.
              </p>
            </div>
          </div>

          {error && (
            <div className="banner banner-error">
              <CircleAlert size={17} /><span>{error}</span>
            </div>
          )}

          <div className="project-grid">
            <section className="stage-card connect-card">
              <div className="stage-header compact">
                <div>
                  <h2>Add project</h2>
                  <p>The backend validates a local Unity or Unreal project root.</p>
                </div>
                <HardDrive size={18} />
              </div>

              <label>
                Engine
                <select
                  value={connectEngine}
                  onChange={(event) => setConnectEngine(event.target.value as Engine)}
                >
                  <option value="unity">Unity</option>
                  <option value="unreal">Unreal Engine</option>
                </select>
              </label>
              <label>
                Project path
                <input
                  value={connectPath}
                  onChange={(event) => setConnectPath(event.target.value)}
                  placeholder={
                    connectEngine === "unity"
                      ? "D:\\Projects\\MyUnityProject"
                      : "D:\\Projects\\MyUnrealProject"
                  }
                />
              </label>
              <label>
                Display name <span>optional</span>
                <input
                  value={connectName}
                  onChange={(event) => setConnectName(event.target.value)}
                  placeholder="My cinematic project"
                />
              </label>
              <label>
                Engine executable <span>optional until runner is connected</span>
                <input
                  value={engineExecutable}
                  onChange={(event) => setEngineExecutable(event.target.value)}
                  placeholder="Path to Unity.exe or UnrealEditor.exe"
                />
              </label>
              <button
                className="primary-button full-width"
                onClick={connectProject}
                disabled={busy === "connect" || !connectPath.trim()}
              >
                {busy === "connect" ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Link2 size={15} />
                )}
                Connect and scan
              </button>
            </section>

            <section className="stage-card project-list-card">
              <div className="stage-header compact">
                <div>
                  <h2>Connected projects</h2>
                  <p>{projects.length} registered on this local Studio instance.</p>
                </div>
                <FolderKanban size={18} />
              </div>

              {projects.length === 0 ? (
                <div className="preview-empty">
                  <FolderKanban size={22} />
                  <span>No local projects connected yet.</span>
                </div>
              ) : (
                <div className="project-list">
                  {projects.map((item) => (
                    <button
                      className={
                        "project-list-item " +
                        (selectedProjectId === item.project_id ? "selected" : "")
                      }
                      key={item.project_id}
                      onClick={() => {
                        setSelectedProjectId(item.project_id);
                        setView("studio");
                        if (cir) loadBindingOptions(cir, item.project_id);
                      }}
                    >
                      <span className={"engine-logo small " + item.engine}>
                        {item.engine === "unity" ? "◆" : "U"}
                      </span>
                      <span className="project-list-copy">
                        <strong>{item.display_name}</strong>
                        <small>{item.project_path}</small>
                        <span>
                          {item.manifest.engine_version || "version unknown"} ·{" "}
                          {item.manifest.assets?.length || 0} objects ·{" "}
                          {item.manifest.discovery_mode}
                        </span>
                      </span>
                      <ChevronRight size={16} />
                    </button>
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className="stage-card">
            <div className="stage-header compact">
              <div>
                <h2>Discovery boundary</h2>
                <p>
                  Filesystem preflight is useful for project setup, but V3 requires
                  an engine-side bridge for stable actor IDs and verified rig/camera state.
                </p>
              </div>
              <ScanSearch size={18} />
            </div>
            <div className="boundary-grid">
              <div>
                <Pill tone="success">Available now</Pill>
                <strong>Scoped filesystem preflight</strong>
                <span>
                  Engine version markers, project assets, scenes/timelines and
                  adapter-ready paths.
                </span>
              </div>
              <div>
                <Pill tone="warning">Bridge required</Pill>
                <strong>Engine-native capability manifest</strong>
                <span>
                  Loaded actors, stable IDs, Humanoid/skeleton compatibility,
                  blendshapes/morphs, cameras and active scene state.
                </span>
              </div>
            </div>
          </section>
        </main>
      )}

      {view === "evidence" && (
        <main className="page-container evidence-page">
          <div className="page-heading">
            <div>
              <span className="eyebrow">RESEARCH & READINESS</span>
              <h1>Evidence is separate from the product workflow</h1>
              <p>
                Benchmark results demonstrate scoped research claims; they do not
                hard-code the Studio around one scene.
              </p>
            </div>
          </div>

          <div className="evidence-grid">
            <section className="stage-card proof-card">
              <div className="stage-header compact">
                <div>
                  <h2>S02 cross-engine motion result</h2>
                  <p>Retained research evidence for one compound humanoid motion.</p>
                </div>
                <FlaskConical size={18} />
              </div>

              <div className="proof-metrics">
                <div><span>Intent</span><strong>{research?.intent || "WALK_FORWARD_STOP_AND_LOOK_DOWN"}</strong></div>
                <div><span>Frames</span><strong>{research?.canonical?.frame_count || 96}</strong></div>
                <div><span>FPS</span><strong>{research?.canonical?.fps || 24}</strong></div>
                <div><span>Joints</span><strong>{research?.canonical?.joint_count || 22}</strong></div>
              </div>
              <div className="hash-box">
                <span>Canonical SHA-256</span>
                <code>{research?.canonical?.sha256 || "Loading…"}</code>
              </div>
              <div className="engine-proof-row">
                <span>Unreal</span>
                <Pill tone="success">Research realization</Pill>
              </div>
              <div className="engine-proof-row">
                <span>Unity</span>
                <Pill tone="warning">Direct runtime realization</Pill>
              </div>
              <p className="fine-print">
                This result demonstrates portability for S02. It does not
                empirically establish support for every possible humanoid motion.
              </p>
            </section>

            <section className="stage-card readiness-card">
              <div className="stage-header compact">
                <div>
                  <h2>V3 workflow readiness</h2>
                  <p>Backend-reported implementation status.</p>
                </div>
                <Settings2 size={18} />
              </div>

              <div className="capability-list">
                {capabilities.map((item) => {
                  const tone =
                    item.status === "implemented"
                      ? "success"
                      : item.status.includes("missing")
                        ? "danger"
                        : "warning";
                  return (
                    <div className="capability-row" key={item.id}>
                      <div>
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </div>
                      <Pill tone={tone as any}>{item.status}</Pill>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>

          <section className="stage-card remaining-card">
            <div className="stage-header compact">
              <div>
                <h2>Blocking work before the complete V3 workflow</h2>
                <p>
                  These are product/research gates, not hidden as completed features.
                </p>
              </div>
              <Wrench size={18} />
            </div>
            <div className="remaining-grid">
              {missingCapabilities.map((item) => (
                <div className="remaining-item" key={item.id}>
                  <CircleAlert size={16} />
                  <div>
                    <strong>{item.label}</strong>
                    <span>{item.description}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </main>
      )}
    </div>
  );
}

export default App;
