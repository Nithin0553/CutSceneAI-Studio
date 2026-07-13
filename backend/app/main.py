from fastapi import FastAPI

from app.api import cir_router, director_router


app = FastAPI(title="CutSceneAI Studio API", version="0.1.0")
app.include_router(cir_router)
app.include_router(director_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
