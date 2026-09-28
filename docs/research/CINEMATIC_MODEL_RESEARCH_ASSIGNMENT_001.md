# CutSceneAI Cinematic Model Research Assignment 001

**Branch:** `agent/cinematic-model-research-v0.1`  
**Parent direction:** `docs/CUTSCENEAI_CINEMATIC_MODEL_HANDOFF.md`

## Role

Act as a research engineer supporting the CutSceneAI technical lead.

Do not redesign the product architecture independently. Do not modify `agent/cross-engine-parity-v0.1`. Work only on the research branch above unless explicitly told otherwise.

## Assignment

Research the strongest technical foundations for a new trainable, engine-neutral **CutSceneAI Cinematic Performance Model**.

The goal is not to find one off-the-shelf model to adopt unchanged. The goal is to identify the best reusable ideas, datasets, representations, training strategies, and benchmark practices that can inform a CutSceneAI-specific model.

Focus on these areas:

1. **Scene-conditioned human motion generation**
   - text + scene geometry
   - target-object conditioning
   - goal-directed motion
   - interaction-aware motion
   - path / trajectory conditioning
   - future-pose or endpoint conditioning

2. **Long-horizon and multi-phase motion**
   - temporal decomposition
   - motion composition
   - transition generation
   - contact-aware generation
   - diffusion, flow-matching, transformer, autoregressive, hybrid approaches

3. **Human-scene interaction datasets**
   - motion capture datasets
   - text-motion datasets
   - scene-conditioned motion datasets
   - interaction datasets
   - datasets with object geometry, contacts, gaze, or goal labels
   - note licensing / research-use constraints

4. **Synthetic data generation**
   - Blender / Unity / Unreal / simulation-based approaches
   - procedural scene randomization
   - automatic labels for contacts, gaze, target direction, root path, collision, and camera
   - domain gap risks and mitigation

5. **Cinematic camera generation**
   - learned or optimization-based camera planning
   - scene-aware composition
   - subject visibility
   - occlusion and collision constraints
   - shot continuity
   - datasets or benchmarks for cinematography

6. **Evaluation**
   - motion realism
   - semantic correctness
   - target-facing error
   - foot sliding
   - contact accuracy
   - root path error
   - scene collision
   - gaze accuracy
   - camera framing / visibility / collision
   - cross-engine parity relevance

## Required deliverable

Create and commit:

`docs/research/CINEMATIC_MODEL_RESEARCH_001.md`

The report must include:

- a concise executive summary;
- a table of the most relevant papers / models / datasets;
- year and source links;
- what each contributes;
- limitations for CutSceneAI;
- license / usage notes where available;
- which ideas are directly reusable;
- which ideas require redesign;
- recommended model families for our first body-motion baseline;
- recommended datasets for pretraining / fine-tuning / synthetic augmentation;
- a proposed staged training strategy;
- a proposed evaluation suite;
- explicit risks;
- a final section titled **"Recommendation to Technical Lead"** with 3–5 concrete recommendations.

## Important constraints

- Do not recommend Unity or Unreal as the motion-generation source.
- Preserve the engine-neutral canonical-performance goal.
- Do not assume MDM remains the central model.
- Distinguish existing research evidence from your own proposal.
- Prefer primary papers, official project pages, and dataset documentation.
- Verify current availability and licensing where possible.
- Do not implement production model code in this assignment.
- Do not merge anything into the main working branch.
- Commit only the research report and any small supporting bibliography file if genuinely useful.

## Completion message

When finished, report:

1. commit SHA;
2. exact file path;
3. one-paragraph summary of the strongest finding;
4. any blocking uncertainty that the technical lead should resolve before model design.
