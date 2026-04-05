from typing import List, Optional, Tuple

from openenv.core.env_server.interfaces import Environment

try:
    # Primary path: CWD-based execution
    from models import Action, Observation, PolicyViolation, State
except ImportError:
    # Fallback: installed as sub-package
    from ..models import Action, Observation, PolicyViolation, State


EASY_CONTRACT = """
MASTER SERVICE AGREEMENT

1. SERVICES
   Supplier agrees to provide software development services.

2. PAYMENT TERMS
   Client shall pay invoices within 90 days of receipt.

3. CONFIDENTIALITY
   Both parties agree to keep information confidential for 1 year.

4. TERM
   This agreement is effective for 12 months.

5. GOVERNING LAW
   This agreement is governed by the laws of Delaware.
"""

MEDIUM_CONTRACT = """
SOFTWARE LICENSE AGREEMENT

1. LICENSE GRANT
   Licensor grants a non-exclusive, worldwide license.

2. PAYMENT
   Licensee shall pay $50,000 annually. Late payments incur no penalty.

3. IP OWNERSHIP
   All work product created by Supplier becomes property of Supplier.

4. LIMITATION OF LIABILITY
   Neither party limits its liability for any damages whatsoever.

5. SLA
   System availability target is 99%. No penalties defined for downtime.

6. TERMINATION
   Either party may terminate with 7 days notice.
"""

HARD_CONTRACT = """
VENDOR PURCHASE ORDER AND MSA

1. SERVICES & DELIVERABLES
   Vendor provides data analytics platform and support.

2. COMMERCIAL TERMS
   Payment due Net-120. Discounts for early payment not addressed.
   Currency fluctuation risk borne entirely by Client.

3. INTELLECTUAL PROPERTY
   All inventions, whether pre-existing or new, transfer to Vendor.
   Client receives no license to Vendor's background IP.

4. LIABILITY
   Vendor's total liability is unlimited. Client's liability is capped at $1,000.
   Consequential damages excluded only for Vendor.

5. DATA PRIVACY
   No data processing agreement referenced. GDPR obligations unaddressed.

6. SLA & PENALTIES
   Uptime target: 95%. No credits or remedies defined for breach.
   Vendor may suspend service without notice.

7. INDEMNIFICATION
   Client indemnifies Vendor for all third-party claims, including Vendor's negligence.

8. DISPUTE RESOLUTION
   All disputes resolved in Vendor's home jurisdiction exclusively.
"""


def compute_gold_violations(task_name: str) -> List[PolicyViolation]:
    if task_name == "easy_nda_review":
        return [
            PolicyViolation(
                rule_id="PAY-001",
                description="Payment terms exceed 60-day standard (90 days found)",
                severity="medium",
                clause_reference="Section 2",
            ),
            PolicyViolation(
                rule_id="CONF-001",
                description="Confidentiality period is only 1 year; minimum 3 years required",
                severity="high",
                clause_reference="Section 3",
            ),
        ]
    if task_name == "medium_sla_review":
        return [
            PolicyViolation(
                rule_id="PAY-002",
                description="No late payment penalty clause - creates collection risk",
                severity="high",
                clause_reference="Section 2",
            ),
            PolicyViolation(
                rule_id="IP-001",
                description="Work product ownership assigned to Supplier, not Client",
                severity="critical",
                clause_reference="Section 3",
            ),
            PolicyViolation(
                rule_id="LIAB-001",
                description="No mutual liability cap defined",
                severity="critical",
                clause_reference="Section 4",
            ),
            PolicyViolation(
                rule_id="SLA-001",
                description="SLA uptime target defined but no financial penalties for breach",
                severity="high",
                clause_reference="Section 5",
            ),
            PolicyViolation(
                rule_id="TERM-001",
                description="7-day termination notice is below 30-day policy minimum",
                severity="medium",
                clause_reference="Section 6",
            ),
        ]
    if task_name == "hard_msa_review":
        return [
            PolicyViolation(
                rule_id="PAY-003",
                description="Net-120 payment terms far exceed 60-day policy maximum",
                severity="high",
                clause_reference="Section 2",
            ),
            PolicyViolation(
                rule_id="PAY-004",
                description="Currency fluctuation risk entirely on Client - unacceptable",
                severity="medium",
                clause_reference="Section 2",
            ),
            PolicyViolation(
                rule_id="IP-002",
                description="Pre-existing IP transfer to Vendor - Client loses all IP rights",
                severity="critical",
                clause_reference="Section 3",
            ),
            PolicyViolation(
                rule_id="IP-003",
                description="No license back to Client on Vendor background IP",
                severity="critical",
                clause_reference="Section 3",
            ),
            PolicyViolation(
                rule_id="LIAB-002",
                description="Asymmetric liability: Vendor unlimited, Client capped at $1,000",
                severity="critical",
                clause_reference="Section 4",
            ),
            PolicyViolation(
                rule_id="LIAB-003",
                description="Consequential damages exclusion is one-sided (Vendor only)",
                severity="high",
                clause_reference="Section 4",
            ),
            PolicyViolation(
                rule_id="PRIV-001",
                description="No Data Processing Agreement (DPA) - GDPR non-compliant",
                severity="critical",
                clause_reference="Section 5",
            ),
            PolicyViolation(
                rule_id="SLA-002",
                description="95% SLA uptime is below 99.5% policy minimum",
                severity="high",
                clause_reference="Section 6",
            ),
            PolicyViolation(
                rule_id="SLA-003",
                description="No SLA credit/remedy for breach; Vendor may suspend without notice",
                severity="critical",
                clause_reference="Section 6",
            ),
            PolicyViolation(
                rule_id="INDEM-001",
                description="Client indemnifies Vendor even for Vendor's own negligence",
                severity="critical",
                clause_reference="Section 7",
            ),
            PolicyViolation(
                rule_id="DISP-001",
                description="Exclusive dispute jurisdiction favors Vendor - no neutral forum",
                severity="medium",
                clause_reference="Section 8",
            ),
        ]
    return []


