from typing import Any, Dict, List, Literal, Optional

from openenv.core.env_server.types import Action as OpenEnvAction
from openenv.core.env_server.types import Observation as OpenEnvObservation
from openenv.core.env_server.types import State as OpenEnvState
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Score safety ──────────────────────────────────────────────────────────────
# The Scaler validator rejects any value that is exactly 0.0 or 1.0.
# We clamp every numeric field that could plausibly be read as a "score".
_EPSILON = 0.01


def _clamp_score(v: float) -> float:
    """Clamp a float strictly within (0, 1). None passes through."""
    if v <= 0.0:
        return _EPSILON
    if v >= 1.0:
        return 1.0 - _EPSILON
    return v


def _clamp_optional(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return _clamp_score(v)


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
    last_reward: float = _EPSILON
    feedback: Optional[str] = None
    rules_to_check: List[str] = Field(default_factory=list)
    reward: Optional[float] = None
    done: bool = False
    user_can_submit: bool = Field(default=True, description="Whether user can submit custom contracts")
    partial_progress: Dict[str, float] = Field(default_factory=dict, description="Partial progress per rule category")

    # Clamp all float fields that could be misread as task scores
    @field_validator("last_reward", mode="before")
    @classmethod
    def _clamp_last_reward(cls, v: Any) -> float:
        if v is None:
            return _EPSILON
        return _clamp_score(float(v))

    @field_validator("reward", mode="before")
    @classmethod
    def _clamp_reward(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        return _clamp_score(float(v))

    @field_validator("partial_progress", mode="before")
    @classmethod
    def _clamp_partial_progress(cls, v: Any) -> Dict[str, float]:
        if not isinstance(v, dict):
            return v
        return {k: _clamp_score(float(val)) for k, val in v.items()}


class State(OpenEnvState):
    """Full internal state (not fully exposed to agent)."""

    task_id: str = ""
    task_name: str = ""
    contract_text: str = ""
    gold_violations: List[PolicyViolation] = Field(default_factory=list)
    agent_violations: List[PolicyViolation] = Field(default_factory=list)
    step: int = 0
    max_steps: int = 5
    cumulative_reward: float = _EPSILON
    done: bool = False
    difficulty: str = "easy"  # easy | medium | hard
    task_metrics: Dict[str, float] = Field(default_factory=dict)

    @field_validator("cumulative_reward", mode="before")
    @classmethod
    def _clamp_cumulative(cls, v: Any) -> float:
        if v is None:
            return _EPSILON
        return _clamp_score(float(v))

    @field_validator("task_metrics", mode="before")
    @classmethod
    def _clamp_metrics(cls, v: Any) -> Dict[str, float]:
        if not isinstance(v, dict):
            return v
        return {k: _clamp_score(float(val)) for k, val in v.items()}
