"""
Task Configurations — Easy / Medium / Hard procurement audit tasks.

Each task defines:
  - task_id: unique identifier
  - description: what the agent should do
  - contract_type: which contract(s) to generate
  - violations: which rules are violated in the contract
  - cross_doc_violations: (doc_a, doc_b, rule_id) for multi-doc tasks
  - max_steps: maximum steps allowed
  - red_herrings: number of deliberate compliant clauses that look suspicious
  - ambiguity_level: 0 (none) to 2 (high)
  - reward_breakdown: scoring rubric
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TaskConfig:
    task_id: str
    description: str
    contract_type: str
    violations: List[str]
    cross_doc_violations: List[Tuple[str, str, str]] = field(default_factory=list)
    max_steps: int = 5
    red_herrings: int = 0
    ambiguity_level: int = 0
    # NOTE: reward_breakdown is informational/documentation only.
    # Actual scoring is performed by grade_action() in environment.py
    # using severity-weighted matching, NOT these per-component weights.
    reward_breakdown: Optional[Dict[str, float]] = None
    expected_score_range: Optional[Tuple[float, float]] = None


TASKS: Dict[str, TaskConfig] = {
    "easy": TaskConfig(
        task_id="easy",
        description=(
            "Agent receives a 1,500-word MSA with clearly labeled sections. "
            "2 violations: payment terms say net-30 (policy requires net-60), "
            "auto-renewal notice is 30 days (policy requires 90). "
            "Both are in clearly labeled 'Payment Terms' and 'Renewal' sections. "
            "No ambiguity, no red herrings. Agent must find both, classify them "
            "correctly, and state which rule they violate."
        ),
        contract_type="MSA",
        violations=["RULE_02", "RULE_03"],
        max_steps=5,
        red_herrings=0,
        ambiguity_level=0,
        reward_breakdown={
            "violation_detection_per_violation": 0.35,
            "severity_classification_per_violation": 0.10,
            "clause_reference_accuracy_per_violation": 0.05,
            "false_positive_penalty": -0.15,
            "clean_clause_confirmation": 0.05,
        },
        expected_score_range=(0.80, 0.95),
    ),
    "medium": TaskConfig(
        task_id="medium",
        description=(
            "A 3,000-word MSA. Liability cap clause reads: 'limited to fees paid in "
            "the preceding 6 months' — agent must compute whether this meets the 2x "
            "annual value threshold (it doesn't, for any contract > 3 months). "
            "Governing law is 'Singapore' — agent must check if this is in the "
            "allowed list (it's not). One clause looks like a violation (IP assignment "
            "language is ambiguous) but is actually covered by an exhibit. Agent must "
            "not flag the red herring."
        ),
        contract_type="MSA",
        violations=["RULE_01", "RULE_04", "RULE_13", "RULE_19", "RULE_20"],
        max_steps=10,
        red_herrings=1,
        ambiguity_level=1,
        reward_breakdown={
            "violation_recall_per_violation": 0.12,
            "severity_accuracy_per_violation": 0.05,
            "red_herring_avoidance": 0.10,
            "numeric_computation_accuracy": 0.10,
            "false_positive_penalty": -0.10,
        },
        expected_score_range=(0.50, 0.65),
    ),
    "hard": TaskConfig(
        task_id="hard",
        description=(
            "A 5,000-word contract package: MSA + Statement of Work (SOW) + Data "
            "Processing Agreement (DPA). The critical violation only appears when "
            "combining MSA clause 12.4 ('indemnification excludes data breaches') with "
            "DPA Section 3 ('vendor processes PII'). Together, this means the company "
            "has no indemnification coverage for data breaches involving PII — a "
            "critical gap. Agent must: find it, classify it as CRITICAL, cite both "
            "documents, and propose replacement clause language scored against a "
            "lawyer-written gold redline."
        ),
        contract_type="MSA",
        violations=["RULE_01", "RULE_06", "RULE_07", "RULE_08", "RULE_09", "RULE_11"],
        cross_doc_violations=[
            ("MSA", "DPA", "RULE_18"),
        ],
        max_steps=15,
        red_herrings=1,
        ambiguity_level=2,
        reward_breakdown={
            "violation_recall_per_violation": 0.10,
            "severity_accuracy_per_violation": 0.05,
            "cross_document_detection": 0.15,
            "redline_coverage": 0.10,
            "redline_precision": 0.05,
            "redline_legal_concepts": 0.10,
            "redline_mutuality": 0.05,
            "red_herring_avoidance": 0.10,
            "false_positive_penalty": -0.10,
        },
        expected_score_range=(0.25, 0.40),
    ),
}


def get_task(task_id: str) -> TaskConfig:
    """Get a task config by ID."""
    if task_id not in TASKS:
        raise ValueError(f"Unknown task_id: {task_id}. Available: {list(TASKS.keys())}")
    return TASKS[task_id]


def list_tasks() -> Dict[str, Dict]:
    """Return task metadata for the /tasks endpoint."""
    return {
        tid: {
            "task_id": cfg.task_id,
            "description": cfg.description,
            "contract_type": cfg.contract_type,
            "num_violations": len(cfg.violations),
            "max_steps": cfg.max_steps,
            "ambiguity_level": cfg.ambiguity_level,
            "red_herrings": cfg.red_herrings,
            "reward_breakdown": cfg.reward_breakdown,
            "expected_score_range": cfg.expected_score_range,
        }
        for tid, cfg in TASKS.items()
    }
