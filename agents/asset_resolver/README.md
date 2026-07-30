# Asset Resolver

Asset Resolver v0.1 is currently a deterministic engine-neutral service, not an autonomous agent.
It maps CIR environment objects and scene locations to a creator-curated Asset Index, records exact
scores and match terms, and emits explicit fallback evidence. It never mutates an engine project or
calls a model.

A future specialist agent may propose index curation or retrieval candidates, but its output must
still pass through the same typed resolution contract and approval boundary.
