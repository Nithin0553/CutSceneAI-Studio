from pydantic import Field

from app.models.cir import APIModel
from cutsceneai_cir import Project
from cutsceneai_dialogue import VoiceProfile


def _default_voice() -> VoiceProfile:
    return VoiceProfile(voice="marin")


class DialogueSynthesizeRequest(APIModel):
    project: Project
    default_voice: VoiceProfile = Field(default_factory=_default_voice)
    voices: dict[str, VoiceProfile] = Field(default_factory=dict)
    replace_existing: bool = False


class DialogueFailure(APIModel):
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None
