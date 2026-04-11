from typing import Any, Dict, List, Literal, Optional

from openenv.core.env_server.types import Action as OpenEnvAction
from openenv.core.env_server.types import Observation as OpenEnvObservation
from openenv.core.env_server.types import State as OpenEnvState
from pydantic import BaseModel, Field


class PolicyViolation(BaseModel):
    rule_id: str
    description: str
    severity: str  # critical | high | medium | low
    clause_reference: Optional[str] = None


class Action(OpenEnvAction):
    """Agent submits a list of detected policy violations."""

    identified_violations: List[PolicyViolation] = Field(default_factory=list)
    reasoning: Optional[str] = None
    user_input: Optional[str] = Field(default=None, description="User-provided contract text or override instructions")
    custom_contract: Optional[str] = Field(default=None, description="User-supplied contract text for analysis")


class Observation(OpenEnvObservation):
    """What the agent sees each step."""

    contract_text: str
    task_id: str = ""
    task_name: str = ""
    step: int = 0
    last_reward: float = 0.0
    feedback: Optional[str] = None
    rules_to_check: List[str] = Field(default_factory=list)
    reward: Optional[float] = None
    done: bool = False
    user_can_submit: bool = Field(default=True, description="Whether user can submit custom contracts")
    partial_progress: Dict[str, float] = Field(default_factory=dict, description="Partial progress per rule category")


class State(OpenEnvState):
    """Full internal state (not fully exposed to agent)."""

    task_id: str = ""
    task_name: str = ""
    contract_text: str = ""
    gold_violations: List[PolicyViolation] = Field(default_factory=list)
    agent_violations: List[PolicyViolation] = Field(default_factory=list)
    step: int = 0
    max_steps: int = 5
    cumulative_reward: float = 0.0
    done: bool = False
    difficulty: str = "easy"  # easy | medium | hard
    task_metrics: Dict[str, float] = Field(default_factory=dict)
