======================================================================
DIAGNOSTIC: Testing all three tasks
======================================================================

======================================================================
TASK: easy
======================================================================
Expected violations: ['RULE_02', 'RULE_03']
Cross-doc violations: []

Contract length: 5481 chars

Rules to check (2):
  - RULE_02: Payment terms must be net-60 or better
  - RULE_03: Auto-renewal requires 90-day written opt-out notice

Gold violations (2):
  - RULE_02: Payment terms must be net-60 or better [high]
  - RULE_03: Auto-renewal requires 90-day written opt-out notice [high]

Policy engine check on expected violations:
  RULE_02: engine says VIOLATION
  RULE_03: engine says VIOLATION

Key patterns in contract:
  'net-XX': NOT FOUND
  'auto-renew': NOT FOUND
  'within XX days': ['30']
  'XX days notice': ['60', '30', '60', '30']

--- Grading with CORRECT violations ---
  Score: 1.0
  Feedback: Matched: ['RULE_02', 'RULE_03']. Missed: []. False positives: []. Score: 1.0000.

--- Grading with EMPTY violations ---
  Score: 0.0
  Feedback: Matched: []. Missed: ['RULE_02', 'RULE_03']. False positives: []. Score: 0.0000.

--- Environment end-to-end test ---
  Reset OK. rules_to_check count=2
  Step with correct violations: reward=1.0, feedback=Matched: ['RULE_02', 'RULE_03']. Missed: []. False positives: []. Score: 1.0000.

--- Serialization round-trip ---
  Serialized violations count: 2
  Deserialized violations count: 2
  From JSON violations count: 2

======================================================================
TASK: medium
======================================================================
Expected violations: ['RULE_01', 'RULE_04', 'RULE_13', 'RULE_19', 'RULE_20']
Cross-doc violations: []

Contract length: 5789 chars

Rules to check (5):
  - RULE_01: Liability cap must be >= 2x annual contract value
  - RULE_04: Governing law must be India or USA (not Singapore/UK)
  - RULE_13: Late payment penalty clause required
  - RULE_19: SLA breach penalties/credits required
  - RULE_20: Vendor may not suspend service without notice

Gold violations (5):
  - RULE_01: Liability cap must be >= 2x annual contract value [critical]
  - RULE_04: Governing law must be India or USA (not Singapore/UK) [high]
  - RULE_13: Late payment penalty clause required [high]
  - RULE_19: SLA breach penalties/credits required [high]
  - RULE_20: Vendor may not suspend service without notice [medium]

Policy engine check on expected violations:
  RULE_01: engine says VIOLATION
  RULE_04: engine says NO VIOLATION
  RULE_13: engine says NO VIOLATION
  RULE_19: engine says VIOLATION
  RULE_20: engine says VIOLATION

Key patterns in contract:
  'net-XX': NOT FOUND
  'auto-renew': NOT FOUND
  'within XX days': ['0']
  'XX days notice': ['60', '30']

--- Grading with CORRECT violations ---
  Score: 1.0
  Feedback: Matched: ['RULE_01', 'RULE_04', 'RULE_13', 'RULE_19', 'RULE_20']. Missed: []. False positives: []. Score: 1.0000.

--- Grading with EMPTY violations ---
  Score: 0.0
  Feedback: Matched: []. Missed: ['RULE_01', 'RULE_04', 'RULE_13', 'RULE_19', 'RULE_20']. False positives: []. Score: 0.0000.

--- Environment end-to-end test ---
  Reset OK. rules_to_check count=5
  Step with correct violations: reward=1.0, feedback=Matched: ['RULE_01', 'RULE_04', 'RULE_13', 'RULE_19', 'RULE_20']. Missed: []. False positives: []. Score: 1.0000.

--- Serialization round-trip ---
  Serialized violations count: 5
  Deserialized violations count: 5
  From JSON violations count: 5

======================================================================
TASK: hard
======================================================================
Expected violations: ['RULE_01', 'RULE_06', 'RULE_07', 'RULE_08', 'RULE_09', 'RULE_11']
Cross-doc violations: [('MSA', 'DPA', 'RULE_18')]

Contract length: 5653 chars

Rules to check (7):
  - RULE_01: Liability cap must be >= 2x annual contract value
  - RULE_06: Indemnification must be mutual (not one-sided)
  - RULE_07: Termination for convenience: minimum 30-day notice
  - RULE_08: Data processing agreement required if PII is shared
  - RULE_09: Limitation of liability clause must be present
  - RULE_11: Warranty period minimum 12 months post-delivery
  - RULE_18: Indemnification must cover data breaches

Gold violations (7):
  - RULE_01: Liability cap must be >= 2x annual contract value [critical]
  - RULE_06: Indemnification must be mutual (not one-sided) [critical]
  - RULE_07: Termination for convenience: minimum 30-day notice [medium]
  - RULE_08: Data processing agreement required if PII is shared [critical]
  - RULE_09: Limitation of liability clause must be present [critical]
  - RULE_11: Warranty period minimum 12 months post-delivery [medium]
  - RULE_18: Indemnification must cover data breaches [critical]

Policy engine check on expected violations:
  RULE_01: engine says VIOLATION
  RULE_06: engine says VIOLATION
  RULE_07: engine says NO VIOLATION
  RULE_08: engine says VIOLATION
  RULE_09: engine says VIOLATION
  RULE_11: engine says NO VIOLATION

Key patterns in contract:
  'net-XX': NOT FOUND
  'auto-renew': NOT FOUND
  'within XX days': ['0']
  'XX days notice': ['30', '15', '30']

--- Grading with CORRECT violations ---
  Score: 1.0
  Feedback: Matched: ['RULE_01', 'RULE_06', 'RULE_07', 'RULE_08', 'RULE_09', 'RULE_11', 'RULE_18']. Missed: []. False positives: []. Score: 1.0000.

--- Grading with EMPTY violations ---
  Score: 0.0
  Feedback: Matched: []. Missed: ['RULE_01', 'RULE_06', 'RULE_07', 'RULE_08', 'RULE_09', 'RULE_11', 'RULE_18']. False positives: []. Score: 0.0000.

--- Environment end-to-end test ---
  Reset OK. rules_to_check count=7
  Step with correct violations: reward=1.0, feedback=Matched: ['RULE_01', 'RULE_06', 'RULE_07', 'RULE_08', 'RULE_09', 'RULE_11', 'RULE_18']. Missed: []. False positives: []. Score: 1.0000.

--- Serialization round-trip ---
  Serialized violations count: 7
  Deserialized violations count: 7
  From JSON violations count: 7

======================================================================
DIAGNOSTIC COMPLETE
======================================================================
