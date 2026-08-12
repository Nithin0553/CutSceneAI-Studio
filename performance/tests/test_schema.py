from __future__ import annotations

import json
from pathlib import Path

from cutsceneai_performance import (
    ARKIT_52_CURVES,
    BODY_MOTION_SCHEMA_ID,
    CAMERA_CURVE_SCHEMA_ID,
    CANONICAL_HUMANOID_JOINTS,
    CANONICAL_HUMANOID_PARENTS,
    FACIAL_CURVE_SCHEMA_ID,
    GENERATION_PLAN_SCHEMA_ID,
    JSON_SCHEMA_DIALECT,
    PERFORMANCE_PACKAGE_SCHEMA_ID,
    body_motion_json_schema,
    camera_curve_json_schema,
    facial_curve_json_schema,
    generation_plan_json_schema,
    performance_package_json_schema,
    render_body_motion_json_schema,
    render_camera_curve_json_schema,
    render_facial_curve_json_schema,
    render_generation_plan_json_schema,
    render_performance_package_json_schema,
    write_body_motion_json_schema,
    write_camera_curve_json_schema,
    write_facial_curve_json_schema,
    write_performance_package_json_schema,
)
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).parents[1] / "schemas" / "performance-package-v0.1.schema.json"
)
PLAN_SCHEMA_PATH = (
    Path(__file__).parents[1] / "schemas" / "generation-plan-v0.1.schema.json"
)
MOTION_SCHEMA_PATH = (
    Path(__file__).parents[1] / "schemas" / "body-motion-v0.1.schema.json"
)
FACIAL_SCHEMA_PATH = (
    Path(__file__).parents[1] / "schemas" / "facial-curves-v0.1.schema.json"
)
CAMERA_SCHEMA_PATH = (
    Path(__file__).parents[1] / "schemas" / "camera-curves-v0.1.schema.json"
)


def test_schema_declares_public_contract() -> None:
    schema = performance_package_json_schema()

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == PERFORMANCE_PACKAGE_SCHEMA_ID
    assert schema["additionalProperties"] is False
    Draft202012Validator.check_schema(schema)


def test_committed_schema_matches_models() -> None:
    committed = SCHEMA_PATH.read_text(encoding="utf-8")

    assert committed == render_performance_package_json_schema()
    assert json.loads(committed) == performance_package_json_schema()


def test_generation_plan_schema_matches_models() -> None:
    schema = generation_plan_json_schema()
    committed = PLAN_SCHEMA_PATH.read_text(encoding="utf-8")

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == GENERATION_PLAN_SCHEMA_ID
    Draft202012Validator.check_schema(schema)
    assert committed == render_generation_plan_json_schema()


def test_body_motion_schema_matches_models() -> None:
    schema = body_motion_json_schema()
    committed = MOTION_SCHEMA_PATH.read_text(encoding="utf-8")

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == BODY_MOTION_SCHEMA_ID
    assert schema["properties"]["joint_names"]["const"] == list(
        CANONICAL_HUMANOID_JOINTS
    )
    assert schema["properties"]["parent_indices"]["const"] == list(
        CANONICAL_HUMANOID_PARENTS
    )
    rotations = schema["$defs"]["BodyMotionSample"]["properties"]["joint_rotations"]
    assert rotations["minItems"] == len(CANONICAL_HUMANOID_JOINTS)
    assert rotations["maxItems"] == len(CANONICAL_HUMANOID_JOINTS)
    Draft202012Validator.check_schema(schema)
    assert committed == render_body_motion_json_schema()


def test_facial_curve_schema_matches_models() -> None:
    schema = facial_curve_json_schema()
    committed = FACIAL_SCHEMA_PATH.read_text(encoding="utf-8")

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == FACIAL_CURVE_SCHEMA_ID
    assert schema["properties"]["curve_names"]["const"] == list(ARKIT_52_CURVES)
    weights = schema["$defs"]["FacialCurveSample"]["properties"]["weights"]
    assert weights["minItems"] == len(ARKIT_52_CURVES)
    assert weights["maxItems"] == len(ARKIT_52_CURVES)
    assert weights["items"]["minimum"] == 0.0
    assert weights["items"]["maximum"] == 1.0
    Draft202012Validator.check_schema(schema)
    assert committed == render_facial_curve_json_schema()


def test_camera_curve_schema_matches_models() -> None:
    schema = camera_curve_json_schema()
    committed = CAMERA_SCHEMA_PATH.read_text(encoding="utf-8")

    assert schema["$schema"] == JSON_SCHEMA_DIALECT
    assert schema["$id"] == CAMERA_CURVE_SCHEMA_ID
    focal = schema["$defs"]["CameraCurveSample"]["properties"]["focal_length_mm"]
    assert focal["minimum"] == 8.0
    assert focal["maximum"] == 300.0
    Draft202012Validator.check_schema(schema)
    assert committed == render_camera_curve_json_schema()


def test_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "performance-package.schema.json"

    written = write_performance_package_json_schema(destination)

    assert written == destination.resolve()
    assert destination.read_text(encoding="utf-8") == (
        render_performance_package_json_schema()
    )


def test_motion_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "body-motion.schema.json"

    written = write_body_motion_json_schema(destination)

    assert written == destination.resolve()
    assert destination.read_text(encoding="utf-8") == (render_body_motion_json_schema())


def test_facial_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "facial-curves.schema.json"

    written = write_facial_curve_json_schema(destination)

    assert written == destination.resolve()
    assert destination.read_text(encoding="utf-8") == (
        render_facial_curve_json_schema()
    )


def test_camera_schema_writer_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "camera-curves.schema.json"

    written = write_camera_curve_json_schema(destination)

    assert written == destination.resolve()
    assert destination.read_text(encoding="utf-8") == (
        render_camera_curve_json_schema()
    )
