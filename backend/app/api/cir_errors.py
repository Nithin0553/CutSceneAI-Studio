from typing import Any

from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.models.cir import CIRValidationFailure, CIRValidationProblem
from cutsceneai_cir import CIRValidationError


def format_location(location: tuple[Any, ...]) -> str:
    path = ""
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path or "$"


def structural_failure(exc: ValidationError) -> JSONResponse:
    problems = [
        CIRValidationProblem(
            code=f"structural.{error['type']}",
            path=format_location(error["loc"]),
            message=error["msg"],
        )
        for error in exc.errors(include_url=False, include_context=False, include_input=False)
    ]
    return failure_response(problems)


def domain_failure(exc: CIRValidationError) -> JSONResponse:
    return failure_response(
        [
            CIRValidationProblem(code=issue.code, path=issue.path, message=issue.message)
            for issue in exc.issues
        ]
    )


def failure_response(problems: list[CIRValidationProblem]) -> JSONResponse:
    failure = CIRValidationFailure(errors=problems)
    return JSONResponse(status_code=422, content=failure.model_dump(mode="json"))
