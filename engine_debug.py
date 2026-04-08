"""Quick check: why policy engine misses some violations in generated contracts."""
import sys
sys.path.insert(0, ".")
import re
from server.contract_gen import ContractGenerator
from server.policy_engine import RULEBOOK_BY_ID
from server.tasks import get_task

out = open("engine_debug.txt", "w", encoding="utf-8")

def p(msg=""):
    out.write(msg + "\n")

for task_id in ["easy", "medium", "hard"]:
    task = get_task(task_id)
    gen = ContractGenerator(seed=42)
    contract = gen.generate(
        contract_type=task.contract_type,
        violations=task.violations,
        ambiguity_level=task.ambiguity_level,
        red_herrings=task.red_herrings,
    )
    
    p(f"\n{'='*70}")
    p(f"TASK: {task_id} — violations: {task.violations}")
    p(f"{'='*70}")
    
    for rule_id in task.violations:
        rule = RULEBOOK_BY_ID.get(rule_id)
        if rule:
            detected = rule.check(contract)
            status = "OK" if detected else "MISSED"
            p(f"\n  [{status}] {rule_id}: {rule.description}")
            
            if not detected:
                # Show relevant sections of contract
                p(f"  === Engine didn't detect this. Searching contract for clues ===")
                for line in contract.split("\n"):
                    # Search for keywords related to the rule
                    keywords = {
                        "RULE_04": ["governing", "laws of", "governed"],
                        "RULE_07": ["terminat"],
                        "RULE_11": ["warrant"],
                        "RULE_13": ["late", "penalty", "payment", "invoice", "interest"],
                    }
                    kws = keywords.get(rule_id, [rule_id.lower()])
                    if any(kw.lower() in line.lower() for kw in kws):
                        p(f"    >> {line.strip()}")

out.close()
print("Done. See engine_debug.txt")
