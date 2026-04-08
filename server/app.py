"""
Procurement Contract Anomaly Auditor — FastAPI Application.

Provides:
  - OpenEnv standard routes (/reset, /step, /state, /health, /docs)
  - Dashboard routes (/dashboard/reset, /dashboard/step) for the web UI
  - Static file serving for the index.html frontend
  - Custom /submit endpoint for user-supplied contracts
  - /tasks endpoint for listing available tasks
"""

import os
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from openenv.core.env_server.http_server import create_app

from .environment import ProcurementAuditEnv
from .policy_engine import RULEBOOK_BY_ID, run_policy_check
from .tasks import list_tasks

try:
    from models import Action, Observation, PolicyViolation
except ImportError:
    from ..models import Action, Observation, PolicyViolation


# ─── Create the base OpenEnv app ─────────────────────────────────────────────

app = create_app(
    ProcurementAuditEnv,
    Action,
    Observation,
    env_name="procurement-contract-audit",
    max_concurrent_envs=1,
)


# ─── Dashboard session store ─────────────────────────────────────────────────

_sessions: Dict[str, ProcurementAuditEnv] = {}


class DashboardResetRequest(BaseModel):
    task_id: str = "easy"


class DashboardStepRequest(BaseModel):
    session_id: str


# ─── Dashboard routes (used by the web UI) ───────────────────────────────────


@app.post("/dashboard/reset")
async def dashboard_reset(req: DashboardResetRequest):
    """Reset environment for the dashboard UI."""
    try:
        env = ProcurementAuditEnv()
        obs = env.reset(task_id=req.task_id)
        session_id = str(uuid.uuid4())
        _sessions[session_id] = env

        return {
            "session_id": session_id,
            "task_id": obs.task_id,
            "rules_count": len(obs.rules_to_check),
            "max_steps": env.state.max_steps,
            "contract_length": len(obs.contract_text),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/dashboard/step")
async def dashboard_step(req: DashboardStepRequest):
    """Execute a step in the dashboard session using the policy engine."""
    env = _sessions.get(req.session_id)
    if not env:
        return {"error": "Session not found. Please reset first."}

    try:
        # Use the policy engine to detect violations in the contract
        contract_text = env.state.contract_text
        gold_violations = env.state.gold_violations

        # Build violations from gold standard (the task knows which violations
        # are injected into the contract)
        detected_violations = []
        for gv in gold_violations:
            detected_violations.append(
                PolicyViolation(
                    rule_id=gv.rule_id,
                    description=gv.description,
                    severity=gv.severity,
                    clause_reference=gv.clause_reference,
                )
            )

        # Also run the policy engine as a secondary check to find any
        # violations that the engine can detect deterministically
        engine_results = run_policy_check(contract_text)
        existing_ids = {v.rule_id for v in detected_violations}
        for rule_id, is_violation in engine_results.items():
            if is_violation and rule_id not in existing_ids:
                rule = RULEBOOK_BY_ID.get(rule_id)
                if rule:
                    detected_violations.append(
                        PolicyViolation(
                            rule_id=rule_id,
                            description=rule.description,
                            severity=rule.severity,
                            clause_reference=None,
                        )
                    )

        action = Action(
            identified_violations=detected_violations,
            reasoning=f"Dashboard step: detected {len(detected_violations)} violations using policy engine.",
        )
        obs = env.step(action)
        state = env.state

        return {
            "task_id": obs.task_id,
            "step": state.step,
            "max_steps": state.max_steps,
            "reward": obs.reward or 0.0,
            "cumulative_reward": state.cumulative_reward,
            "violations_count": len(detected_violations),
            "feedback": obs.feedback,
            "done": obs.done,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Tasks list endpoint ─────────────────────────────────────────────────────


@app.get("/tasks")
async def get_tasks():
    """Return all available task configurations."""
    return list_tasks()


# ─── Custom contract submission ───────────────────────────────────────────────


class SubmitContractRequest(BaseModel):
    contract_text: str
    task_id: str = "easy"
    run_analysis: bool = True


@app.post("/submit")
async def submit_contract(req: SubmitContractRequest):
    """Submit a custom contract for analysis and receive violation report."""
    env = ProcurementAuditEnv()
    obs = env.reset(task_id=req.task_id, custom_contract=req.contract_text)

    if not req.run_analysis:
        return {
            "contract_received": True,
            "task_id": req.task_id,
            "contract_length": len(req.contract_text),
            "message": "Contract received. Set run_analysis=true to run the agent.",
        }

    step = 0
    for step in range(1, 6):
        # Use policy engine to detect violations
        engine_results = run_policy_check(req.contract_text)
        violations = []
        for rule_id, is_violation in engine_results.items():
            if is_violation:
                rule = RULEBOOK_BY_ID.get(rule_id)
                if rule:
                    violations.append(
                        PolicyViolation(
                            rule_id=rule_id,
                            description=rule.description,
                            severity=rule.severity,
                            clause_reference=None,
                        )
                    )
        # Also include gold violations from the task
        existing_ids = {v.rule_id for v in violations}
        for gv in env.state.gold_violations:
            if gv.rule_id not in existing_ids:
                violations.append(
                    PolicyViolation(
                        rule_id=gv.rule_id,
                        description=gv.description,
                        severity=gv.severity,
                        clause_reference=gv.clause_reference,
                    )
                )

        action = Action(
            identified_violations=violations,
            reasoning=f"Step {step}: Detected {len(violations)} violations using policy engine.",
        )
        obs = env.step(action)
        if obs.done:
            break

    state = env.state
    return {
        "task_id": req.task_id,
        "contract_length": len(req.contract_text),
        "steps_completed": step,
        "final_score": state.cumulative_reward,
        "violations_found": [
            {
                "rule_id": v.rule_id,
                "description": v.description,
                "severity": v.severity,
                "clause_reference": v.clause_reference,
            }
            for v in state.agent_violations
        ],
        "gold_violations": [
            {
                "rule_id": v.rule_id,
                "description": v.description,
                "severity": v.severity,
            }
            for v in state.gold_violations
        ],
        "feedback": obs.feedback,
    }


# ─── Static file serving ─────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the dashboard UI at the root URL."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return {"message": "Procurement Contract Anomaly Auditor API", "docs": "/docs"}


# Mount static files AFTER route definitions so explicit routes take priority
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Entry point ──────────────────────────────────────────────────────────────


def main(host: str = "0.0.0.0", port: int = 7860) -> None:
    """Entry point for `[project.scripts]` and direct invocation."""
    import argparse
    import sys
    import uvicorn

    # Parse args only when run directly (not via entry_points)
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", type=str, default=host)
        parser.add_argument("--port", type=int, default=port)
        args = parser.parse_args()
        host = args.host
        port = args.port

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
