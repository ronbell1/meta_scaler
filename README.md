# Procurement Contract Anomaly Auditor — OpenEnv RL Environment

An RL environment simulating procurement contract review at Fortune 500 companies. The agent reads synthetic supplier contracts and must identify policy violations across 6 categories: Liability, Payment, IP, Data/Privacy, Termination, and Dispute Resolution.

## Why This Matters

Legal operations teams review thousands of supplier contracts per quarter — MSAs, NDAs, SLAs, SOWs, DPAs, and vendor POs. A single reviewer manually checks 30–50 policy rules per document. This environment lets AI agents learn to do it autonomously, with deterministic, verifiable rewards.

## Architecture

```
procurement-audit-env/
├── models.py              # Pydantic: Action, Observation, State, PolicyViolation
├── client.py              # OpenEnv sync client
├── inference.py           # Baseline LLM agent — [START]/[STEP]/[END] stdout
├── openenv.yaml           # OpenEnv v0.2.1 spec
├── Dockerfile             # HF Spaces deployment
├── pyproject.toml
├── server/
│   ├── app.py             # FastAPI: /reset /step /state /tasks /health
│   ├── environment.py     # Core: scenario loading, grader, reward, episode mgmt
│   ├── policy_engine.py   # 30-rule policy rulebook — deterministic checkers
│   ├── contract_gen.py    # Synthetic contract generator (MSA/NDA/SLA/SOW/DPA/PO)
│   └── tasks.py           # Easy / Medium / Hard task configs
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_policy_engine.py
│   ├── test_contract_gen.py
│   ├── test_environment.py
│   ├── test_tasks.py
│   └── test_server.py
└── README.md
```

## Action Space

```python
Action(
    identified_violations: List[PolicyViolation],  # violations found by agent
    reasoning: Optional[str]                       # optional explanation
)
```

Each `PolicyViolation` has:

- `rule_id`: string identifier (e.g. `"RULE_02"`)
- `description`: plain-English explanation
- `severity`: `"critical"` | `"high"` | `"medium"` | `"low"`
- `clause_reference`: e.g. `"Payment Terms"`

## Observation Space

```python
Observation(
    contract_text: str,          # full contract text
    task_id: str,                # easy | medium | hard
    step: int,
    last_reward: float,
    feedback: str,               # grader feedback on last action
    rules_to_check: List[str]    # policy rules to evaluate
)
```

## State

```python
State(
    task_id: str,
    contract_text: str,
    gold_violations: List[PolicyViolation],
    agent_violations: List[PolicyViolation],
    step: int,
    max_steps: int,
    cumulative_reward: float,
    done: bool,
    difficulty: str,
    task_metrics: Dict[str, float]
)
```

## Policy Rulebook — 30 Deterministic Rules

| Rule ID | Category | Severity | Description |
|---------|----------|----------|-------------|
| RULE_01 | LIABILITY | critical | Liability cap must be >= 2x annual contract value |
| RULE_02 | PAYMENT | high | Payment terms must be net-60 or better |
| RULE_03 | PAYMENT | high | Auto-renewal requires 90-day written opt-out notice |
| RULE_04 | DISPUTE | high | Governing law must be India or USA (not Singapore/UK) |
| RULE_05 | IP | critical | IP created by vendor is work-for-hire (company owns it) |
| RULE_06 | LIABILITY | critical | Indemnification must be mutual (not one-sided) |
| RULE_07 | TERMINATION | medium | Termination for convenience: minimum 30-day notice |
| RULE_08 | DATA_PRIVACY | critical | Data processing agreement required if PII is shared |
| RULE_09 | LIABILITY | critical | Limitation of liability clause must be present |
| RULE_10 | PAYMENT | high | SLA uptime commitment >= 99.5% for production services |
| RULE_11 | TERMINATION | medium | Warranty period minimum 12 months post-delivery |
| RULE_12 | DISPUTE | low | Dispute resolution: arbitration preferred over litigation |
| RULE_13 | PAYMENT | high | Late payment penalty clause required |
| RULE_14 | PAYMENT | medium | Currency fluctuation risk must be shared |
| RULE_15 | IP | critical | License-back required on vendor background IP |
| RULE_16 | LIABILITY | critical | Symmetric liability caps required |
| RULE_17 | LIABILITY | high | Mutual consequential damages exclusion |
| RULE_18 | DATA_PRIVACY | critical | Indemnification must cover data breaches |
| RULE_19 | PAYMENT | high | SLA breach penalties/credits required |
| RULE_20 | TERMINATION | medium | Vendor may not suspend service without notice |
| RULE_21 | DATA_PRIVACY | medium | Confidentiality period must be >= 3 years |
| RULE_22 | DISPUTE | low | Dispute escalation to senior management before litigation |
| RULE_23 | LIABILITY | medium | Force majeure clause must be present |
| RULE_24 | TERMINATION | low | Contract assignment requires prior written consent |
| RULE_25 | DATA_PRIVACY | medium | Client must have audit rights over vendor |
| RULE_26 | LIABILITY | medium | Vendor must maintain minimum insurance coverage |
| RULE_27 | TERMINATION | low | Key clauses must survive termination |
| RULE_28 | PAYMENT | medium | Subcontracting requires client approval |
| RULE_29 | DISPUTE | low | Export compliance clause required for software/services |
| RULE_30 | DISPUTE | low | Anti-corruption / FCPA compliance clause required |

