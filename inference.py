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

import asyncio
import json
import os
import re
import subprocess
import textwrap
import time
from typing import Any, Dict, List, Optional

# Only load .env as a fallback for LOCAL development.
# The validator / CI runner injects its own env vars (API_BASE_URL, API key)
# BEFORE the process starts, so we must NOT override them.
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)  # never override existing env vars

from openai import OpenAI
from openenv.core.containers.runtime import LocalDockerProvider

from models import PolicyViolation
from my_env import Action, LegalContractClient


def _resolve_api_key() -> str:
    """Return the API key from whichever env var the runner provided.

    Priority order: API_KEY > OPENAI_API_KEY > HF_TOKEN
    The validator injects API_KEY; it MUST be checked first and is the
    only key that routes through the LiteLLM proxy.
    """
    for var in ("API_KEY", "OPENAI_API_KEY", "HF_TOKEN"):
        val = os.environ.get(var)
        if val:
            print(f"[CONFIG] Using API key from {var}")
            return val
    raise EnvironmentError(
        "No API key found. Set one of: API_KEY, OPENAI_API_KEY, HF_TOKEN"
    )


# API_BASE_URL MUST come from the environment — the validator injects its own
# LiteLLM proxy URL here.  We provide the HF router ONLY as a last-resort
# local-dev fallback; production runs will always have this injected.
_raw_base_url = os.environ.get("API_BASE_URL", "")
if not _raw_base_url:
    print(
        "[WARNING] API_BASE_URL not set — falling back to HF router for local dev. "
        "The validator must inject API_BASE_URL for proxy routing to work.",
        flush=True,
    )
    _raw_base_url = "https://router.huggingface.co/v1"
API_BASE_URL = _raw_base_url
API_KEY = _resolve_api_key()
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
TASK_NAME = os.getenv("PROCUREMENT_TASK", "easy")
BENCHMARK = "procurement-contract-audit"
MAX_STEPS = int(os.getenv("MAX_STEPS", "10"))
TEMPERATURE = 0.0
MAX_TOKENS = 4096
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.5"))

# Force the OpenAI SDK's auto-detected env vars to match our resolved values.
# This prevents the SDK from silently using a different key or base URL
# that was set elsewhere in the environment (e.g. OPENAI_API_KEY from HF).
os.environ["OPENAI_API_KEY"] = API_KEY
os.environ["OPENAI_BASE_URL"] = API_BASE_URL

# Debug: show which endpoint and key prefix are in use
print(f"[CONFIG] API_BASE_URL = {API_BASE_URL}")
print(f"[CONFIG] MODEL_NAME   = {MODEL_NAME}")
print(f"[CONFIG] API_KEY       = {API_KEY[:8]}...{API_KEY[-4:]}")


