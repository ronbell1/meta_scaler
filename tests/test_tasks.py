"""Unit tests for task configurations."""

import pytest

from server.tasks import TASKS, TaskConfig, get_task, list_tasks


class TestTaskConfig:
    def test_task_config_creation(self):
        config = TaskConfig(
            task_id="test",
            description="Test task",
            contract_type="MSA",
            violations=["RULE_01"],
        )
        assert config.task_id == "test"
        assert config.max_steps == 5
        assert config.red_herrings == 0
        assert config.ambiguity_level == 0
        assert config.cross_doc_violations == []


class TestTasksDictionary:
    def test_tasks_has_three_difficulty_levels(self):
        assert set(TASKS.keys()) == {"easy", "medium", "hard"}

    def test_easy_task_config(self):
        task = TASKS["easy"]
        assert task.task_id == "easy"
        assert task.contract_type == "MSA"
        assert len(task.violations) == 2
        assert task.max_steps == 5
        assert task.red_herrings == 0
        assert task.ambiguity_level == 0
        assert "RULE_02" in task.violations
        assert "RULE_03" in task.violations

    def test_medium_task_config(self):
        task = TASKS["medium"]
        assert task.task_id == "medium"
        assert task.contract_type == "MSA"
        assert len(task.violations) == 5
        assert task.max_steps == 10
        assert task.red_herrings == 1
        assert task.ambiguity_level == 1

    def test_hard_task_config(self):
        task = TASKS["hard"]
        assert task.task_id == "hard"
        assert task.contract_type == "MSA"
        assert len(task.violations) == 3
        assert task.max_steps == 15
        assert task.red_herrings == 1
        assert task.ambiguity_level == 2
        assert len(task.cross_doc_violations) > 0

    def test_all_tasks_have_valid_violations(self):
        from server.policy_engine import RULEBOOK_BY_ID

        for task_id, task in TASKS.items():
            for rule_id in task.violations:
                assert rule_id in RULEBOOK_BY_ID, f"{task_id} has invalid violation: {rule_id}"

    def test_all_tasks_have_descriptions(self):
        for task_id, task in TASKS.items():
            assert len(task.description) > 0

    def test_all_tasks_have_reward_breakdown(self):
        for task_id, task in TASKS.items():
            assert task.reward_breakdown is not None
            assert isinstance(task.reward_breakdown, dict)

    def test_all_tasks_have_expected_score_range(self):
        for task_id, task in TASKS.items():
            assert task.expected_score_range is not None
            low, high = task.expected_score_range
            assert low < high
            assert 0.0 <= low <= 1.0
            assert 0.0 <= high <= 1.0


class TestGetTask:
    def test_get_easy_task(self):
        task = get_task("easy")
        assert task.task_id == "easy"

    def test_get_medium_task(self):
        task = get_task("medium")
        assert task.task_id == "medium"

    def test_get_hard_task(self):
        task = get_task("hard")
        assert task.task_id == "hard"

    def test_get_task_case_sensitivity(self):
        with pytest.raises(ValueError):
            get_task("EASY")

    def test_get_task_invalid_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            get_task("nonexistent")
        assert "Unknown task_id" in str(exc_info.value)
        assert "easy" in str(exc_info.value)


class TestListTasks:
    def test_list_tasks_returns_dict(self):
        result = list_tasks()
        assert isinstance(result, dict)
        assert set(result.keys()) == {"easy", "medium", "hard"}

    def test_list_tasks_contains_expected_fields(self):
        result = list_tasks()
        for task_id, metadata in result.items():
            assert "task_id" in metadata
            assert "description" in metadata
            assert "contract_type" in metadata
            assert "num_violations" in metadata
            assert "max_steps" in metadata
            assert "ambiguity_level" in metadata
            assert "red_herrings" in metadata
            assert "reward_breakdown" in metadata
            assert "expected_score_range" in metadata

    def test_list_tasks_num_violations_matches(self):
        result = list_tasks()
        for task_id, metadata in result.items():
            task = TASKS[task_id]
            assert metadata["num_violations"] == len(task.violations)