## Reward Function

- **Violation detection**: +0.35 per correct flag with matching rule_id
- **Severity classification**: +0.10 if severity matches gold standard, +0.05 if off by one
- **Clause reference accuracy**: +0.05 if section reference matches actual location
- **False positive penalty**: -0.15 per incorrect violation flag
- **Clean clause confirmation**: +0.05 per correctly cleared compliant clause
- Severity weights: `critical` = 1.0, `high` = 0.75, `medium` = 0.5, `low` = 0.25
- Reward is incremental: `reward = max(0, current_score - previous_best_score)`
- All scores bounded to `[0.0, 1.0]`

## Task Difficulty Levels

| Task | Difficulty | Violations | Max Steps | Contract |
|------|------------|------------|-----------|----------|
| `easy` | easy | 2 | 5 | 1,500-word MSA, clearly labeled sections |
| `medium` | medium | 5 | 10 | 3,000-word MSA, numeric computation, 1 red herring |
| `hard` | hard | 3+ | 15 | Multi-document (MSA+SOW+DPA), cross-reference violations |

### Easy Task
- 2 obvious violations: payment terms net-30 (policy: net-60), auto-renewal notice 30 days (policy: 90)
- No ambiguity, no red herrings
- Expected GPT-4o zero-shot score: 0.80–0.95

### Medium Task
- 5 violations including numeric computation (6-month cap vs 2x annual)
- Governing law in disallowed jurisdiction (Singapore)
- 1 deliberate red herring (ambiguous IP clause covered by exhibit)
- Expected GPT-4o zero-shot score: 0.50–0.65

### Hard Task
- Multi-document package: MSA + SOW + DPA
- Cross-document violations (MSA indemnity exclusion + DPA PII processing)
- Agent must find, classify as CRITICAL, cite both documents, and propose redline language
- Expected GPT-4o zero-shot score: 0.25–0.40

## Synthetic Contract Generation

Contracts are generated procedurally — no real company data needed. The generator:

- Templates 6 contract types: MSA, NDA, SLA, SOW, DPA, Vendor PO
- Injects violations deterministically by rule_id
- Varies clause language across 3–5 paraphrase templates per rule area
- Controls difficulty by: number of violations, ambiguity level, cross-document references
- All scenarios seeded for reproducibility — seed 42 always produces the same contracts

## Testing

```bash
# Install dev dependencies
uv sync --all-extras

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=server --cov=models --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_policy_engine.py

# Run with verbose output
uv run pytest -v
```

## Setup Instructions

```bash
uv sync
uv run uvicorn server.app:app --host 0.0.0.0 --port 7860

# Validate
curl http://localhost:7860/health
openenv validate --url http://localhost:7860 --verbose

# Docker
docker build -t procurement-contract-env .
docker run -p 7860:7860 procurement-contract-env

# Run inference
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your-token"
export LOCAL_IMAGE_NAME="procurement-contract-env"
export PROCUREMENT_TASK="easy"
python inference.py
```

## OpenEnv + Hugging Face Commands

### Validate Environment (Local)

```bash
openenv validate --url http://localhost:7860 --verbose
```

### Docker (Required for Deployment)

```bash
docker build -t procurement-contract-env .
docker run -p 7860:7860 procurement-contract-env
```

### Hugging Face Setup

```bash
huggingface-cli login
openenv push
```

### Run Inference

```bash
python inference.py
# Or run all tasks:
export PROCUREMENT_TASK="all"
python inference.py
```

### Required Environment Variables

```bash
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
HF_TOKEN=<your_token>
```

## Key Differentiator

This environment requires **zero external infrastructure** — no K8s cluster, no real database, no external APIs. The entire reward function is deterministic Python. It runs reliably on any machine, any time, and every score is perfectly reproducible. Judges can verify results independently without any environment setup.
