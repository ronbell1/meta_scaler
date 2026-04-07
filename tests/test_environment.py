"""Unit tests for the RL environment (ProcurementAuditEnv)."""

import pytest

from server.environment import ProcurementAuditEnv, grade_action, compute_gold_violations
from server.tasks import get_task
from models import PolicyViolation, Action


class TestComputeGoldViolations:
    def test_compute_gold_violations_easy_task(self, easy_task, sample_contract_text):
        violations = compute_gold_violations(sample_contract_text, easy_task)
        assert isinstance(violations, list)
        assert len(violations) == len(easy_task.violations)

    def test_compute_gold_violations_returns_policy_violations(self, easy_task, sample_contract_text):
        violations = compute_gold_violations(sample_contract_text, easy_task)
        for v in violations:
            assert isinstance(v, PolicyViolation)
            assert v.rule_id in easy_task.violations

    def test_compute_gold_violations_has_severity(self, easy_task, sample_contract_text):
        violations = compute_gold_violations(sample_contract_text, easy_task)
        for v in violations:
            assert v.severity in ("critical", "high", "medium", "low")


class TestGradeAction:
    def test_perfect_match(self, easy_task):
        gold = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
            PolicyViolation(rule_id="RULE_03", description="test", severity="high"),
        ]
        agent = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
            PolicyViolation(rule_id="RULE_03", description="test", severity="high"),
        ]
        score, feedback = grade_action(agent, gold, easy_task)
        assert score == pytest.approx(1.0, abs=0.01)
        assert "Matched" in feedback

    def test_complete_miss(self, easy_task):
        gold = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
            PolicyViolation(rule_id="RULE_03", description="test", severity="high"),
        ]
        agent = []
        score, feedback = grade_action(agent, gold, easy_task)
        assert score == 0.0
        assert "Missed" in feedback

    def test_partial_match(self, easy_task):
        gold = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
            PolicyViolation(rule_id="RULE_03", description="test", severity="high"),
        ]
        agent = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
        ]
        score, feedback = grade_action(agent, gold, easy_task)
        assert 0.0 < score < 1.0
        assert "Matched" in feedback
        assert "Missed" in feedback

    def test_false_positive_penalty(self, easy_task):
        gold = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
        ]
        agent = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
            PolicyViolation(rule_id="RULE_99", description="test", severity="low"),
        ]
        score, feedback = grade_action(agent, gold, easy_task)
        assert score < 1.0
        assert "False positives" in feedback

    def test_no_gold_violations(self, easy_task):
        gold = []
        agent = []
        score, feedback = grade_action(agent, gold, easy_task)
        assert score == 1.0
        assert "No violations expected" in feedback

    def test_wrong_severity_partial_credit(self, easy_task):
        gold = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
        ]
        agent = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="medium"),
        ]
        score, feedback = grade_action(agent, gold, easy_task)
        assert 0.0 < score < 1.0

    def test_multiple_false_positives(self, easy_task):
        gold = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
        ]
        agent = [
            PolicyViolation(rule_id="RULE_02", description="test", severity="high"),
            PolicyViolation(rule_id="RULE_98", description="test", severity="low"),
            PolicyViolation(rule_id="RULE_99", description="test", severity="low"),
            PolicyViolation(rule_id="RULE_97", description="test", severity="low"),
            PolicyViolation(rule_id="RULE_96", description="test", severity="low"),
        ]
        score, feedback = grade_action(agent, gold, easy_task)
        assert score >= 0.0
        assert score <= 1.0


class TestProcurementAuditEnv:
    def test_env_initialization(self, environment):
        assert environment is not None
        assert environment._state is None

    def test_reset_returns_observation(self, environment):
        obs = environment.reset(task_id="easy")
        assert obs is not None
        assert isinstance(obs.contract_text, str)
        assert len(obs.contract_text) > 0
        assert obs.task_id == "easy"
        assert obs.step == 0
        assert obs.last_reward == 0.0
        assert isinstance(obs.rules_to_check, list)

    def test_reset_invalid_task_defaults_to_easy(self, environment):
        obs = environment.reset(task_id="nonexistent")
        assert obs.task_id == "easy"

    def test_reset_medium_task(self, environment):
        obs = environment.reset(task_id="medium")
        assert obs.task_id == "medium"
        assert len(obs.contract_text) > 0

    def test_reset_hard_task(self, environment):
        obs = environment.reset(task_id="hard")
        assert obs.task_id == "hard"
        assert len(obs.contract_text) > 0

    def test_step_requires_reset_first(self, environment):
        action = Action(identified_violations=[])
        obs = environment.step(action)
        assert obs is not None

    def test_step_returns_observation(self, environment):
        environment.reset(task_id="easy")
        action = Action(identified_violations=[])
        obs = environment.step(action)
        assert obs is not None
        assert obs.step == 1
        assert isinstance(obs.last_reward, float)
        assert isinstance(obs.feedback, str)

    def test_step_with_correct_violations(self, environment):
        obs = environment.reset(task_id="easy")
        state = environment.state
        correct_violations = [
            PolicyViolation(
                rule_id=v.rule_id,
                description=v.description,
                severity=v.severity,
            )
            for v in state.gold_violations
        ]
        action = Action(identified_violations=correct_violations)
        obs = environment.step(action)
        assert obs.last_reward > 0
        assert obs.done is True

    def test_step_with_wrong_violations(self, environment):
        environment.reset(task_id="easy")
        wrong_violations = [
            PolicyViolation(
                rule_id="RULE_99",
                description="fake violation",
                severity="low",
            ),
        ]
        action = Action(identified_violations=wrong_violations)
        obs = environment.step(action)
        assert obs.last_reward == 0.0
        assert "False positives" in obs.feedback

    def test_step_increments_step_count(self, environment):
        environment.reset(task_id="easy")
        action = Action(identified_violations=[])
        obs1 = environment.step(action)
        assert obs1.step == 1
        obs2 = environment.step(action)
        assert obs2.step == 2

    def test_state_returns_state(self, environment):
        environment.reset(task_id="easy")
        state = environment.state
        assert state is not None
        assert state.task_id == "easy"
        assert isinstance(state.contract_text, str)
        assert isinstance(state.gold_violations, list)

    def test_state_auto_resets_if_none(self, environment):
        state = environment.state
        assert state is not None
        assert environment._state is not None

    def test_episode_done_at_max_steps(self, environment):
        environment.reset(task_id="easy")
        action = Action(identified_violations=[])
        for _ in range(5):
            obs = environment.step(action)
        assert obs.done is True

    def test_concurrent_sessions_supported(self, environment):
        assert environment.SUPPORTS_CONCURRENT_SESSIONS is True
