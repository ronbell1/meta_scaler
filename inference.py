"""
Inference Script - Procurement Contract Anomaly Auditor OpenEnv
===============================================================
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

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import asyncio
import json
import os
import re
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
TASK_NAME = os.getenv("PROCUREMENT_TASK", "easy")
BENCHMARK = "procurement-contract-audit"
MAX_STEPS = int(os.getenv("MAX_STEPS", "10"))
TEMPERATURE = 0.0
MAX_TOKENS = 4096
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

        print("\nStarting Docker container...")
        print("COMMAND:", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self._container_id = result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            print("DOCKER ERROR:", exc.stderr)
            raise RuntimeError("Docker failed") from exc

        time.sleep(1)
        return f"http://localhost:{port}"


SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert legal contract compliance auditor for Fortune 500 procurement.

Your task is to review a supplier contract against a specific set of policy rules and identify ALL violations.

## INSTRUCTIONS
1. Read the contract text carefully, clause by clause.
2. Check EACH rule in the provided rules list against the contract.
3. For each rule, determine if the contract violates it.
4. A violation exists when the contract does NOT meet the policy requirement stated in the rule.
5. You MUST use the EXACT rule_id from the rules list (e.g., "RULE_01", "RULE_14").
6. Be thorough — missing a real violation is worse than a false positive.
7. If you received feedback from a previous attempt, use it to correct your answer.

## SEVERITY GUIDELINES
- "critical": Missing clauses that create major legal/financial exposure
- "high": Terms that significantly deviate from policy
- "medium": Moderate deviations from policy standards
- "low": Minor issues with limited business impact

## OUTPUT FORMAT
Return ONLY a valid JSON array. No markdown, no code fences, no explanation outside the JSON.
Each element must have exactly these fields:
[
  {
    "rule_id": "<exact rule_id from the rules list, e.g. RULE_02>",
    "description": "<specific explanation of what the contract says vs what the policy requires>",
    "severity": "<critical|high|medium|low>",
    "clause_reference": "<Section name where the violation appears>"
  }
]

IMPORTANT: Use the EXACT rule_id values from the rules list. Do NOT invent new rule IDs.
""")


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
    rules_block = "\n".join(f"  {i + 1}. {r}" for i, r in enumerate(rules_to_check))

    prompt_parts = []

    prompt_parts.append(f"## CONTRACT TEXT\n{contract_text.strip()}")

    prompt_parts.append(f"""## POLICY RULES TO CHECK
Check EACH of the following rules against the contract. For every rule that is violated, include it in your output with the EXACT rule_id shown:
{rules_block}""")

    if feedback and step > 1 and "Review the contract" not in feedback:
        prompt_parts.append(f"""## FEEDBACK FROM PREVIOUS ATTEMPT (Step {step - 1})
{feedback}

IMPORTANT: Carefully review the feedback above. If violations were "Missed", you MUST find and include them this time. If there were "False positives", remove those from your answer. Keep all previously "Matched" violations.""")

    prompt_parts.append(f"""## TASK
Analyze the contract against ALL {len(rules_to_check)} rules listed above.
Return a JSON array with one entry per violation found. Use the EXACT rule_id values from the rules list.""")

    return "\n\n".join(prompt_parts)


