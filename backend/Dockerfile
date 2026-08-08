FROM python:3.11-slim

WORKDIR /app

COPY cir/pyproject.toml /packages/cir/pyproject.toml
COPY cir/src /packages/cir/src
COPY preview/pyproject.toml /packages/preview/pyproject.toml
COPY preview/src /packages/preview/src
COPY dialogue/pyproject.toml /packages/dialogue/pyproject.toml
COPY dialogue/src /packages/dialogue/src
COPY parity/pyproject.toml /packages/parity/pyproject.toml
COPY parity/src /packages/parity/src
COPY adapters/unreal/pyproject.toml /packages/unreal/pyproject.toml
COPY adapters/unreal/src /packages/unreal/src
COPY adapters/unity/pyproject.toml /packages/unity/pyproject.toml
COPY adapters/unity/src /packages/unity/src
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app

RUN pip install --no-cache-dir \
    /packages/cir \
    /packages/preview \
    /packages/dialogue \
    /packages/parity \
    /packages/unreal \
    /packages/unity \
    .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
