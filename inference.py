"""
Inference Script - Procurement Contract Anomaly Auditor OpenEnv
===============================================================
MANDATORY env vars (injected by the validator at runtime):
  API_BASE_URL        The LiteLLM proxy endpoint URL.
  HF_TOKEN or API_KEY The API key for the LiteLLM proxy.
  MODEL_NAME          The model identifier to use for inference.

STDOUT FORMAT
  [START] task=<task_name> env=<benchmark> model=<model_name>
  [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
  [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
"""

from pathlib import Path
import asyncio
import json
import os
import re
import textwrap
import time
import traceback
from typing import Any, Dict, List, Optional

# Load .env ONLY as fallback for local dev — never override injected vars
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

from openai import OpenAI
from models import PolicyViolation
from my_env import Action, LegalContractClient

# ── Configuration (safe at module level — no env-var guards here) ─────────────
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
TASK_NAME = os.getenv("PROCUREMENT_TASK", "all")
BENCHMARK = "procurement-contract-audit"
MAX_STEPS = int(os.getenv("MAX_STEPS", "5"))
TEMPERATURE = 0.0
MAX_TOKENS = 2048
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.5"))


# ── Prompts ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert legal contract compliance auditor for Fortune 500 procurement.
Your task is to review a supplier contract against a set of policy rules and identify ONLY the rules that are actually violated.

## INSTRUCTIONS
1. Read the contract text carefully, clause by clause.
2. Check EACH rule in the provided rules list against the contract.
3. For each rule, determine if the contract VIOLATES it by failing to meet the policy requirement.
4. Only include a rule in your output if you find a CLEAR violation.
5. You MUST use the EXACT rule_id from the rules list (e.g., "RULE_01").
6. You MUST use the EXACT severity shown in brackets [severity=X] in the rules list.
7. If you received feedback from a previous attempt, use it to correct your answer.

## OUTPUT FORMAT
Return ONLY a valid JSON array. No markdown, no code fences, no explanation.
Include ONLY rules that are violated.

