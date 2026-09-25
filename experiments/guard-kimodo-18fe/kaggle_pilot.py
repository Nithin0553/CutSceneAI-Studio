"""Run the 18fe guard body-motion pilot in a Kaggle GPU notebook.

This script intentionally keeps the private Hugging Face token out of the
repository and saves only motion evidence under /kaggle/working.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
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


def install_kimodo() -> None:
    """Build MotionCorrection against Kaggle's Python rather than Ubuntu's 3.10."""
    if os.geteuid() != 0:
        raise RuntimeError("This notebook requires root to install C++ build dependencies.")
    run(["apt-get", "update", "-qq"])
    run(["apt-get", "install", "-y", "-qq", "cmake", "libeigen3-dev"])

    # Ubuntu 22.04's pybind11-dev is 2.9.1. Its CMake package takes priority
    # unless a Python-3.12-compatible package is put first on CMAKE_PREFIX_PATH.
    run([sys.executable, "-m", "pip", "install", "pybind11==2.13.6"])
    import pybind11

    import sysconfig

    header_dir = Path(sysconfig.get_path("include"))
    if not (header_dir / "Python.h").is_file():
        raise RuntimeError(f"Python {sys.version_info[:2]} headers missing at {header_dir}")

    # A Python extension needs Development.Module, not Development.Embed.
    # Ubuntu 22.04's python3-dev supplies 3.10 embed libraries while Kaggle
    # runs 3.12, which can make CMake's full Development check fail.
    cmake_file = SRC_DIR / "MotionCorrection" / "CMakeLists.txt"
    original = "find_package(Python3 COMPONENTS Interpreter Development REQUIRED)"
    replacement = "find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)"
    contents = cmake_file.read_text()
    if original in contents:
        cmake_file.write_text(contents.replace(original, replacement, 1))
    elif replacement not in contents:
        raise RuntimeError("Kimodo MotionCorrection CMake declaration changed; inspect upstream source.")

    env = os.environ.copy()
    env["CMAKE_PREFIX_PATH"] = os.pathsep.join(
        filter(None, (pybind11.get_cmake_dir(), env.get("CMAKE_PREFIX_PATH", "")))
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logfile = OUT_DIR / "build.log"
    print(f"Building Kimodo with pybind11 {pybind11.__version__}; log: {logfile}", flush=True)
    with logfile.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(SRC_DIR), "-v"],
            env=env, stdout=log, stderr=subprocess.STDOUT, check=False,
        )
    if result.returncode:
        lines = logfile.read_text(errors="replace").splitlines()
        markers = [i for i, line in enumerate(lines) if re.search(
            r"CMake Error|fatal error|Could NOT find|FAILED:|error: command", line
        )]
        if markers:
            index = markers[0]
            print("First native build error:\n" + "\n".join(lines[max(0, index - 8):index + 20]))
        print("Last 35 build-log lines:\n" + "\n".join(lines[-35:]))
        raise RuntimeError(f"Kimodo build failed; full log at {logfile}")
    import motion_correction

    print(f"Kimodo and MotionCorrection installed: {motion_correction.__file__}", flush=True)


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

    install_kimodo()

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
        "native_build": "pybind11==2.13.6; CMake Python3 Development.Module",
        "text_encoder_device": "cpu",
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "numpy_arrays": arrays,
        "sha256": {p.name: sha256(p) for p in (
            npz, bvh, logfile, OUT_DIR / "build.log", OUT_DIR / "meta.json", OUT_DIR / "constraints.json"
        )},
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
