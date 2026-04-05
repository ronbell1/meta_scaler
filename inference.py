"""
Inference Script - Legal Contract Review OpenEnv
===================================
MANDATORY env vars:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME  Docker image name if using from_docker_image()

STDOUT FORMAT
- Exactly three line types, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after env.close(), always emitted (even on exception).
    - reward and rewards formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw last_action_error string, or null if none.
    - All fields on a single line with no newlines within a line.
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import os
import subprocess
import textwrap
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openenv.core.containers.runtime import LocalDockerProvider

from models import PolicyViolation
from my_env import Action, LegalContractClient

API_BASE_URL = os.environ["API_BASE_URL"]
MODEL_NAME = os.environ["MODEL_NAME"]
TASK_NAME = os.getenv("LEGAL_ENV_TASK", "easy_nda_review")
BENCHMARK = "legal-contract-review"
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
TEMPERATURE = 0.2
MAX_TOKENS = 800
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.5"))


class Port7860DockerProvider(LocalDockerProvider):
    def start_container(
        self,
        image: str,
        port: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> str:
        if port is None:
            port = self._find_available_port()

        self._container_name = self._generate_container_name(image)

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self._container_name,
            "-p",
            f"{port}:7860",
        ]

        if env_vars:
            for key, value in env_vars.items():
                cmd.extend(["-e", f"{key}={value}"])

        cmd.append(image)

        print("\n🚀 Starting Docker container...")
        print("COMMAND:", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self._container_id = result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            print("❌ DOCKER ERROR:", exc.stderr)
            raise RuntimeError("Docker failed") from exc

        time.sleep(1)
        return f"http://localhost:{port}"


SYSTEM_PROMPT = """
You are a strict legal contract reviewer.

Your job is to find ALL violations in the contract.

IMPORTANT:
- Assume violations exist
- DO NOT return empty array unless absolutely certain
- Even minor issues count as violations

Return STRICT JSON only:
[
  {
    "rule_id": "...",
    "description": "...",
    "severity": "critical|high|medium|low",
    "clause_reference": "Section X"
  }
]
"""


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP]  step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}",
        flush=True,
    )


def build_user_prompt(contract_text, rules_to_check, step, feedback):
    rules_block = "\n".join(f"- {r}" for r in rules_to_check)
    return f"""
Step: {step}

CONTRACT:
{contract_text}

RULES:
{rules_block}

Find all violations. Return JSON only.
"""


def get_model_violations(client, contract_text, rules_to_check, step, feedback):
    user_prompt = build_user_prompt(contract_text, rules_to_check, step, feedback)

    print("\n===== USER PROMPT =====")
    print(user_prompt)

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        text = (completion.choices[0].message.content or "").strip()

        print("\n===== RAW MODEL OUTPUT =====")
        print(text)

        text = text.replace("```json", "").replace("```", "").strip()

        try:
            raw = json.loads(text)
        except Exception as e:
            print("❌ JSON ERROR:", e)
            return []

        print("PARSED:", raw)

        violations = []
        for item in raw:
            try:
                violations.append(PolicyViolation.model_validate(item))
            except Exception as e:
                print("❌ VALIDATION ERROR:", e)

        print("FINAL:", violations)

        return violations

    except Exception as e:
        print("❌ LLM ERROR:", e)
        return []


async def main():
    client = OpenAI(
        base_url=os.environ["API_BASE_URL"],
        api_key=os.environ["HF_TOKEN"]
    )

    image_name = os.environ.get("LOCAL_IMAGE_NAME")

    log_start(TASK_NAME, BENCHMARK, MODEL_NAME)

    env = await LegalContractClient.from_docker_image(
        image_name,
        provider=Port7860DockerProvider()
    )

    result = await env.reset(task_name=TASK_NAME)

    rewards = []
    steps = 0

    for step in range(1, MAX_STEPS + 1):
        obs = result.observation

        violations = get_model_violations(
            client,
            obs.contract_text,
            obs.rules_to_check,
            step,
            obs.feedback,
        )

        action = Action(
            identified_violations=violations,
            reasoning=f"step {step}"
        )

        result = await env.step(action)

        reward = result.reward or 0.0
        rewards.append(reward)
        steps = step

        log_step(step, f"{len(violations)}_violations", reward, result.done, None)

        if result.done:
            break

    await env.close()

    success = sum(rewards) >= SUCCESS_SCORE_THRESHOLD
    log_end(success, steps, rewards)


if __name__ == "__main__":
    asyncio.run(main())