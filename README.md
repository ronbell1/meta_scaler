---
title: Legal Contract Review
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# Legal Contract Review - OpenEnv RL Environment

## Environment Description

An RL environment simulating legal contract review at Fortune 500 companies.
The agent reads a synthetic contract and must identify all policy violations
across payment terms, IP ownership, liability caps, SLA penalties, and data privacy.

## Action Space

```python
Action(
    identified_violations: List[PolicyViolation],  # violations found
    reasoning: Optional[str]                       # optional explanation
)
```

Each `PolicyViolation` has:

- `rule_id`: string identifier (e.g. `"PAY-001"`)
- `description`: plain-English explanation
- `severity`: `"critical"` | `"high"` | `"medium"` | `"low"`
- `clause_reference`: e.g. `"Section 2"`

## Observation Space

```python
Observation(
    contract_text: str,          # full contract text
    task_name: str,
    step: int,
    last_reward: float,
    feedback: str,
    rules_to_check: List[str]
)
```

## State

```python
State(
    task_name: str,
    contract_text: str,
    gold_violations: List[PolicyViolation],
    agent_violations: List[PolicyViolation],
    step: int,
    max_steps: int,
    cumulative_reward: float,
    done: bool,
    difficulty: str
)
```

## Reward Function

- Score per step is severity-weighted violation coverage with false-positive penalty.
- `critical` = 1.0, `high` = 0.75, `medium` = 0.5, `low` = 0.25
- Partial credit uses incremental improvement:
  - `reward = max(0, current_score - previous_best_score)`
- False positives are penalized by `-0.05` each, capped at `-0.20`
- Step score and cumulative reward are bounded to `[0.0, 1.0]`

## Task Difficulty Levels

| Task                | Difficulty | Violations | Max Steps |
| ------------------- | ---------- | ---------- | --------- |
| `easy_nda_review`   | easy       | 2          | 3         |
| `medium_sla_review` | medium     | 5          | 5         |
| `hard_msa_review`   | hard       | 11         | 8         |

## Setup Instructions

```bash
uv sync
uv run server --port 7860

# Validate
curl http://localhost:7860/health
openenv validate --url http://localhost:7860 --verbose

# Docker
docker build -t legal-contract-env .
docker run -p 7860:7860 legal-contract-env

# Run inference
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your-token"
export IMAGE_NAME="legal-contract-env"
export LEGAL_ENV_TASK="easy_nda_review"
python inference.py
```

---

## 🚀 OpenEnv + Hugging Face Commands

### ✅ Validate Environment (Local)

```bash
openenv validate --url http://localhost:7860 --verbose
```

👉 Ensure this passes **before deployment**

---

### 🐳 Docker (Required for Deployment)

```bash
cd server
docker build -t my-env .
docker run -p 7860:7860 my-env
```

---

### 🤗 Hugging Face Setup

#### 1. Login

```bash
huggingface-cli login
```

---

#### 2. Deploy Environment

```bash
openenv push
```

👉 This will:

* Build Docker image
* Upload to Hugging Face Space
* Deploy your environment

---

#### 3. Test Deployed Space

```bash
curl -X POST https://<your-username>-<space-name>.hf.space/reset
```

---

### 🤖 Run Inference (Evaluator Simulation)

```bash
python inference.py
```

---

### 🔑 Required Environment Variables

```bash
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
HF_TOKEN=<your_token>
```

---

### 🧠 Deployment Flow Summary

```bash
Run Server → Validate → Docker Test → openenv push → Test HF Space
```

---
