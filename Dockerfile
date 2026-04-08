FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir uv && uv pip install --system -e .

EXPOSE 7860

# HF Spaces injects secrets as environment variables at runtime.
# API_BASE_URL and MODEL_NAME have defaults; HF_TOKEN must be set as a Space secret.
ENV API_BASE_URL=https://router.huggingface.co/v1
ENV MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