def extract_json_from_text(text: str) -> Optional[list]:
    """Robustly extract JSON array from model output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    bracket_match = re.search(r"\[[\s\S]*\]", text)
    if bracket_match:
        try:
            result = json.loads(bracket_match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    objects = re.findall(r"\{[^{}]*\}", text)
    if objects:
        results = []
        for obj_str in objects:
            try:
                results.append(json.loads(obj_str))
            except json.JSONDecodeError:
                continue
        if results:
            return results

    return None


def get_model_violations(client, contract_text, rules_to_check, step, feedback):
    user_prompt = build_user_prompt(contract_text, rules_to_check, step, feedback)

    print("\n===== USER PROMPT =====")
    print(user_prompt[:500] + "..." if len(user_prompt) > 500 else user_prompt)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n--- LLM call attempt {attempt}/{max_retries} ---")
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

            raw = extract_json_from_text(text)
            if raw is None:
                print("JSON EXTRACTION FAILED - no valid JSON found in output")
                return []

            print("PARSED:", raw)

            violations = []
            valid_rule_ids = set()
            for rule in rules_to_check:
                rule_id = rule.split(":")[0].strip()
                valid_rule_ids.add(rule_id)

            for item in raw:
                try:
                    normalized = {}
                    normalized["rule_id"] = item.get("rule_id", "UNKNOWN")
                    normalized["description"] = item.get("description", item.get("reasoning", ""))
                    normalized["severity"] = item.get("severity", "medium").lower()
                    normalized["clause_reference"] = item.get("clause_reference", item.get("section", None))

                    if normalized["severity"] not in ("critical", "high", "medium", "low"):
                        normalized["severity"] = "medium"

                    violation = PolicyViolation.model_validate(normalized)

                    if violation.rule_id in valid_rule_ids:
                        violations.append(violation)
                    else:
                        print(f"Skipping unknown rule_id: {violation.rule_id} (valid: {valid_rule_ids})")

                except Exception as e:
                    print(f"VALIDATION ERROR: {e}")

            print(f"FINAL: {len(violations)} violations (from {len(raw)} raw items)")
            for v in violations:
                print(f"  - {v.rule_id}: {v.description[:80]}... [{v.severity}]")

            return violations

        except Exception as e:
            print(f"LLM ERROR (attempt {attempt}/{max_retries}): {type(e).__name__}: {e}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("All retries exhausted.")
                return []


async def run_task(task_id: str):
    """Run a single task and return results."""
    client = OpenAI(
        base_url=os.environ["API_BASE_URL"],
        api_key=os.environ["HF_TOKEN"],
        timeout=60.0,
    )
    image_name = os.environ.get("LOCAL_IMAGE_NAME", "my-env")

    log_start(task_id, BENCHMARK, MODEL_NAME)

    env = await LegalContractClient.from_docker_image(image_name, provider=Port7860DockerProvider())

    result = await env.reset(task_id=task_id)

    rewards = []
    steps = 0
    best_violations = []

    for step in range(1, MAX_STEPS + 1):
        obs = result.observation

        violations = get_model_violations(
            client,
            obs.contract_text,
            obs.rules_to_check,
            step,
            obs.feedback,
        )

        if step > 1 and best_violations:
            existing_ids = {v.rule_id for v in violations}
            for prev_v in best_violations:
                if prev_v.rule_id not in existing_ids:
                    violations.append(prev_v)

        action = Action(
            identified_violations=violations,
            reasoning=f"Step {step}: Identified {len(violations)} violations by checking each policy rule against contract clauses.",
        )

        result = await env.step(action)

        reward = result.reward or 0.0
        rewards.append(reward)
        steps = step

        if reward > 0 or step == 1:
            best_violations = violations.copy()

        log_step(step, f"{len(violations)}_violations", reward, result.done, None)

        if result.done:
            break

    await env.close()

    success = sum(rewards) >= SUCCESS_SCORE_THRESHOLD
    log_end(success, steps, rewards)

    return success, sum(rewards), steps


async def main():
    """Run all tasks or a single task based on env var."""
    task_id = os.getenv("PROCUREMENT_TASK", "easy")

    if task_id == "all":
        for tid in ["easy", "medium", "hard"]:
            print(f"\n{'=' * 60}")
            print(f"Running task: {tid}")
            print(f"{'=' * 60}")
            success, total_reward, steps = await run_task(tid)
            print(f"\nTask {tid}: success={success}, total_reward={total_reward:.2f}, steps={steps}")
    else:
        await run_task(task_id)


if __name__ == "__main__":
    asyncio.run(main())
