# Performance Agent

The Performance Agent converts CIR motion, emotion, dialogue, and camera intent into an
inference-time Generated Performance Package. It must synthesize new motion rather than retrieve
pre-authored animation clips.

The portable contract lives in `performance/`. Model-provider integration is added behind this
boundary so Unreal and Unity always consume the same generated numerical artifacts.