[
  {
    "rule_id": "<exact rule_id>",
    "description": "<what the contract says vs what policy requires>",
    "severity": "<copy EXACTLY from [severity=X]>",
    "clause_reference": "<Section name where the violation appears>"
  }
]
""")


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def _clamp_reward(r: float) -> float:
    """Clamp reward strictly within (0, 1) — validator rejects exactly 0.0 and 1.0."""
    return max(0.01, min(0.99, float(r)))


def log_step(step: int, action: str, reward: float, done: bool,
             error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    clamped = _clamp_reward(reward)
    print(f"[STEP] step={step} action={action} reward={clamped:.2f} "
          f"done={done_val} error={error_val}", flush=True)


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    # IMPORTANT: exact format per spec — no extra fields like score=
    # Clamp all rewards strictly within (0, 1)
    clamped_rewards = [_clamp_reward(r) for r in rewards]
    rewards_str = ",".join(f"{r:.2f}" for r in clamped_rewards)
    print(f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}",
          flush=True)


def build_user_prompt(contract_text, rules_to_check, step, feedback):
    rules_block = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(rules_to_check))
    parts = []
    parts.append(f"## CONTRACT TEXT\n{contract_text.strip()}")
    parts.append(
        f"## POLICY RULES TO CHECK\n"
        f"Check EACH rule. For every violated rule include it with the EXACT rule_id:\n"
        f"{rules_block}"
    )
    if feedback and step > 1 and "Review the contract" not in feedback:
        parts.append(
            f"## FEEDBACK FROM PREVIOUS ATTEMPT (Step {step - 1})\n{feedback}\n\n"
            f"IMPORTANT: Fix missed violations and remove false positives."
        )
    parts.append(
        f"## TASK\nAnalyze the contract against ALL {len(rules_to_check)} rules. "
        f"Return a JSON array with one entry per violation found."
    )
    return "\n\n".join(parts)


def extract_json_from_text(text: str) -> Optional[list]:
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
    print(f"\n===== USER PROMPT (step {step}) =====")
    print(user_prompt[:500] + "..." if len(user_prompt) > 500 else user_prompt)

    for attempt in range(1, 4):
        try:
            print(f"\n--- LLM call attempt {attempt}/3 ---")
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
                print("JSON EXTRACTION FAILED")
                return []

            # Build valid rule ID → expected severity map from rules_to_check
            valid_rule_ids: set = set()
            rule_severity_map: dict = {}
            for rule in rules_to_check:
                rule_id = rule.split(" ")[0].strip().split(":")[0].strip()
                valid_rule_ids.add(rule_id)
                sev_match = re.search(r"\[severity=(\w+)\]", rule)
                if sev_match:
                    rule_severity_map[rule_id] = sev_match.group(1).lower()

            violations = []
            for item in raw:
                try:
                    normalized = {
                        "rule_id": item.get("rule_id", "UNKNOWN").strip(),
                        "description": item.get("description", item.get("reasoning", "")),
                        "clause_reference": item.get("clause_reference",
                                                     item.get("section", None)),
                        "severity": rule_severity_map.get(
                            item.get("rule_id", "").strip(),
                            item.get("severity", "medium").lower()
                        ),
                    }
                    violation = PolicyViolation.model_validate(normalized)
                    if violation.rule_id in valid_rule_ids:
                        violations.append(violation)
                    else:
                        print(f"Skipping unknown rule_id: {violation.rule_id!r}")
                except Exception as e:
                    print(f"VALIDATION ERROR: {e}")

            print(f"FINAL: {len(violations)} violations")
            return violations

        except Exception as e:
            print(f"LLM ERROR (attempt {attempt}/3): {type(e).__name__}: {e}")
            traceback.print_exc()
            if attempt < 3:
                wait = 2 ** attempt
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print("All retries exhausted.")
                return []


async def run_task(task_id: str):
    # ── Validate API env vars (checked here, not at module level, because the
    #    validator injects them *after* the container starts) ──────────────────
    api_base_url = os.environ.get("API_BASE_URL", "")
    api_key = os.environ.get("API_KEY") or os.environ.get("HF_TOKEN", "")

    if not api_base_url:
        raise EnvironmentError(
            "API_BASE_URL is not set. The validator must inject this variable."
        )
    if not api_key:
        raise EnvironmentError(
            "Neither API_KEY nor HF_TOKEN is set. The validator must inject one of these."
        )

    print(f"[CONFIG] API_BASE_URL = {api_base_url}", flush=True)
    print(f"[CONFIG] MODEL_NAME   = {MODEL_NAME}", flush=True)
    print(f"[CONFIG] API_KEY      = {api_key[:8]}...{api_key[-4:]}", flush=True)

    # Initialize client with injected credentials — strictly no hardcoding
    client = OpenAI(
        base_url=os.environ["API_BASE_URL"],
        api_key=os.environ.get("API_KEY") or os.environ["HF_TOKEN"],
        timeout=60.0,
    )

    log_start(task_id, BENCHMARK, MODEL_NAME)

    rewards: List[float] = []
    steps = 0
    env = None

    try:
        # Connect to the environment server already running at localhost:7860
        # inside this container (started by the Dockerfile CMD).
        # Do NOT use from_docker_image() — there is no Docker-in-Docker.
        env = LegalContractClient(base_url="http://localhost:7860")
        await env.connect()
        result = await env.reset(task_id=task_id)
        best_violations = []
        cumulative_score = 0.0

        for step in range(1, MAX_STEPS + 1):
            obs = result.observation

            try:
                violations = get_model_violations(
                    client, obs.contract_text, obs.rules_to_check, step, obs.feedback
                )
            except Exception as e:
                traceback.print_exc()
                violations = best_violations if best_violations else []

            action = Action(
                identified_violations=violations,
                reasoning=f"Step {step}: Identified {len(violations)} violations.",
            )
            result = await env.step(action)

            step_reward = result.reward if result.reward is not None else 0.01
            step_reward = _clamp_reward(step_reward)
            rewards.append(step_reward)
            cumulative_score += step_reward
            steps = step

            if violations and (step_reward > 0 or step == 1):
                best_violations = violations.copy()

            print(f"\n[SCORE] step={step} incremental={step_reward:.4f} "
                  f"cumulative={cumulative_score:.4f} violations={len(violations)}")
            log_step(step, f"{len(violations)}_violations", step_reward, result.done, None)

            if result.done:
                break

    except Exception as e:
        traceback.print_exc()
        log_step(steps + 1, "error", _clamp_reward(0.01), True, str(e))
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
    task_id = os.getenv("PROCUREMENT_TASK", "all")
    if task_id == "all":
        for tid in ["easy", "medium", "hard"]:
            print(f"\n{'='*60}\nRunning task: {tid}\n{'='*60}")
            success, total_reward, steps = await run_task(tid)
            print(f"\nTask {tid}: success={success}, reward={total_reward:.2f}, steps={steps}")
    else:
        await run_task(task_id)


if __name__ == "__main__":
    asyncio.run(main())