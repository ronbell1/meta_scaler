FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir uv && uv pip install --system -e .

EXPOSE 7860

# ── Runtime config ────────────────────────────────────────────────────────────
# MODEL_NAME has a safe default; all other secrets (API_KEY, API_BASE_URL)
# are injected by the validator / HF Spaces at runtime — never hardcode them.
ENV MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Runs the OpenEnv-compliant web server (reset / step / state / health).
# The validator also runs inference.py as a separate process — it does NOT
# need to be the CMD; it is executed with the same injected env vars.
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
