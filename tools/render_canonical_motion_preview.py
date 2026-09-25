from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from zipfile import ZipFile


def load_timeline(bundle_path: Path, actor: str | None) -> dict[str, object]:
    with ZipFile(bundle_path) as z:
        package = json.loads(z.read("performance.package.json"))
        tracks = package["body_tracks"]
        actors = sorted({t["actor_binding_id"] for t in tracks})
        actor = actor or actors[0]
        selected = sorted(
            [t for t in tracks if t["actor_binding_id"] == actor],
            key=lambda t: (t["start_frame"], t["semantic_id"]),
        )
        if not selected:
            raise ValueError(f"No body tracks for {actor!r}; available: {actors}")
        duration = package["duration_frames"]
        frames = [None] * duration
        phases = [None] * duration
        names = parents = None
        for track in selected:
            motion = json.loads(z.read(track["artifact"]["relative_path"]))
            names = names or motion["joint_names"]
            parents = parents or motion["parent_indices"]
            for sample in motion["samples"]:
                if sample["joint_positions"] is None:
                    raise ValueError("Canonical joint_positions are required.")
                i = track["start_frame"] + sample["frame_index"]
                frames[i] = [[p["x"], p["y"], p["z"]] for p in sample["joint_positions"]]
                phases[i] = track["semantic_id"]

    used = [i for i, f in enumerate(frames) if f is not None]
    if not used:
        raise ValueError("No canonical XYZ frames found.")
    lo, hi = used[0], used[-1]
    frames = frames[lo : hi + 1]
    phases = phases[lo : hi + 1]
    previous = None
    for i, frame in enumerate(frames):
        if frame is None:
            if previous is None:
                raise ValueError("Timeline starts with an empty body frame.")
            frames[i] = previous
        else:
            previous = frame
    return {
        "actor": actor,
        "fps": package["fps"],
        "start_frame": lo,
        "frames": frames,
        "phases": phases,
        "joint_names": names,
        "parents": parents,
        "bundle": bundle_path.name,
    }


def render_html(data: dict[str, object]) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    title = html.escape(f"CutSceneAI Canonical Motion Preview — {data['actor']}")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:system-ui;background:#111;color:#eee;margin:0}}main{{max-width:1500px;margin:auto;padding:18px}}
h1{{font-size:20px}}.c{{display:flex;gap:10px;align-items:center}}input{{flex:1}}
.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}}
.p{{background:#181818;border:1px solid #333;padding:8px}}canvas{{width:100%;aspect-ratio:1;background:#080808}}
@media(max-width:900px){{.g{{grid-template-columns:1fr}}}}</style></head><body><main>
<h1>{title}</h1><div id="meta"></div><div class="c"><button id="play">Play</button>
<input id="s" type="range" min="0" value="0" step="1"><span id="f"></span></div><div id="phase"></div>
<div class="g"><div class="p">Front (X/Y)<canvas id="front" width="520" height="520"></canvas></div>
<div class="p">Side (Z/Y)<canvas id="side" width="520" height="520"></canvas></div>
<div class="p">Top (X/Z)<canvas id="top" width="520" height="520"></canvas></div></div>
<script>
const D={payload},F=D.frames,P=D.parents,S=document.getElementById("s");S.max=F.length-1;
const V={{front:[0,1,false,true],side:[2,1,true,true],top:[0,2,false,false]}};
let mn=[Infinity,Infinity,Infinity],mx=[-Infinity,-Infinity,-Infinity];
for(const f of F)for(const p of f)for(let a=0;a<3;a++){{mn[a]=Math.min(mn[a],p[a]);mx[a]=Math.max(mx[a],p[a]);}}
for(let a=0;a<3;a++){{const q=Math.max((mx[a]-mn[a])*.08,.05);mn[a]-=q;mx[a]+=q;}}
let i=0,t=null;
function pr(p,v,w,h){{let x=(p[v[0]]-mn[v[0]])/(mx[v[0]]-mn[v[0]]),y=(p[v[1]]-mn[v[1]])/(mx[v[1]]-mn[v[1]]);
if(v[2])x=1-x;if(v[3])y=1-y;return[24+x*(w-48),24+y*(h-48)];}}
function dc(id){{const c=document.getElementById(id),x=c.getContext("2d"),v=V[id],f=F[i];x.clearRect(0,0,c.width,c.height);
x.strokeStyle="#ddd";x.fillStyle="#fff";x.lineWidth=5;x.lineCap="round";
for(let j=0;j<P.length;j++){{if(P[j]<0)continue;const a=pr(f[P[j]],v,c.width,c.height),b=pr(f[j],v,c.width,c.height);
x.beginPath();x.moveTo(...a);x.lineTo(...b);x.stroke();}}for(const p of f){{const q=pr(p,v,c.width,c.height);x.beginPath();x.arc(q[0],q[1],4,0,Math.PI*2);x.fill();}}}}
function draw(){{S.value=i;document.getElementById("f").textContent="frame "+(D.start_frame+i);
document.getElementById("phase").textContent=D.phases[i]||"";for(const id of Object.keys(V))dc(id);}}
document.getElementById("meta").textContent=D.bundle+" · "+D.actor+" · "+D.fps+" fps";
document.getElementById("play").onclick=e=>{{if(t){{clearInterval(t);t=null;e.target.textContent="Play";return;}}
e.target.textContent="Pause";t=setInterval(()=>{{i=(i+1)%F.length;draw();}},1000/Math.max(1,D.fps));}};
S.oninput=()=>{{i=Number(S.value);draw();}};draw();
</script></main></body></html>"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--actor")
    p.add_argument("--run-root", default=".cutsceneai-studio/runs/performance")
    p.add_argument("--output")
    a = p.parse_args()
    run = Path(a.run_root) / a.run_id
    bundle = run / "performance.bundle.zip"
    if not bundle.is_file():
        raise SystemExit(f"Missing bundle: {bundle}")
    out = Path(a.output) if a.output else run / "canonical-body-preview.html"
    out.write_text(render_html(load_timeline(bundle, a.actor)), encoding="utf-8", newline="\n")
    print(out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
