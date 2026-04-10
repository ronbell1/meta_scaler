FROM python:3.11-slim

WORKDIR /app

# Install curl for health check
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir uv && uv pip install --system -e .

EXPOSE 7860

# Safe default — validator overrides at runtime
ENV MODEL_NAME=Qwen/Qwen2.5-7B-Instruct

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# HF Space: just run the server. The validator handles inference separately.
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]