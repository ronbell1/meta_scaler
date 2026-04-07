import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.policy_engine import RULEBOOK, RULEBOOK_BY_ID, SEVERITY_WEIGHT
from server.contract_gen import ContractGenerator
from server.environment import ProcurementAuditEnv, grade_action, compute_gold_violations
from server.tasks import TASKS, get_task
from models import PolicyViolation, Action, Observation, State


@pytest.fixture
def contract_generator():
    return ContractGenerator(seed=42)


@pytest.fixture
def environment():
    return ProcurementAuditEnv()


@pytest.fixture
def easy_task():
    return get_task("easy")


@pytest.fixture
def medium_task():
    return get_task("medium")


@pytest.fixture
def hard_task():
    return get_task("hard")


@pytest.fixture
def sample_policy_violation():
    return PolicyViolation(
        rule_id="RULE_02",
        description="Payment terms are net-30 instead of required net-60",
        severity="high",
        clause_reference="Payment Terms",
    )


@pytest.fixture
def sample_contract_text():
    return """
PREAMBLE
This Master Service Agreement ("Agreement") is entered into as of the Effective Date.

PAYMENT TERMS
Client shall pay all invoices within thirty (30) days of receipt.

TERM AND RENEWAL
This Agreement shall automatically renew for successive one-year terms unless either party 
provides written notice of non-renewal at least thirty (30) days prior to the end of the 
then-current term.

LIMITATION OF LIABILITY
Each party's total aggregate liability under this agreement shall not exceed two times (2x) 
the annual contract value paid or payable in the twelve (12) months preceding the claim.

GOVERNING LAW
This Agreement shall be governed by and construed in accordance with the laws of Singapore.

INTELLECTUAL PROPERTY
All work product created by Vendor in the performance of this Agreement shall remain the 
property of Vendor.

INDEMNIFICATION
Client shall indemnify, defend, and hold harmless Vendor from and against any third-party 
claims arising from Client's use of the services.

TERMINATION
Either party may terminate this Agreement for convenience upon sixty (60) days' prior 
written notice to the other party.

DATA PROTECTION
Vendor may process personal data as necessary to perform the services. No separate Data 
Processing Agreement is executed.

FORCE MAJEURE
Neither party shall be liable for any failure or delay in performance due to causes beyond 
its reasonable control.

DISPUTE RESOLUTION
Any dispute arising under this Agreement shall first be submitted to good-faith negotiation 
between senior executives. If unresolved within 30 days, the dispute shall be resolved by 
binding arbitration.

ANTI-CORRUPTION
Each party represents and warrants that it has not and will not offer, pay, or promise to 
pay anything of value to any government official in violation of the FCPA.
"""
