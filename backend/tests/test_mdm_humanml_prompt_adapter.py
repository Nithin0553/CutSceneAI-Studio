from __future__ import annotations

from tools.providers import mdm_humanml_provider as mdm


def _request(action: str, *, target_binding_id: str | None) -> dict[str, object]:
    return {
        "prompt": (
            "Generate novel full-body motion. "
            f"Action: {action} "
            "Style: cautious pivot. "
            "Emotion: wary at 0.70 intensity. "
            "Duration: 24 frames at 24 fps."
        ),
        "target_binding_id": target_binding_id,
    }


def test_target_turn_is_rewritten_as_generic_turn_primitive() -> None:
    prompt = mdm._motion_prompt(
        _request("turn toward the door", target_binding_id="actor:door")
    )

    assert "turn the whole body in place" in prompt
    assert "distinctly different direction" in prompt
    assert "door" not in prompt
    assert "planted-foot pivot" in prompt


def test_target_hold_is_rewritten_as_stationary_primitive() -> None:
    prompt = mdm._motion_prompt(
        _request(
            "hold a cautious stance facing the door",
            target_binding_id="actor:door",
        )
    )

    assert "remain still in place" in prompt
    assert "no stepping or root travel" in prompt
    assert "door" not in prompt


def test_non_target_phase_preserves_its_action_text() -> None:
    prompt = mdm._motion_prompt(
        _request("hold a guarded listening pose", target_binding_id=None)
    )

    assert prompt.startswith("hold a guarded listening pose.")
