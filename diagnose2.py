"""Diagnostic script to pinpoint why score is always 0."""
import sys
sys.path.insert(0, ".")

from server.contract_gen import ContractGenerator
from server.policy_engine import run_policy_check, RULEBOOK_BY_ID, check_payment_terms, check_auto_renewal
from server.tasks import TASKS, get_task
from server.environment import ProcurementAuditEnv, compute_gold_violations, grade_action, _build_rules_to_check
from models import Action, PolicyViolation

out = open("diagnose_result.txt", "w", encoding="utf-8")

def p(msg=""):
    print(msg, file=out)
    print(msg)

p("=" * 70)
p("DIAGNOSTIC: Testing all three tasks")
p("=" * 70)

for task_id in ["easy", "medium", "hard"]:
    p(f"\n{'='*70}")
    p(f"TASK: {task_id}")
    p(f"{'='*70}")
    
    task = get_task(task_id)
    p(f"Expected violations: {task.violations}")
    p(f"Cross-doc violations: {task.cross_doc_violations}")
    
    # Generate contract
    gen = ContractGenerator(seed=42)
    contract_text = gen.generate(
        contract_type=task.contract_type,
        violations=task.violations,
        ambiguity_level=task.ambiguity_level,
        red_herrings=task.red_herrings,
    )
    
    p(f"\nContract length: {len(contract_text)} chars")
    
    # Check rules_to_check
    rules = _build_rules_to_check(task)
    p(f"\nRules to check ({len(rules)}):")
    for r in rules:
        p(f"  - {r}")
    
    # Compute gold violations
    gold = compute_gold_violations(contract_text, task)
    p(f"\nGold violations ({len(gold)}):")
    for g in gold:
        p(f"  - {g.rule_id}: {g.description} [{g.severity}]")
    
    # Run the policy engine to verify the contract actually contains violations
    p(f"\nPolicy engine check on expected violations:")
    for rule_id in task.violations:
        rule = RULEBOOK_BY_ID.get(rule_id)
        if rule:
            detected = rule.check(contract_text)
            p(f"  {rule_id}: engine says {'VIOLATION' if detected else 'NO VIOLATION'}")
    
    # Search for key violation patterns in the contract
    import re
    p(f"\nKey patterns in contract:")
    patterns = {
        "net-XX": r"net[- ](\d+)",
        "auto-renew": r"auto[- ]?renew|automatically renew",
        "within XX days": r"within\s+\w+\s*\(?\s*(\d+)\s*\)?\s*days",
        "XX days notice": r"(\d+)\s*\)?\s*days['\s]*(?:prior\s+)?(?:written\s+)?notice",
    }
    for name, pattern in patterns.items():
        matches = re.findall(pattern, contract_text, re.IGNORECASE)
        p(f"  '{name}': {matches if matches else 'NOT FOUND'}")
    
    # Test grading with CORRECT violations
    p(f"\n--- Grading with CORRECT violations ---")
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
    p(f"  Score: {score}")
    p(f"  Feedback: {feedback}")
    
    # Test grading with EMPTY violations
    p(f"\n--- Grading with EMPTY violations ---")
    score_empty, feedback_empty = grade_action([], gold, task)
    p(f"  Score: {score_empty}")
    p(f"  Feedback: {feedback_empty}")
    
    # Test the full environment end-to-end
    p(f"\n--- Environment end-to-end test ---")
    env = ProcurementAuditEnv()
    obs = env.reset(task_id=task_id)
    p(f"  Reset OK. rules_to_check count={len(obs.rules_to_check)}")
    
    action = Action(
        identified_violations=correct_violations,
        reasoning="Test: submitting correct violations",
    )
    obs2 = env.step(action)
    p(f"  Step with correct violations: reward={obs2.reward}, feedback={obs2.feedback}")
    
    # Test serialization round-trip
    p(f"\n--- Serialization round-trip ---")
    action_dict = action.model_dump(exclude_none=True)
    p(f"  Serialized violations count: {len(action_dict.get('identified_violations', []))}")
    action_restored = Action.model_validate(action_dict)
    p(f"  Deserialized violations count: {len(action_restored.identified_violations)}")
    
    # Test: what happens when Action comes in via JSON (simulating HTTP)
    import json
    json_str = json.dumps(action_dict)
    action_from_json = Action.model_validate_json(json_str)
    p(f"  From JSON violations count: {len(action_from_json.identified_violations)}")

p("\n" + "=" * 70)
p("DIAGNOSTIC COMPLETE")
p("=" * 70)
out.close()
