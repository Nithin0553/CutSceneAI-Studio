from __future__ import annotations

import numpy as np

from .rotations import matrix_to_quaternion, quaternion_to_matrix, slerp_quaternion


def target_frame_count(source_frame_count: int, source_fps: float, target_fps: int) -> int:
    if source_frame_count < 1:
        raise ValueError("source_frame_count must be positive.")
    if source_fps <= 0.0 or target_fps <= 0:
        raise ValueError("frame rates must be positive.")
    if source_frame_count == 1:
        return 1
    duration_seconds = (source_frame_count - 1) / source_fps
    return int(round(duration_seconds * target_fps)) + 1


def source_position_for_target(
    *,
    source_frame_count: int,
    target_index: int,
    target_frame_count: int,
) -> tuple[int, int, float]:
    if source_frame_count == 1 or target_frame_count == 1:
        return 0, 0, 0.0
    position = target_index * (source_frame_count - 1) / (target_frame_count - 1)
    lower = int(np.floor(position))
    upper = min(lower + 1, source_frame_count - 1)
    return lower, upper, float(position - lower)


def resample_vectors(values: np.ndarray, *, source_fps: float, target_fps: int) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64)
    if source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("vector sequence must have shape [T, 3].")
    count = target_frame_count(source.shape[0], source_fps, target_fps)
    result = np.empty((count, 3), dtype=np.float32)
    for index in range(count):
        lower, upper, alpha = source_position_for_target(
            source_frame_count=source.shape[0],
            target_index=index,
            target_frame_count=count,
        )
        result[index] = ((1.0 - alpha) * source[lower] + alpha * source[upper]).astype(
            np.float32
        )
    return result


def resample_rotation_matrices(
    values: np.ndarray,
    *,
    source_fps: float,
    target_fps: int,
) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64)
    if source.ndim < 3 or source.shape[-2:] != (3, 3):
        raise ValueError("rotation sequence must end with shape [3, 3].")

    source_frames = source.shape[0]
    trailing = source.shape[1:-2]
    count = target_frame_count(source_frames, source_fps, target_fps)
    result = np.empty((count, *trailing, 3, 3), dtype=np.float64)

    flattened = source.reshape(source_frames, -1, 3, 3)
    flat_result = result.reshape(count, -1, 3, 3)

    quaternions = np.empty((source_frames, flattened.shape[1], 4), dtype=np.float64)
    for frame in range(source_frames):
        for item in range(flattened.shape[1]):
            quaternions[frame, item] = matrix_to_quaternion(flattened[frame, item])

    for index in range(count):
        lower, upper, alpha = source_position_for_target(
            source_frame_count=source_frames,
            target_index=index,
            target_frame_count=count,
        )
        for item in range(flattened.shape[1]):
            quat = slerp_quaternion(
                quaternions[lower, item],
                quaternions[upper, item],
                alpha,
            )
            flat_result[index, item] = quaternion_to_matrix(quat)

    return result
