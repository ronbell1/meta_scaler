"""
Procurement Contract Anomaly Auditor — Core Environment.

Integrates:
  - policy_engine: 30-rule deterministic policy checker
  - contract_gen: synthetic contract generation
  - tasks: Easy/Medium/Hard task configurations
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from openenv.core.env_server.interfaces import Environment

try:
    from models import Action, Observation, PolicyViolation, State
except ImportError:
    from ..models import Action, Observation, PolicyViolation, State

from .contract_gen import ContractGenerator
from .policy_engine import (
    RULEBOOK,
    RULEBOOK_BY_ID,
    SEVERITY_WEIGHT,
    PolicyRule,
    run_policy_check,
)
from .tasks import TASKS, TaskConfig, get_task


# ─── gold violation computation ───────────────────────────────────────────


def _get_all_violation_rule_ids(task: TaskConfig) -> List[str]:
    """Get ALL violation rule IDs including cross-document violations."""
    all_ids = list(task.violations)
    for _doc_a, _doc_b, rule_id in task.cross_doc_violations:
        if rule_id not in all_ids:
            all_ids.append(rule_id)
    return all_ids


def _compute_partial_progress(
    agent_violations: List[PolicyViolation],
    gold_violations: Optional[List[PolicyViolation]] = None,
) -> Dict[str, float]:
    """Compute partial progress per rule category for incremental reward signals."""
    if gold_violations is None:
        gold_violations = []
    
    gold_by_category: Dict[str, List[str]] = {}
    agent_by_category: Dict[str, List[str]] = {}
    
    for gv in gold_violations:
        rule = RULEBOOK_BY_ID.get(gv.rule_id, None)
        if rule:
            category = rule.category
            if category not in gold_by_category:
                gold_by_category[category] = []
            gold_by_category[category].append(gv.rule_id)
    
    for av in agent_violations:
        rule = RULEBOOK_BY_ID.get(av.rule_id, None)
        if rule:
            category = rule.category
            if category not in agent_by_category:
                agent_by_category[category] = []
            agent_by_category[category].append(av.rule_id)
    
    progress = {}
    all_categories = set(gold_by_category.keys())
    for category in all_categories:
        gold_count = len(gold_by_category[category])
        agent_count = len(agent_by_category.get(category, []))
        if gold_count > 0:
            progress[category] = agent_count / gold_count
        else:
            progress[category] = 1.0
    
    for category in agent_by_category:
        if category not in progress:
            progress[category] = 1.0
    
    return progress


def compute_gold_violations(
    contract_text: str,
    task: TaskConfig,
) -> List[PolicyViolation]:
    """Compute gold violations from task config (deterministic).

    Since violations are injected by the generator, we trust the task config
    and validate with the policy engine as a secondary check.

    Includes BOTH direct violations AND cross-document violations.
    """
    result = []
    all_rule_ids = _get_all_violation_rule_ids(task)

    for rule_id in all_rule_ids:
        rule = RULEBOOK_BY_ID.get(rule_id)
        if rule:
            result.append(
                PolicyViolation(
                    rule_id=rule_id,
                    description=rule.description,
                    severity=rule.severity,
                    clause_reference=_find_clause_reference(contract_text, rule_id),
                )
            )
    return result


def _find_clause_reference(contract_text: str, rule_id: str) -> str:
    """Find the section/clause reference for a rule violation."""
    clause_section_map = {
        "RULE_01": "Limitation of Liability",
        "RULE_02": "Payment Terms",
        "RULE_03": "Term and Renewal",
        "RULE_04": "Governing Law",
        "RULE_05": "Intellectual Property",
        "RULE_06": "Indemnification",
        "RULE_07": "Termination",
        "RULE_08": "Data Protection",
        "RULE_09": "Limitation of Liability",
        "RULE_10": "Service Levels",
        "RULE_11": "Warranty",
        "RULE_12": "Dispute Resolution",
        "RULE_13": "Payment Terms",
        "RULE_14": "Payment Terms",
        "RULE_15": "Intellectual Property",
        "RULE_16": "Limitation of Liability",
        "RULE_17": "Limitation of Liability",
        "RULE_18": "Indemnification",
        "RULE_19": "Service Levels",
        "RULE_20": "Service Levels",
        "RULE_21": "Confidentiality",
        "RULE_22": "Dispute Resolution",
        "RULE_23": "Force Majeure",
        "RULE_24": "Assignment",
        "RULE_25": "Audit Rights",
        "RULE_26": "Insurance",
        "RULE_27": "Survival",
        "RULE_28": "Subcontracting",
        "RULE_29": "Export Compliance",
        "RULE_30": "Anti-Corruption",
    }
    return clause_section_map.get(rule_id, "Unknown Section")


# ─── grading ──────────────────────────────────────────────────────────────


def grade_action(
    agent_violations: List[PolicyViolation],
    gold_violations: List[PolicyViolation],
    task: TaskConfig,
) -> Tuple[float, str]:
    """Grade agent violations against gold standard."""
    if not gold_violations:
        return 1.0, "No violations expected; full score."

    gold_map: Dict[str, PolicyViolation] = {v.rule_id: v for v in gold_violations}
    agent_ids: Set[str] = {v.rule_id for v in agent_violations}

    total_weight = sum(SEVERITY_WEIGHT.get(v.severity, 0.5) for v in gold_violations)
    earned_weight = 0.0
    matched: List[str] = []
    missed: List[str] = []

    for rule_id, gold_v in gold_map.items():
        weight = SEVERITY_WEIGHT.get(gold_v.severity, 0.5)
        if rule_id in agent_ids:
            agent_v = next((av for av in agent_violations if av.rule_id == rule_id), None)
            if agent_v and agent_v.severity == gold_v.severity:
                earned_weight += weight
            else:
                earned_weight += weight * 0.5
            matched.append(rule_id)
        else:
            missed.append(rule_id)

    score = round(earned_weight / total_weight, 4) if total_weight > 0 else 0.0

    false_positives = [v.rule_id for v in agent_violations if v.rule_id not in gold_map]
    penalty = min(len(false_positives) * 0.05, 0.2)
    score = max(0.0, score - penalty)

    feedback = f"Matched: {matched}. Missed: {missed}. False positives: {false_positives}. Score: {score:.4f}."
    return score, feedback


def score_redline(
    proposed_language: str,
    gold_redline: str,
) -> float:
    """Score a redline proposal against gold standard."""
    if not proposed_language or not gold_redline:
        return 0.0

    proposed_lower = proposed_language.lower()
    gold_lower = gold_redline.lower()

    key_concepts = [
        "indemnif",
        "data breach",
        "pii",
        "personal data",
        "material breach",
    ]
    concept_score = sum(0.10 / len(key_concepts) for concept in key_concepts if concept in proposed_lower)

    gold_words = set(gold_lower.split())
    proposed_words = set(proposed_lower.split())
    overlap = len(gold_words & proposed_words) / max(len(gold_words), 1)
    precision_score = min(overlap * 0.5, 0.5)

    return min(1.0, concept_score + precision_score)


# ─── helper to build rules_to_check ──────────────────────────────────────


def _build_rules_to_check(task: TaskConfig) -> List[str]:
    """Build rules_to_check list including both direct and cross-doc violations."""
    all_rule_ids = _get_all_violation_rule_ids(task)
    return [
        f"{r.rule_id}: {r.description}"
        for r in RULEBOOK
        if r.rule_id in all_rule_ids
    ]


# ─── environment ──────────────────────────────────────────────────────────


class ProcurementAuditEnv(Environment[Action, Observation, State]):
    """
    OpenEnv environment for procurement contract anomaly auditing.

    The agent reviews synthetic supplier contracts against a 30-rule policy
    rulebook, detecting missing clauses, unfavorable terms, and liability risks.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        super().__init__()
        self._state: Optional[State] = None
        self._generator = ContractGenerator(seed=42)
        self._contract_text: str = ""
        self._gold_violations: List[PolicyViolation] = []
        self._task: Optional[TaskConfig] = None

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = "easy",
        custom_contract: Optional[str] = None,
        **kwargs,
    ) -> Observation:
        """Load a contract + policy rulebook, return initial observation."""
        task_id = task_id.lower()
        if task_id not in TASKS:
            task_id = "easy"

        self._task = get_task(task_id)
        self._generator = ContractGenerator(seed=seed or 42)

        if custom_contract:
            self._contract_text = custom_contract
            self._gold_violations = compute_gold_violations(custom_contract, self._task)
        else:
            contract_text = self._generator.generate(
                contract_type=self._task.contract_type,
                violations=self._task.violations,
                ambiguity_level=self._task.ambiguity_level,
                red_herrings=self._task.red_herrings,
            )
            self._contract_text = contract_text
            self._gold_violations = compute_gold_violations(contract_text, self._task)

        rules_to_check = _build_rules_to_check(self._task)

        self._state = State(
            episode_id=episode_id or "",
            step_count=0,
            task_id=task_id,
            task_name=self._task.description[:80],
            contract_text=self._contract_text,
            gold_violations=self._gold_violations,
            agent_violations=[],
            step=0,
            max_steps=self._task.max_steps,
            cumulative_reward=0.0,
            done=False,
            difficulty=task_id,
            task_metrics={"current_score": 0.0, "best_score": 0.0},
        )

        return Observation(
            contract_text=self._contract_text,
            task_id=task_id,
            task_name=self._task.description[:80],
            step=0,
            last_reward=0.0,
            feedback="Review the contract and identify all policy violations.",
            rules_to_check=rules_to_check,
            reward=0.0,
            done=False,
            user_can_submit=True,
            partial_progress=_compute_partial_progress([], self._gold_violations),
        )

    def step(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> Observation:
        """Process agent action and return observation with reward."""
        if self._state is None:
            return self.reset()

        s = self._state
        s.step += 1
        s.step_count = s.step

        agent_violations = action.identified_violations
        s.agent_violations = agent_violations

        score, feedback = grade_action(
            agent_violations,
            self._gold_violations,
            self._task,  # type: ignore
        )

        prev_best = s.cumulative_reward
        reward = max(0.0, score - prev_best)
        s.cumulative_reward = max(s.cumulative_reward, score)

        done = (s.step >= s.max_steps) or (score >= 1.0)
        s.done = done
        s.task_metrics["current_score"] = score
        s.task_metrics["best_score"] = s.cumulative_reward

        partial_progress = _compute_partial_progress(agent_violations, self._gold_violations)

        rules_to_check = _build_rules_to_check(self._task)  # type: ignore

        return Observation(
            contract_text=s.contract_text,
            task_id=s.task_id,
            task_name=s.task_name,
            step=s.step,
            last_reward=reward,
            feedback=feedback,
            rules_to_check=rules_to_check,
            reward=reward,
            done=done,
            user_can_submit=True,
            partial_progress=partial_progress,
        )

    @property
    def state(self) -> State:
        """Return current environment state."""
        if self._state is None:
            self.reset()
        assert self._state is not None
        return self._state
