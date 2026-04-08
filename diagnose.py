"""Diagnostic script to pinpoint why score is always 0."""
import sys
sys.path.insert(0, ".")

from server.contract_gen import ContractGenerator
from server.policy_engine import run_policy_check, RULEBOOK_BY_ID, check_payment_terms, check_auto_renewal
from server.tasks import TASKS, get_task
from server.environment import ProcurementAuditEnv, compute_gold_violations, grade_action, _build_rules_to_check
from models import Action, PolicyViolation

print("=" * 70)
print("DIAGNOSTIC: Testing all three tasks")
print("=" * 70)

for task_id in ["easy", "medium", "hard"]:
    print(f"\n{'='*70}")
    print(f"TASK: {task_id}")
    print(f"{'='*70}")
    
    task = get_task(task_id)
    print(f"Expected violations: {task.violations}")
    print(f"Cross-doc violations: {task.cross_doc_violations}")
    
    # Generate contract
    gen = ContractGenerator(seed=42)
    contract_text = gen.generate(
        contract_type=task.contract_type,
        violations=task.violations,
        ambiguity_level=task.ambiguity_level,
        red_herrings=task.red_herrings,
    )
    
    print(f"\nContract length: {len(contract_text)} chars")
    print(f"Contract preview (first 500 chars):")
    print(contract_text[:500])
    print("...")
    
    # Check rules_to_check
    rules = _build_rules_to_check(task)
    print(f"\nRules to check ({len(rules)}):")
    for r in rules:
        print(f"  - {r}")
    
    # Compute gold violations
    gold = compute_gold_violations(contract_text, task)
    print(f"\nGold violations ({len(gold)}):")
    for g in gold:
        print(f"  - {g.rule_id}: {g.description} [{g.severity}]")
    
    # Run the policy engine to verify the contract actually contains violations
    print(f"\nPolicy engine check (all rules):")
    results = run_policy_check(contract_text)
    violations_found = {k: v for k, v in results.items() if v}
    print(f"  Violations detected by engine: {list(violations_found.keys())}")
    
    # Check specifically for the expected violations
    print(f"\nDirect check for expected violations:")
    for rule_id in task.violations:
        rule = RULEBOOK_BY_ID.get(rule_id)
        if rule:
            detected = rule.check(contract_text)
            print(f"  {rule_id} ({rule.description}): {'DETECTED' if detected else 'NOT DETECTED'}")
    
    # Test grading with CORRECT violations
    print(f"\n--- Grading with CORRECT violations ---")
    correct_violations = [
        PolicyViolation(
            rule_id=g.rule_id,
            description=g.description,
            severity=g.severity,
            clause_reference=g.clause_reference,
        )
        for g in gold
    ]
    score, feedback = grade_action(correct_violations, gold, task)
    print(f"  Score: {score}")
    print(f"  Feedback: {feedback}")
    
    # Test grading with EMPTY violations
    print(f"\n--- Grading with EMPTY violations ---")
    score_empty, feedback_empty = grade_action([], gold, task)
    print(f"  Score: {score_empty}")
    print(f"  Feedback: {feedback_empty}")
    
    # Test the environment end-to-end
    print(f"\n--- End-to-end environment test ---")
    env = ProcurementAuditEnv()
    obs = env.reset(task_id=task_id)
    print(f"  Reset OK. task_id={obs.task_id}, rules_to_check={len(obs.rules_to_check)}")
    print(f"  Contract has 'net-30': {'net-30' in obs.contract_text}")
    print(f"  Contract has 'net-60': {'net-60' in obs.contract_text}")
    
    # Search for key violation patterns in the contract
    import re
    print(f"\n  Searching for key patterns in contract:")
    patterns = {
        "net-30/net-45": r"net[- ](\d+)",
        "auto-renew": r"auto[- ]?renew|automatically renew",
        "30 days notice": r"(?:thirty|30)\s*\(?.*?\)?\s*days.*?notice",
        "60 days notice": r"(?:sixty|60)\s*\(?.*?\)?\s*days.*?notice",
        "90 days notice": r"(?:ninety|90)\s*\(?.*?\)?\s*days.*?notice",
    }
    for name, pattern in patterns.items():
        matches = re.findall(pattern, obs.contract_text, re.IGNORECASE)
        print(f"    '{name}': {matches if matches else 'NOT FOUND'}")
    
    # Step with correct violations
    action = Action(
        identified_violations=correct_violations,
        reasoning="Test: submitting correct violations",
    )
    obs2 = env.step(action)
    print(f"\n  Step with correct violations:")
    print(f"    Reward: {obs2.reward}")
    print(f"    Feedback: {obs2.feedback}")
    
    # Test: does the Action model properly serialize/deserialize?
    print(f"\n--- Serialization test ---")
    action_dict = action.model_dump(exclude_none=True)
    print(f"  Action dict keys: {list(action_dict.keys())}")
    print(f"  identified_violations count: {len(action_dict.get('identified_violations', []))}")
    if action_dict.get('identified_violations'):
        print(f"  First violation: {action_dict['identified_violations'][0]}")
    
    # Deserialize back
    action_restored = Action.model_validate(action_dict)
    print(f"  Restored violations count: {len(action_restored.identified_violations)}")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
