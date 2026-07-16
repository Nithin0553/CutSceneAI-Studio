# Unreal Adapter v0.4.0 Release Notes

Released: 2026-07-16  
Target engine: Unreal Engine 5.8.0  
Merge commit: `1a18f8c5eb87bb07e3d8dd6a251f38dbe66ce768`

## Outcome

Unreal Adapter v0.4 turns compatible CIR motion asset references into editable, frame-aligned
Skeletal Animation sections in Sequencer. It extends the existing deterministic scene assembly,
camera cuts, persistent transforms, and Skeletal Mesh character binding without making the adapter
responsible for asset discovery or retargeting.

## Shipped contract

- `animation_sections` is a typed collection in the Unreal export plan and committed v0.4 schema.
- Each section identifies its CIR beat, target actor binding, `/Game/...` animation asset, start
  frame, and exclusive end frame.
- The importer creates one **CutSceneAI Animation** track per skeletal character and reuses it for
  that character's sections.
- Unsupported URIs and non-skeletal targets remain marker metadata with explicit warnings.
- The importer remains non-destructive and refuses to overwrite an existing Level Sequence.

## Automated evidence

- 85 tests passed before merge.
- Branch-aware coverage: 97.48%, above the required 95% threshold.
- Ruff check and format check passed.
- Mypy passed across 32 source files.
- CIR, Preview, and Unreal generated-artifact drift checks passed.
- GitHub Actions passed on Python 3.11, 3.12, and 3.13 before and after merge.

## Unreal Engine 5.8 acceptance

The office-dialogue fixture compiled four animation sections:

| Character | Frame ranges | Skeletal Mesh | Accepted animation asset |
| --- | --- | --- | --- |
| Mina | `0-96`, `96-336` | `SKM_Quinn_Simple` | `/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle` |
| Arjun | `96-336`, `336-432` | `SKM_Manny_Simple` | `/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle` |

Acceptance results:

- one editable animation track and two sections per character;
- both characters moved normally in the accepted project;
- tracks and motion persisted after saving and restarting Unreal;
- Movie Render Queue completed with 432 frames (`0000-0431`);
- both characters were animated and visible;
- all camera cuts were correct; and
- no black or empty frames were produced.

The installed Third Person content exposed `MM_Idle` but not `MF_Idle`. The accepted animation was
compatible with both mannequin meshes in that project. Consumers must still verify skeleton
compatibility in their own projects.

## Object-reference troubleshooting

Unreal's **Copy Reference** command can return a value such as:

```text
/Script/Engine.AnimSequence'/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle'
```

CIR must receive only the quoted object path:

```text
/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle
```

Passing the `/Script/Engine.AnimSequence'...'` wrapper intentionally produces an
`unsupported_animation_uri` warning and leaves the cue as metadata.

## Upgrade and regeneration

1. Install the updated CIR, Preview, Unreal Adapter, and backend packages from the same checkout.
2. Add `/Game/...` Skeletal Mesh references to CIR characters.
3. Add compatible `/Game/...` Anim Sequence references to `performance.motion.asset_uri`.
4. Export a new plan and confirm the expected `animation_sections` before generating the importer.
5. Back up manual edits, intentionally remove the old generated `LS_SceneMeeting`, execute the new
   importer, and save all.
6. Restart Unreal and run MRQ before accepting the regenerated sequence.

## Known boundaries and next milestone

This release does not discover assets, infer compatibility, retarget skeletons, generate motion,
animate faces, place dialogue audio, generate camera curves, or launch unattended final renders.
The next milestone is Unreal Adapter v0.5, which compiles CIR dialogue audio references into editable,
speaker-bound Sequencer audio sections.

Implementation and review history: [pull request #12](https://github.com/Nithin0553/CutSceneAI-Studio/pull/12).