TASK_CONFIG = {
    "easy_nda_review": {
        "difficulty": "easy",
        "contract": EASY_CONTRACT,
        "rules_to_check": [
            "PAY-001: Payment terms must be <= 60 days",
            "CONF-001: Confidentiality period must be >= 3 years",
        ],
        "max_steps": 3,
    },
    "medium_sla_review": {
        "difficulty": "medium",
        "contract": MEDIUM_CONTRACT,
        "rules_to_check": [
            "PAY-002: Late payment penalty clause required",
            "IP-001: Work product must assign to Client",
            "LIAB-001: Mutual liability cap required",
            "SLA-001: SLA breach penalties required",
            "TERM-001: Termination notice >= 30 days",
        ],
        "max_steps": 5,
    },
    "hard_msa_review": {
        "difficulty": "hard",
        "contract": HARD_CONTRACT,
        "rules_to_check": [
            "PAY-003: Payment terms <= 60 days",
            "PAY-004: Currency risk must be shared",
            "IP-002: No IP transfer to Vendor",
            "IP-003: License-back required on background IP",
            "LIAB-002: Symmetric liability caps",
            "LIAB-003: Mutual consequential damages exclusion",
            "PRIV-001: DPA required for GDPR compliance",
            "SLA-002: Uptime >= 99.5%",
            "SLA-003: SLA breach remedies required",
            "INDEM-001: No indemnity for counterparty negligence",
            "DISP-001: Neutral dispute forum required",
        ],
        "max_steps": 8,
    },
}


SEVERITY_WEIGHT = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}


def grade(
    agent_violations: List[PolicyViolation], gold_violations: List[PolicyViolation]
) -> Tuple[float, str]:
    if not gold_violations:
        return 1.0, "No violations expected; full score."

    gold_ids = {v.rule_id: v for v in gold_violations}
    agent_ids = {v.rule_id for v in agent_violations}

    total_weight = sum(SEVERITY_WEIGHT.get(v.severity, 0.5) for v in gold_violations)
    earned_weight = 0.0
    matched: List[str] = []
    missed: List[str] = []

    for rule_id, gold_v in gold_ids.items():
        weight = SEVERITY_WEIGHT.get(gold_v.severity, 0.5)
        if rule_id in agent_ids:
            earned_weight += weight
            matched.append(rule_id)
        else:
            missed.append(rule_id)

    score = round(earned_weight / total_weight, 4) if total_weight > 0 else 0.0

    false_positives = [v.rule_id for v in agent_violations if v.rule_id not in gold_ids]
    penalty = min(len(false_positives) * 0.05, 0.2)
    score = max(0.0, score - penalty)

    feedback = (
        f"Matched: {matched}. Missed: {missed}. "
        f"False positives: {false_positives}. "
        f"Raw score: {score:.4f}."
    )
    return score, feedback


class LegalContractEnv(Environment[Action, Observation, State]):
    """
    OpenEnv environment for legal contract policy review.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        super().__init__()
        self._state: Optional[State] = None

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_name: str = "easy_nda_review",
    ) -> Observation:
        cfg = TASK_CONFIG.get(task_name, TASK_CONFIG["easy_nda_review"])
        resolved_task_name = task_name if task_name in TASK_CONFIG else "easy_nda_review"
        gold = compute_gold_violations(resolved_task_name)

        self._state = State(
            episode_id=episode_id,
            step_count=0,
            task_name=resolved_task_name,
            contract_text=cfg["contract"],
            gold_violations=gold,
            agent_violations=[],
            step=0,
            max_steps=cfg["max_steps"],
            cumulative_reward=0.0,
            done=False,
            difficulty=cfg["difficulty"],
            task_metrics={"current_score": 0.0, "best_score": 0.0},
        )

        return Observation(
            contract_text=self._state.contract_text,
            task_name=resolved_task_name,
            step=0,
            last_reward=0.0,
            feedback="Review the contract and identify all policy violations.",
            rules_to_check=cfg["rules_to_check"],
            reward=0.0,
            done=False,
        )

    def step(self, action: Action, timeout_s: Optional[float] = None) -> Observation:
        if self._state is None:
            return self.reset()

        s = self._state
        s.step += 1
        s.step_count = s.step
        s.agent_violations = action.identified_violations

        score, feedback = grade(s.agent_violations, s.gold_violations)

        prev_best = s.cumulative_reward
        reward = max(0.0, score - prev_best)
        s.cumulative_reward = max(s.cumulative_reward, score)

        done = (s.step >= s.max_steps) or (score >= 1.0)
        s.done = done
        s.task_metrics["current_score"] = score
        s.task_metrics["best_score"] = s.cumulative_reward

        return Observation(
            contract_text=s.contract_text,
            task_name=s.task_name,
            step=s.step,
            last_reward=reward,
            feedback=feedback,
            rules_to_check=TASK_CONFIG[s.task_name]["rules_to_check"],
            reward=reward,
            done=done,
        )

    @property
    def state(self) -> State:
        if self._state is None:
            # Ensure state endpoint always returns a valid state payload.
            self.reset()
        return self._state
