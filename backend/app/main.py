from fastapi import FastAPI

app = FastAPI(title="CutSceneAI Studio API")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
