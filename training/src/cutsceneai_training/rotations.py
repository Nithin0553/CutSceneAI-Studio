from __future__ import annotations

import math

import numpy as np


def axis_angle_to_matrix(value: np.ndarray) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (3,):
        raise ValueError("axis-angle rotation must have shape (3,).")
    angle = float(np.linalg.norm(vector))
    if angle < 1e-12:
        return np.eye(3, dtype=np.float64)
    axis = vector / angle
    x, y, z = axis
    skew = np.array(
        [[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]],
        dtype=np.float64,
    )
    return (
        np.eye(3, dtype=np.float64)
        + math.sin(angle) * skew
        + (1.0 - math.cos(angle)) * (skew @ skew)
    )


def matrix_to_rotation_6d(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=np.float64)
    if value.shape != (3, 3):
        raise ValueError("rotation matrix must have shape (3, 3).")
    return np.array(
        [
            value[0, 0],
            value[1, 0],
            value[2, 0],
            value[0, 1],
            value[1, 1],
            value[2, 1],
        ],
        dtype=np.float32,
    )


def matrix_to_quaternion(matrix: np.ndarray) -> np.ndarray:
    m = np.asarray(matrix, dtype=np.float64)
    if m.shape != (3, 3):
        raise ValueError("rotation matrix must have shape (3, 3).")

    trace = float(np.trace(m))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quat = np.array(
            [
                (m[2, 1] - m[1, 2]) / scale,
                (m[0, 2] - m[2, 0]) / scale,
                (m[1, 0] - m[0, 1]) / scale,
                0.25 * scale,
            ],
            dtype=np.float64,
        )
    else:
        diagonal = np.diag(m)
        index = int(np.argmax(diagonal))
        if index == 0:
            scale = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
            quat = np.array(
                [
                    0.25 * scale,
                    (m[0, 1] + m[1, 0]) / scale,
                    (m[0, 2] + m[2, 0]) / scale,
                    (m[2, 1] - m[1, 2]) / scale,
                ],
                dtype=np.float64,
            )
        elif index == 1:
            scale = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
            quat = np.array(
                [
                    (m[0, 1] + m[1, 0]) / scale,
                    0.25 * scale,
                    (m[1, 2] + m[2, 1]) / scale,
                    (m[0, 2] - m[2, 0]) / scale,
                ],
                dtype=np.float64,
            )
        else:
            scale = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
            quat = np.array(
                [
                    (m[0, 2] + m[2, 0]) / scale,
                    (m[1, 2] + m[2, 1]) / scale,
                    0.25 * scale,
                    (m[1, 0] - m[0, 1]) / scale,
                ],
                dtype=np.float64,
            )
    return quat / np.linalg.norm(quat)


def quaternion_to_matrix(value: np.ndarray) -> np.ndarray:
    quat = np.asarray(value, dtype=np.float64)
    if quat.shape != (4,):
        raise ValueError("quaternion must have shape (4,).")
    quat = quat / np.linalg.norm(quat)
    x, y, z, w = quat
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def slerp_quaternion(first: np.ndarray, second: np.ndarray, alpha: float) -> np.ndarray:
    q0 = np.asarray(first, dtype=np.float64)
    q1 = np.asarray(second, dtype=np.float64)
    q0 = q0 / np.linalg.norm(q0)
    q1 = q1 / np.linalg.norm(q1)

    dot = float(np.dot(q0, q1))
    if dot < 0.0:
        q1 = -q1
        dot = -dot
    dot = float(np.clip(dot, -1.0, 1.0))

    if dot > 0.9995:
        result = q0 + alpha * (q1 - q0)
        return result / np.linalg.norm(result)

    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    first_weight = math.sin((1.0 - alpha) * theta) / sin_theta
    second_weight = math.sin(alpha * theta) / sin_theta
    result = first_weight * q0 + second_weight * q1
    return result / np.linalg.norm(result)


def canonical_basis(source_forward_axis: str) -> np.ndarray:
    if source_forward_axis == "-z":
        return np.eye(3, dtype=np.float64)
    if source_forward_axis == "+z":
        return np.diag([-1.0, 1.0, -1.0]).astype(np.float64)
    raise ValueError("source_forward_axis must be '+z' or '-z'.")


def change_rotation_basis(matrix: np.ndarray, basis: np.ndarray) -> np.ndarray:
    return basis @ matrix @ basis.T


def rotation_6d_to_matrix(value: np.ndarray) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (6,):
        raise ValueError("rotation 6D value must have shape (6,).")
    first = vector[:3]
    second = vector[3:]
    first_norm = np.linalg.norm(first)
    if first_norm < 1e-12:
        raise ValueError("rotation 6D first column has zero length.")
    first = first / first_norm
    second = second - first * float(np.dot(first, second))
    second_norm = np.linalg.norm(second)
    if second_norm < 1e-12:
        raise ValueError("rotation 6D columns are collinear.")
    second = second / second_norm
    third = np.cross(first, second)
    return np.column_stack((first, second, third))


def yaw_from_rotation_6d(value: np.ndarray) -> float:
    matrix = rotation_6d_to_matrix(value)
    forward = matrix @ np.array([0.0, 0.0, -1.0], dtype=np.float64)
    return math.atan2(-float(forward[0]), -float(forward[2]))
