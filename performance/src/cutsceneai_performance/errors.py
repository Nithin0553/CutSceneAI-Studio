from __future__ import annotations


class PerformanceError(Exception):
    """Base exception for generated-performance contract failures."""


class PerformanceInputError(PerformanceError):
    """Raised when an untrusted Generated Performance bundle is invalid."""


class PerformanceOutputError(PerformanceError):
    """Raised when provider output or bundle assembly violates the contract."""
