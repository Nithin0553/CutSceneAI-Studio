"""Run the 18fe guard body-motion pilot in a Kaggle GPU notebook.

This script intentionally keeps the private Hugging Face token out of the
repository and saves only motion evidence under /kaggle/working.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


KIMODO_COMMIT = "58e781898b3d7e328a676a75d3e338c45dce3ad9"
PILOT_DIR = Path(__file__).resolve().parent
WORK_DIR = Path("/kaggle/working")
OUT_DIR = WORK_DIR / "guard-kimodo-18fe"
SRC_DIR = Path("/tmp/cutsceneai-kimodo-source")


def run(args: list[str], **kwargs: object) -> None:
    print("Running:", " ".join(args), flush=True)
    subprocess.run(args, check=True, **kwargs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not WORK_DIR.is_dir():
        raise RuntimeError("Run this pilot in a Kaggle notebook with a T4 GPU.")
    token = os.environ.pop("HF_TOKEN", None)
    if not token:
        raise RuntimeError("Set HF_TOKEN via Kaggle Secrets; never paste it into notebook code.")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Select GPU T4 x2 in Kaggle Notebook Settings first.")
    memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    cgroup_limit = Path("/sys/fs/cgroup/memory.max")
    if cgroup_limit.is_file() and cgroup_limit.read_text().strip().isdigit():
        memory_bytes = min(memory_bytes, int(cgroup_limit.read_text().strip()))
    memory_gib = memory_bytes / 1024**3
    print(f"Python {sys.version.split()[0]}; PyTorch {torch.__version__}; GPU {torch.cuda.get_device_name(0)}; RAM {memory_gib:.1f} GiB")
    if memory_gib < 24:
        raise RuntimeError("The 8B CPU text encoder needs a notebook with about 29 GiB RAM.")

    if not SRC_DIR.exists():
        run(["git", "clone", "https://github.com/nv-tlabs/kimodo.git", str(SRC_DIR)])
    run(["git", "-C", str(SRC_DIR), "fetch", "--depth", "1", "origin", KIMODO_COMMIT])
    run(["git", "-C", str(SRC_DIR), "checkout", "--detach", KIMODO_COMMIT])

    # Kimodo bundles a CMake/pybind11 MotionCorrection extension for foot contact.
    if os.geteuid() != 0:
        raise RuntimeError("This notebook requires root to install C++ build dependencies.")
    run(["apt-get", "update", "-qq"])
    run(["apt-get", "install", "-y", "-qq", "cmake", "libeigen3-dev", "pybind11-dev", "python3-dev"])
    run([sys.executable, "-m", "pip", "install", "-e", str(SRC_DIR)])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("meta.json", "constraints.json"):
        shutil.copy2(PILOT_DIR / name, OUT_DIR / name)
    env = os.environ.copy()
    env["HF_HOME"] = "/root/.cache/huggingface"  # outside Kaggle's downloadable outputs
    env["TEXT_ENCODER_DEVICE"] = "cpu"
    env["TEXT_ENCODER_MODE"] = "local"
    env["HF_TOKEN"] = token
    stem = OUT_DIR / "guard"
    cmd = [
        sys.executable, "-m", "kimodo.scripts.generate",
        "--input_folder", str(PILOT_DIR),
        "--model", "Kimodo-SOMA-RP-v1.1",
        "--output", str(stem),
        "--bvh", "--bvh_standard_tpose",
    ]
    logfile = OUT_DIR / "run.log"
    print("Generating the 12-second guard motion; watch run.log if this takes a while.", flush=True)
    with logfile.open("w", encoding="utf-8") as log:
        result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        print("Kimodo failed. Final log lines:")
        print("\n".join(logfile.read_text(errors="replace").splitlines()[-60:]))
        raise RuntimeError(f"Kimodo exited with status {result.returncode}")

    npz = stem.with_suffix(".npz")
    bvh = stem.with_suffix(".bvh")
    if not npz.is_file() or not bvh.is_file():
        raise RuntimeError(f"Missing expected output: {npz} / {bvh}. Inspect {logfile}.")
    import numpy as np

    with np.load(npz) as motion:
        arrays = {name: list(motion[name].shape) for name in motion.files}
    manifest = {
        "kimodo_commit": KIMODO_COMMIT,
        "model": "nvidia/Kimodo-SOMA-RP-v1.1",
        "text_encoder_device": "cpu",
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "numpy_arrays": arrays,
        "sha256": {p.name: sha256(p) for p in (npz, bvh, logfile, OUT_DIR / "meta.json", OUT_DIR / "constraints.json")},
        "acceptance": "UNREVIEWED: asset creation alone does not pass visual acceptance",
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    archive = WORK_DIR / "guard-kimodo-18fe-evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(OUT_DIR.iterdir()):
            if path.is_file():
                bundle.write(path, path.name)
    print(f"Evidence ready: {archive}; arrays: {arrays}")
    print("Download the ZIP and share it for visual review. Do not import to Unity yet.")


if __name__ == "__main__":
    main()
