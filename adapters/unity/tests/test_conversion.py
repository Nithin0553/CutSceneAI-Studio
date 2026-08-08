from cutsceneai_cir import Quaternion, Transform, Vector3
from cutsceneai_unity import (
    UnityQuaternion,
    UnityTransform,
    UnityVector,
    convert_position,
    convert_quaternion,
    convert_scale,
    convert_transform,
)


def test_unity_coordinate_conversion_reflects_z_axis() -> None:
    assert convert_position(Vector3(x=1, y=2, z=3)) == UnityVector(x=1, y=2, z=-3)
    assert convert_scale(Vector3(x=2, y=3, z=4)) == UnityVector(x=2, y=3, z=4)
    assert convert_quaternion(Quaternion(x=0.1, y=0.2, z=0.3, w=0.9)) == (
        UnityQuaternion(x=-0.1, y=-0.2, z=0.3, w=0.9)
    )


def test_complete_transform_conversion_is_typed() -> None:
    source = Transform(
        position=Vector3(x=-1.5, y=0.25, z=2),
        rotation=Quaternion(x=0.1, y=0.2, z=0.3, w=0.9),
        scale=Vector3(x=1, y=2, z=3),
    )

    assert convert_transform(source) == UnityTransform(
        position_m=UnityVector(x=-1.5, y=0.25, z=-2),
        rotation=UnityQuaternion(x=-0.1, y=-0.2, z=0.3, w=0.9),
        scale=UnityVector(x=1, y=2, z=3),
    )
