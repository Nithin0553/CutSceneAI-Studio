using System;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class CutSceneAIRobotKyleHumanoidPoseDiagnostic
{
    private const string PrefabPath =
        "Assets/Starter Assets/Runtime/SpaceRobotKyle/Prefabs/RobotKyle.prefab";

    [MenuItem("CutSceneAI/Diagnostics/Run RobotKyle Humanoid Pose Smoke Test")]
    public static void Run()
    {
        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
        if (prefab == null)
            throw new InvalidOperationException("RobotKyle prefab was not found at: " + PrefabPath);

        GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        if (instance == null)
            throw new InvalidOperationException("RobotKyle prefab could not be instantiated.");

        try
        {
            Animator animator = instance.GetComponentInChildren<Animator>();
            if (animator == null)
                throw new InvalidOperationException("RobotKyle has no Animator.");

            if (animator.avatar == null)
                throw new InvalidOperationException("RobotKyle Animator has no Avatar.");

            if (!animator.avatar.isValid || !animator.avatar.isHuman)
                throw new InvalidOperationException(
                    "RobotKyle Avatar must be a valid Humanoid Avatar.");

            Transform upperArm = animator.GetBoneTransform(HumanBodyBones.LeftUpperArm);
            if (upperArm == null)
                throw new InvalidOperationException(
                    "RobotKyle Humanoid mapping has no LeftUpperArm bone.");

            int muscleIndex = Enumerable.Range(0, HumanTrait.MuscleCount)
                .FirstOrDefault(index =>
                    HumanTrait.MuscleName[index].StartsWith(
                        "Left Arm",
                        StringComparison.OrdinalIgnoreCase));

            if (muscleIndex < 0
                || muscleIndex >= HumanTrait.MuscleCount
                || !HumanTrait.MuscleName[muscleIndex].StartsWith(
                    "Left Arm",
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "Could not find a Left Arm Humanoid muscle.");
            }

            animator.runtimeAnimatorController = null;
            animator.applyRootMotion = false;

            HumanPoseHandler handler =
                new HumanPoseHandler(animator.avatar, animator.transform);

            HumanPose before = new HumanPose();
            handler.GetHumanPose(ref before);
            if (before.muscles == null
                || before.muscles.Length != HumanTrait.MuscleCount)
            {
                throw new InvalidOperationException(
                    "HumanPoseHandler did not return a complete muscle array.");
            }

            float beforeMuscle = before.muscles[muscleIndex];
            Quaternion beforeBoneRotation = upperArm.localRotation;

            HumanPose target = new HumanPose
            {
                bodyPosition = before.bodyPosition,
                bodyRotation = before.bodyRotation,
                muscles = (float[])before.muscles.Clone(),
            };

            float positiveTarget = Mathf.Clamp(beforeMuscle + 0.35f, -0.9f, 0.9f);
            float negativeTarget = Mathf.Clamp(beforeMuscle - 0.35f, -0.9f, 0.9f);
            target.muscles[muscleIndex] =
                Mathf.Abs(positiveTarget - beforeMuscle)
                >= Mathf.Abs(negativeTarget - beforeMuscle)
                    ? positiveTarget
                    : negativeTarget;

            handler.SetHumanPose(ref target);

            HumanPose after = new HumanPose();
            handler.GetHumanPose(ref after);

            float muscleDelta =
                Mathf.Abs(after.muscles[muscleIndex] - beforeMuscle);
            float boneDeltaDegrees =
                Quaternion.Angle(beforeBoneRotation, upperArm.localRotation);

            Debug.Log(
                "CUTSCENEAI_HUMANOID_POSE_DIAGNOSTIC "
                + "muscle='" + HumanTrait.MuscleName[muscleIndex] + "' "
                + "before=" + beforeMuscle.ToString("F6") + " "
                + "after=" + after.muscles[muscleIndex].ToString("F6") + " "
                + "muscle_delta=" + muscleDelta.ToString("F6") + " "
                + "left_upper_arm_delta_deg=" + boneDeltaDegrees.ToString("F6"));

            if (muscleDelta < 0.01f)
                throw new InvalidOperationException(
                    "HumanPoseHandler accepted the pose call but the requested "
                    + "Humanoid muscle did not change.");

            if (boneDeltaDegrees < 0.1f)
                throw new InvalidOperationException(
                    "Humanoid muscle changed but the mapped LeftUpperArm transform "
                    + "did not move.");

            Debug.Log("CUTSCENEAI_HUMANOID_POSE=PASS");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(instance);
        }
    }
}
