from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

try:
    from models import Action, Observation, State
except ImportError:
    from .models import Action, Observation, State


class LegalContractClient(EnvClient[Action, Observation, State]):
    def _step_payload(self, action: Action) -> Dict[str, Any]:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[Observation]:
        obs_data = payload.get("observation", {})
        reward = payload.get("reward")
        done = payload.get("done", False)

        if "last_reward" not in obs_data:
            obs_data["last_reward"] = float(reward or 0.0)

        obs_data["reward"] = reward
        obs_data["done"] = done

        observation = Observation.model_validate(obs_data)
        return StepResult(observation=observation, reward=reward, done=done)

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        return State.model_validate(payload)
