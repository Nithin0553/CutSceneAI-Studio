#!/usr/bin/env python3
"""Compatibility launcher for the CutSceneAI HY-Motion provider.

The implementation lives in providers.hymotion.service so local, Docker, and cloud
deployments all exercise exactly one provider code path.
"""

from providers.hymotion.service import main


if __name__ == "__main__":
    main()
