"""Unit tests for the OpenEnv client wrapper (LegalContractClient)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from client import LegalContractClient
from models import Action, Observation, State, PolicyViolation


class TestStepPayload:
    def test_step_payload_excludes_none(self):
        client = LegalContractClient(base_url="http://test")
        action = Action(
            identified_violations=[],
            reasoning=None,
        )
        payload = client._step_payload(action)
        assert "reasoning" not in payload
        assert "identified_violations" in payload

    def test_step_payload_includes_reasoning(self):
        client = LegalContractClient(base_url="http://test")
        action = Action(
            identified_violations=[
                PolicyViolation(
                    rule_id="RULE_01",
                    description="test",
                    severity="high",
                )
            ],
            reasoning="Found violation in liability clause",
        )
        payload = client._step_payload(action)
        assert "reasoning" in payload
        assert payload["reasoning"] == "Found violation in liability clause"
        assert len(payload["identified_violations"]) == 1


class TestParseResult:
    def test_parse_result_basic(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "observation": {
                "contract_text": "test contract",
                "task_id": "easy",
                "step": 1,
                "rules_to_check": ["RULE_01: test"],
            },
            "reward": 0.5,
            "done": False,
        }
        result = client._parse_result(payload)
        assert result.reward == 0.5
        assert result.done is False
        assert isinstance(result.observation, Observation)
        assert result.observation.contract_text == "test contract"

    def test_parse_result_adds_last_reward_when_missing(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "observation": {
                "contract_text": "test",
                "task_id": "easy",
                "step": 1,
                "rules_to_check": [],
            },
            "reward": 0.75,
            "done": False,
        }
        result = client._parse_result(payload)
        assert result.observation.last_reward == 0.75

    def test_parse_result_preserves_existing_last_reward(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "observation": {
                "contract_text": "test",
                "task_id": "easy",
                "step": 1,
                "rules_to_check": [],
                "last_reward": 0.25,
            },
            "reward": 0.75,
            "done": False,
        }
        result = client._parse_result(payload)
        assert result.observation.last_reward == 0.25

    def test_parse_result_adds_reward_to_observation(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "observation": {
                "contract_text": "test",
                "task_id": "easy",
                "step": 1,
                "rules_to_check": [],
            },
            "reward": 0.5,
            "done": True,
        }
        result = client._parse_result(payload)
        assert result.observation.reward == 0.5
        assert result.observation.done is True

    def test_parse_result_with_violations(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "observation": {
                "contract_text": "test",
                "task_id": "easy",
                "step": 1,
                "rules_to_check": [],
            },
            "reward": 1.0,
            "done": True,
        }
        result = client._parse_result(payload)
        assert result.observation.reward == 1.0
        assert result.done is True


class TestParseState:
    def test_parse_state_basic(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "task_id": "easy",
            "contract_text": "test contract",
            "gold_violations": [],
            "agent_violations": [],
            "step": 0,
            "max_steps": 5,
            "cumulative_reward": 0.0,
            "done": False,
            "difficulty": "easy",
            "task_metrics": {"current_score": 0.0, "best_score": 0.0},
        }
        state = client._parse_state(payload)
        assert isinstance(state, State)
        assert state.task_id == "easy"
        assert state.contract_text == "test contract"
        assert state.step == 0
        assert state.max_steps == 5

    def test_parse_state_with_violations(self):
        client = LegalContractClient(base_url="http://test")
        payload = {
            "task_id": "medium",
            "contract_text": "test",
            "gold_violations": [
                {
                    "rule_id": "RULE_02",
                    "description": "test violation",
                    "severity": "high",
                    "clause_reference": "Payment Terms",
                }
            ],
            "agent_violations": [],
            "step": 2,
            "max_steps": 10,
            "cumulative_reward": 0.5,
            "done": False,
            "difficulty": "medium",
            "task_metrics": {"current_score": 0.5, "best_score": 0.5},
        }
        state = client._parse_state(payload)
        assert isinstance(state, State)
        assert len(state.gold_violations) == 1
        assert state.gold_violations[0].rule_id == "RULE_02"
        assert state.cumulative_reward == 0.5