class Port7860DockerProvider(LocalDockerProvider):
    MAX_RETRIES = 3
    HEALTH_TIMEOUT = 30  # seconds to wait for container to become healthy

    def _cleanup_existing_container(self, name: str) -> None:
        """Remove any existing container with the given name (stopped or running)."""
        try:
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True, text=True, check=False,
            )
        except Exception:
            pass  # Container may not exist — that's fine

    def _wait_for_healthy(self, url: str, timeout: int = 30) -> bool:
        """Poll the container's /health endpoint until it responds or timeout."""
        import urllib.request
        import urllib.error

        health_url = f"{url}/health"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                req = urllib.request.urlopen(health_url, timeout=3)
                if req.status == 200:
                    print(f"Container healthy at {health_url}")
                    return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(1)
        print(f"WARNING: Container not healthy after {timeout}s at {health_url}")
        return False

    def start_container(
        self,
        image: str,
        port: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> str:
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            if port is None:
                port = self._find_available_port()

            self._container_name = self._generate_container_name(image)

            # Remove any leftover container with the same name
            self._cleanup_existing_container(self._container_name)

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

            print(f"\nStarting Docker container (attempt {attempt}/{self.MAX_RETRIES})...")
            print("COMMAND:", " ".join(cmd))

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                self._container_id = result.stdout.strip()
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr or ""
                print(f"DOCKER ERROR (attempt {attempt}): {stderr}")
                last_error = exc

                # If it's a port conflict, try again with a new port
                if "port is already allocated" in stderr or "address already in use" in stderr:
                    port = None  # will pick a new port on next attempt
                    continue
                # If it's a name conflict (shouldn't happen after cleanup, but just in case)
                if "is already in use by container" in stderr:
                    self._cleanup_existing_container(self._container_name)
                    continue
                # Unknown error — don't retry
                raise RuntimeError(f"Docker failed: {stderr}") from exc

            url = f"http://localhost:{port}"

            # Wait for the container to be reachable before returning
            self._wait_for_healthy(url, timeout=self.HEALTH_TIMEOUT)

            return url

        raise RuntimeError(
            f"Docker failed after {self.MAX_RETRIES} attempts"
        ) from last_error


SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert legal contract compliance auditor for Fortune 500 procurement.

Your task is to review a supplier contract against a set of policy rules and identify ONLY the rules that are actually violated.

## INSTRUCTIONS
1. Read the contract text carefully, clause by clause.
2. Check EACH rule in the provided rules list against the contract.
3. For each rule, determine if the contract VIOLATES it by failing to meet the policy requirement.
4. Only include a rule in your output if you find a CLEAR violation — do NOT flag rules that the contract complies with.
5. A violation exists when the contract does NOT meet the policy requirement stated in the rule.
6. You MUST use the EXACT rule_id from the rules list (e.g., "RULE_01", "RULE_14").
7. You MUST use the EXACT severity shown in brackets [severity=X] in the rules list — do NOT guess severities.
8. Be thorough — missing a real violation is worse than a false positive, but false positives are also penalized.
9. If you received feedback from a previous attempt, use it to correct your answer.

## SEVERITY — USE EXACTLY AS SPECIFIED IN THE RULES LIST
Each rule in the list shows its required severity in [severity=X] brackets.
You MUST copy this exact severity value into your output. Do not change it.

## OUTPUT FORMAT
Return ONLY a valid JSON array. No markdown, no code fences, no explanation outside the JSON.
Include ONLY rules that are violated. Do NOT include rules the contract complies with.
Each element must have exactly these fields:
[
  {
    "rule_id": "<exact rule_id from the rules list, e.g. RULE_02>",
    "description": "<specific explanation of what the contract says vs what the policy requires>",
    "severity": "<copy EXACTLY from the [severity=X] shown next to the rule_id>",
    "clause_reference": "<Section name where the violation appears>"
  }
]

IMPORTANT: Use the EXACT rule_id AND severity values from the rules list. Do NOT invent new rule IDs or change severities. Only report ACTUAL violations.
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
    # score is the total cumulative reward clamped to [0.0, 1.0] as required
    score = min(1.0, max(0.0, sum(rewards)))
    print(
        f"[END]   success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
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

            # Parse valid rule IDs and their expected severities from rules_to_check.
            # Format: "RULE_02 [severity=high]: Payment terms must be net-60 or better"
            valid_rule_ids: set = set()
            rule_severity_map: dict = {}
            for rule in rules_to_check:
                # Extract rule_id: everything before the first space or colon
                rule_id = rule.split(" ")[0].strip().split(":")[0].strip()
                valid_rule_ids.add(rule_id)
                # Extract expected severity from [severity=X] bracket
                sev_match = re.search(r"\[severity=(\w+)\]", rule)
                if sev_match:
                    rule_severity_map[rule_id] = sev_match.group(1).lower()

            print(f"Valid rule IDs: {valid_rule_ids}")
            print(f"Expected severities: {rule_severity_map}")

            violations = []
            for item in raw:
                try:
                    normalized = {}
                    raw_rule_id = item.get("rule_id", "UNKNOWN").strip()
                    normalized["rule_id"] = raw_rule_id
                    normalized["description"] = item.get("description", item.get("reasoning", ""))
                    normalized["clause_reference"] = item.get("clause_reference", item.get("section", None))

                    # Always use the expected severity from the rules list (guarantees full credit)
                    if raw_rule_id in rule_severity_map:
                        normalized["severity"] = rule_severity_map[raw_rule_id]
                    else:
                        llm_sev = item.get("severity", "medium").lower()
                        normalized["severity"] = llm_sev if llm_sev in ("critical", "high", "medium", "low") else "medium"

                    violation = PolicyViolation.model_validate(normalized)

                    if violation.rule_id in valid_rule_ids:
                        violations.append(violation)
                    else:
                        print(f"Skipping unknown rule_id: {violation.rule_id!r} (valid: {valid_rule_ids})")

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
        base_url=API_BASE_URL,
        api_key=API_KEY,
        timeout=60.0,
    )
    image_name = os.environ.get("LOCAL_IMAGE_NAME", "my-env")

    log_start(task_id, BENCHMARK, MODEL_NAME)

    rewards: List[float] = []
    steps = 0
    env = None

    try:
        env = await LegalContractClient.from_docker_image(
            image_name, provider=Port7860DockerProvider()
        )

        result = await env.reset(task_id=task_id)

        best_violations = []
        cumulative_score = 0.0

        for step in range(1, MAX_STEPS + 1):
            obs = result.observation

            try:
                violations = get_model_violations(
                    client,
                    obs.contract_text,
                    obs.rules_to_check,
                    step,
                    obs.feedback,
                )
            except Exception as e:
                print(f"ERROR in get_model_violations at step {step}: {e}")
                violations = best_violations if best_violations else []

            # On step 1, submit what the LLM found as-is (no carry-forward).
            # On subsequent steps, try two strategies and pick the better one:
            #   A) LLM's fresh answer (may have dropped false positives)
            #   B) LLM's answer merged with carry-forward from best step
            # We submit the fresh answer first to see if dropping FPs helps.

            action = Action(
                identified_violations=violations,
                reasoning=f"Step {step}: Identified {len(violations)} violations by checking each policy rule against contract clauses.",
            )

            result = await env.step(action)

            # result.reward is the INCREMENTAL reward (improvement over prev best score).
            # Accumulate to track total earned reward.
            step_reward = result.reward if result.reward is not None else 0.0
            rewards.append(step_reward)
            cumulative_score += step_reward
            steps = step

            # Update best_violations when score improves (or on first step as baseline).
            # This ensures we always track the best-performing violation set.
            if violations:
                if step_reward > 0 or step == 1:
                    best_violations = violations.copy()

            print(f"\n[SCORE] Step {step}: incremental_reward={step_reward:.4f}, cumulative_score={cumulative_score:.4f}, violations_submitted={len(violations)}")
            log_step(step, f"{len(violations)}_violations", step_reward, result.done, None)

            if result.done:
                break

    except Exception as e:
        print(f"FATAL ERROR in run_task: {type(e).__name__}: {e}")
        log_step(steps + 1, "error", 0.0, True, str(e))
    finally:
        if env is not None:
            try:
                await env.close()
            except Exception:
                pass

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
