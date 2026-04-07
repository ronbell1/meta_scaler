"""Integration tests for the FastAPI server endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport

from server.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200


class TestStateEndpoint:
    async def test_state_returns_200(self, client):
        response = await client.get("/state")
        assert response.status_code == 200

    async def test_state_returns_valid_json(self, client):
        response = await client.get("/state")
        data = response.json()
        assert isinstance(data, dict)


class TestResetEndpoint:
    async def test_reset_easy_returns_200(self, client):
        response = await client.post("/reset", json={"task_id": "easy"})
        assert response.status_code == 200

    async def test_reset_medium_returns_200(self, client):
        response = await client.post("/reset", json={"task_id": "medium"})
        assert response.status_code == 200

    async def test_reset_hard_returns_200(self, client):
        response = await client.post("/reset", json={"task_id": "hard"})
        assert response.status_code == 200

    async def test_reset_invalid_task_defaults_to_easy(self, client):
        response = await client.post("/reset", json={"task_id": "invalid"})
        assert response.status_code == 200
        data = response.json()
        assert data["observation"]["task_id"] == "easy"

    async def test_reset_returns_contract_text(self, client):
        response = await client.post("/reset", json={"task_id": "easy"})
        data = response.json()
        assert "contract_text" in data["observation"]
        assert len(data["observation"]["contract_text"]) > 0

    async def test_reset_returns_rules_to_check(self, client):
        response = await client.post("/reset", json={"task_id": "easy"})
        data = response.json()
        assert "rules_to_check" in data["observation"]
        assert len(data["observation"]["rules_to_check"]) > 0

    async def test_reset_returns_feedback(self, client):
        response = await client.post("/reset", json={"task_id": "easy"})
        data = response.json()
        assert "feedback" in data["observation"]

    async def test_reset_returns_step_zero(self, client):
        response = await client.post("/reset", json={"task_id": "easy"})
        data = response.json()
        assert data["observation"]["step"] == 0

    async def test_reset_returns_done_false(self, client):
        response = await client.post("/reset", json={"task_id": "easy"})
        assert response.status_code == 200
        data = response.json()
        assert "observation" in data


class TestStepEndpoint:
    async def test_step_without_reset_returns_observation(self, client):
        response = await client.post("/step", json={"action": {"identified_violations": []}})
        assert response.status_code == 200
        data = response.json()
        assert "observation" in data

    async def test_step_with_empty_violations(self, client):
        await client.post("/reset", json={"task_id": "easy"})
        response = await client.post("/step", json={"action": {"identified_violations": []}})
        assert response.status_code == 200
        data = response.json()
        assert data["observation"]["step"] == 1

    async def test_step_increments_step_count(self, client):
        await client.post("/reset", json={"task_id": "easy"})
        response1 = await client.post("/step", json={"action": {"identified_violations": []}})
        response2 = await client.post("/step", json={"action": {"identified_violations": []}})
        data1 = response1.json()
        data2 = response2.json()
        assert data2["observation"]["step"] == data1["observation"]["step"] + 1

    async def test_step_with_valid_violations(self, client):
        await client.post("/reset", json={"task_id": "easy"})
        state_resp = await client.get("/state")
        state = state_resp.json()
        violations = [
            {
                "rule_id": v["rule_id"],
                "description": v["description"],
                "severity": v["severity"],
            }
            for v in state["gold_violations"]
        ]
        response = await client.post("/step", json={"action": {"identified_violations": violations}})
        data = response.json()
        assert data["observation"]["last_reward"] > 0

    async def test_step_with_false_positives(self, client):
        await client.post("/reset", json={"task_id": "easy"})
        violations = [
            {
                "rule_id": "RULE_99",
                "description": "fake violation",
                "severity": "low",
            }
        ]
        response = await client.post("/step", json={"action": {"identified_violations": violations}})
        data = response.json()
        assert "feedback" in data["observation"]
        assert "False positives" in data["observation"]["feedback"]

    async def test_step_returns_feedback(self, client):
        await client.post("/reset", json={"task_id": "easy"})
        response = await client.post("/step", json={"action": {"identified_violations": []}})
        data = response.json()
        assert "feedback" in data["observation"]
        assert isinstance(data["observation"]["feedback"], str)

    async def test_step_returns_last_reward(self, client):
        await client.post("/reset", json={"task_id": "easy"})
        response = await client.post("/step", json={"action": {"identified_violations": []}})
        data = response.json()
        assert "last_reward" in data["observation"]
        assert isinstance(data["observation"]["last_reward"], float)
