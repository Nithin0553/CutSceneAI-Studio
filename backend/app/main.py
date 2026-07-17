from fastapi import FastAPI

from app.api import cir_router, dialogue_router, director_router, preview_router, unreal_router


app = FastAPI(title="CutSceneAI Studio API", version="0.1.0")
app.include_router(cir_router)
app.include_router(dialogue_router)
app.include_router(director_router)
app.include_router(preview_router)
app.include_router(unreal_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
