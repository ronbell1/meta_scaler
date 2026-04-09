FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir uv && uv pip install --system -e .

EXPOSE 7860

# HF Spaces injects secrets as environment variables at runtime.
# API_BASE_URL and API_KEY are injected by the validator / runner.
# Do NOT hardcode API_BASE_URL here — the validator provides its own proxy URL.
ENV MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
