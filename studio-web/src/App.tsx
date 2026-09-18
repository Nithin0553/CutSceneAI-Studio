import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BadgeCheck,
  Box,
  ChevronRight,
  CircleAlert,
  Clapperboard,
  Code2,
  Download,
  ExternalLink,
  FileJson2,
  Film,
  FlaskConical,
  LoaderCircle,
  Play,
  Server,
  Sparkles,
  Waypoints,
} from "lucide-react";
import "./styles.css";

type Json = Record<string, any>;

type Stage = "idle" | "generating" | "ready" | "error";

const S02_SHA =
  "f708f7a0ca84f055d9c357a6c72bc30f726108400c8c9b799d728f8f58fca461";

const defaultPrompt =
  "Create a tense cinematic office scene where a character walks forward, stops beside a desk, looks down, then pauses before the next beat. Keep the action readable and grounded.";

async function apiJson(path: string, init?: RequestInit) {
  const response = await fetch(path, init);
  const text = await response.text();
  let body: any;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!response.ok) {
    const message =
      body?.message ||
      body?.detail ||
      body?.code ||
      `Request failed with HTTP ${response.status}`;
    throw new Error(message);
  }
  return body;
}

async function downloadPost(
  path: string,
  project: Json,
  filename: string,
  fallbackType: string,
) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project),
  });
  const data = await response.blob();
  if (!response.ok) {
    throw new Error(await data.text());
  }
  const blob = new Blob([data], { type: data.type || fallbackType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function Pill({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "success" | "warning" | "info";
  children: React.ReactNode;
}) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function App() {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [stage, setStage] = useState<Stage>("idle");
  const [project, setProject] = useState<Json | null>(null);
  const [validation, setValidation] = useState<Json | null>(null);
  const [storyboard, setStoryboard] = useState<string>("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [exportBusy, setExportBusy] = useState("");

  useEffect(() => {
    apiJson("/health")
      .then(() => setHealth("online"))
      .catch(() => setHealth("offline"));
  }, []);

  const summary = useMemo(() => {
    if (!validation?.summary) return null;
    return validation.summary;
  }, [validation]);

  async function generate() {
    setStage("generating");
    setError("");
    setProject(null);
    setValidation(null);
    setStoryboard("");

    try {
      const director = await apiJson("/api/v1/director/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      const nextProject = director.project;
      setProject(nextProject);
      setProvider(director.provider || "");
      setModel(director.model || "");
      setRequestId(director.request_id || null);

      const [validated, storyboardResponse] = await Promise.all([
        apiJson("/api/v1/cir/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextProject),
        }),
        fetch("/api/v1/preview/storyboard.svg", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextProject),
        }),
      ]);

      if (!storyboardResponse.ok) {
        throw new Error(await storyboardResponse.text());
      }

      setValidation(validated);
      setStoryboard(await storyboardResponse.text());
      setStage("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setStage("error");
    }
  }

  async function doExport(engine: "unity" | "unreal") {
    if (!project) return;
    setExportBusy(engine);
    setError("");
    try {
      if (engine === "unity") {
        await downloadPost(
          "/api/v1/adapters/unity/importer.cs",
          project,
          "CutSceneAI-Unity-Importer.cs",
          "text/x-csharp",
        );
      } else {
        await downloadPost(
          "/api/v1/adapters/unreal/importer.py",
          project,
          "cutsceneai-unreal-import.py",
          "text/x-python",
        );
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setExportBusy("");
    }
  }

  function downloadCir() {
    if (!project) return;
    const blob = new Blob([JSON.stringify(project, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${project.id || "cutsceneai-project"}.cir.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Clapperboard size={22} />
          </div>
          <div>
            <strong>CutSceneAI</strong>
            <span>Studio</span>
          </div>
        </div>

        <div className="topbar-center">
          <Pill tone="info">Research Preview</Pill>
          <span className="branch">cross-engine-parity-v0.1</span>
        </div>

        <div className={`server-status server-${health}`}>
          <Server size={15} />
          {health === "checking"
            ? "Checking API"
            : health === "online"
              ? "API connected"
              : "API offline"}
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <Pill tone="success">
              <BadgeCheck size={13} /> S02 research result locked
            </Pill>
            <h1>
              Generate cinematic intent once.
              <br />
              <span>Realize it across engines.</span>
            </h1>
            <p>
              CutSceneAI turns a creative brief into a validated,
              engine-independent cinematic representation, then compiles it for
              Unreal and Unity without rewriting the scene by hand.
            </p>
          </div>

          <div className="hero-proof">
            <div className="proof-header">
              <FlaskConical size={18} />
              Cross-engine research proof
            </div>
            <div className="proof-flow">
              <div>
                <small>Canonical motion</small>
                <strong>S02</strong>
              </div>
              <ChevronRight size={16} />
              <div>
                <small>Unreal</small>
                <strong className="ok">Realized</strong>
              </div>
              <ChevronRight size={16} />
              <div>
                <small>Unity</small>
                <strong className="ok">Runtime realized</strong>
              </div>
            </div>
            <code>{S02_SHA}</code>
            <small className="proof-note">
              Same hash-locked source; no engine-specific AI re-inference.
            </small>
          </div>
        </section>

        <section className="workspace">
          <aside className="workflow-card panel">
            <div className="panel-title">
              <Waypoints size={18} />
              Pipeline
            </div>

            {[
              ["01", "Creative brief", "Describe the scene"],
              ["02", "Director", "Generate typed CIR"],
              ["03", "Validation", "Check cinematic contract"],
              ["04", "Preview", "Review storyboard"],
              ["05", "Export", "Compile engine adapters"],
            ].map(([number, title, subtitle], index) => (
              <div
                className={`workflow-step ${stage === "ready" || index === 0 ? "active" : ""}`}
                key={number}
              >
                <span>{number}</span>
                <div>
                  <strong>{title}</strong>
                  <small>{subtitle}</small>
                </div>
              </div>
            ))}
          </aside>

          <section className="creator panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">CREATE</div>
                <h2>What should happen in the scene?</h2>
              </div>
              <Sparkles size={20} />
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              minLength={20}
              maxLength={8000}
              placeholder="Describe the action, mood, characters, camera intent..."
            />

            <div className="prompt-footer">
              <span>{prompt.length} / 8000</span>
              <button
                className="primary-button"
                onClick={generate}
                disabled={stage === "generating" || prompt.trim().length < 20}
              >
                {stage === "generating" ? (
                  <>
                    <LoaderCircle className="spin" size={17} /> Generating
                  </>
                ) : (
                  <>
                    <Sparkles size={17} /> Generate scene
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="error-banner">
                <CircleAlert size={17} />
                <span>{error}</span>
              </div>
            )}

            <div className="generation-meta">
              <span>
                Director <b>{provider || "waiting"}</b>
              </span>
              <span>
                Model <b>{model || "—"}</b>
              </span>
              {requestId && (
                <span>
                  Request <b>{requestId.slice(0, 12)}</b>
                </span>
              )}
            </div>
          </section>

          <aside className="research-card panel">
            <div className="panel-title">
              <Activity size={18} />
              Locked evidence
            </div>
            <Stat label="Motion" value="WALK → STOP → LOOK DOWN" />
            <div className="mini-grid">
              <Stat label="Frames" value="96" />
              <Stat label="FPS" value="24" />
              <Stat label="Joints" value="22" />
            </div>
            <div className="research-row">
              <span>Unreal</span>
              <Pill tone="success">Research pass</Pill>
            </div>
            <div className="research-row">
              <span>Unity</span>
              <Pill tone="warning">Runtime pass</Pill>
            </div>
            <p className="research-disclaimer">
              Native Unity AnimationClip/Timeline playback remains a known
              limitation. Production animation polish is deferred.
            </p>
          </aside>
        </section>

        <section className="results-grid">
          <div className="panel preview-panel">
            <div className="panel-heading compact">
              <div>
                <div className="eyebrow">PREVIEW</div>
                <h2>Storyboard</h2>
              </div>
              <Film size={19} />
            </div>

            {storyboard ? (
              <div
                className="storyboard"
                dangerouslySetInnerHTML={{ __html: storyboard }}
              />
            ) : (
              <div className="empty-state">
                <div className="empty-icon">
                  <Play size={22} />
                </div>
                <strong>Your storyboard will appear here</strong>
                <span>
                  Generate a scene to compile the engine-neutral preview.
                </span>
              </div>
            )}
          </div>

          <div className="panel output-panel">
            <div className="panel-heading compact">
              <div>
                <div className="eyebrow">OUTPUT</div>
                <h2>Cinematic contract</h2>
              </div>
              <FileJson2 size={19} />
            </div>

            {summary ? (
              <>
                <div className="summary-grid">
                  <Stat label="Scenes" value={String(summary.scene_count)} />
                  <Stat label="Beats" value={String(summary.beat_count)} />
                  <Stat label="Shots" value={String(summary.shot_count)} />
                </div>
                <div className="contract-row">
                  <span>Project</span>
                  <code>{validation.project_id}</code>
                </div>
                <div className="contract-row">
                  <span>Schema</span>
                  <Pill tone="success">{validation.schema_version}</Pill>
                </div>
                <button className="secondary-button full" onClick={downloadCir}>
                  <Download size={16} /> Download CIR JSON
                </button>
              </>
            ) : (
              <div className="empty-state small">
                <Code2 size={24} />
                <strong>No CIR generated yet</strong>
                <span>Validated project details will appear here.</span>
              </div>
            )}
          </div>
        </section>

        <section className="engine-section">
          <div className="section-heading">
            <div>
              <div className="eyebrow">ENGINE ADAPTERS</div>
              <h2>Take the same scene into your engine</h2>
              <p>
                Both exports are compiled from the same validated CIR project.
              </p>
            </div>
          </div>

          <div className="engine-grid">
            <article className="engine-card panel">
              <div className="engine-icon unreal">U</div>
              <div className="engine-copy">
                <div className="engine-name">
                  <h3>Unreal Engine</h3>
                  <Pill tone="success">Adapter available</Pill>
                </div>
                <p>
                  Generate a self-contained Python importer for editable
                  Sequencer assets.
                </p>
                <div className="engine-tags">
                  <span>Sequencer</span>
                  <span>Python importer</span>
                  <span>Editable assets</span>
                </div>
              </div>
              <button
                className="secondary-button"
                disabled={!project || exportBusy === "unreal"}
                onClick={() => doExport("unreal")}
              >
                {exportBusy === "unreal" ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Download size={16} />
                )}
                Export Unreal
              </button>
            </article>

            <article className="engine-card panel">
              <div className="engine-icon unity">◆</div>
              <div className="engine-copy">
                <div className="engine-name">
                  <h3>Unity</h3>
                  <Pill tone="success">Adapter available</Pill>
                </div>
                <p>
                  Generate a C# Editor importer for deterministic Unity
                  Timeline realization.
                </p>
                <div className="engine-tags">
                  <span>Timeline</span>
                  <span>C# importer</span>
                  <span>Humanoid mapping</span>
                </div>
              </div>
              <button
                className="secondary-button"
                disabled={!project || exportBusy === "unity"}
                onClick={() => doExport("unity")}
              >
                {exportBusy === "unity" ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Download size={16} />
                )}
                Export Unity
              </button>
            </article>
          </div>

          <div className="local-runner-note">
            <Box size={18} />
            <div>
              <strong>Engine execution stays local in this version.</strong>
              <span>
                The browser generates portable project and adapter artifacts.
                The next integration layer will hand those artifacts to a local
                CutSceneAI runner that launches the installed engine and
                returns progress/evidence to this page.
              </span>
            </div>
          </div>
        </section>

        <section className="research-strip">
          <FlaskConical size={18} />
          <div>
            <strong>Research claim, scoped correctly</strong>
            <span>
              S02 demonstrates cross-engine canonical motion portability for one
              compound humanoid motion. It does not claim universal empirical
              support for every possible motion.
            </span>
          </div>
          <a href="#top" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
            Back to create <ExternalLink size={14} />
          </a>
        </section>
      </main>
    </div>
  );
}

export default App;
