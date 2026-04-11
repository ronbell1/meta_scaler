OpenEnv Incident Debugging — Grader & Score Analysis
Purpose: This document explains exactly how this project avoids the
"One or more task scores are out of range" error, and how the grading system works end-to-end.

1. File Structure & Responsibilities
scaler/
├── openenv.yaml            ← Task + grader configuration (the spec file)
├── inference.py             ← Baseline agent that runs all 3 tasks
├── server/
│   ├── app.py               ← FastAPI server, API endpoints, grader routes
│   ├── environment.py       ← Core RL environment (reset/step/state)
│   ├── scorer.py            ← ⭐ WHERE SCORES ARE CALCULATED + CLAMPED
│   ├── parser.py            ← Parses raw text actions into structured fields
│   ├── tasks.py             ← Gold-standard answers for easy/medium/hard
│   ├── models.py            ← Pydantic typed models (Action, Observation, State)
│   └── log_generator.py     ← Procedural noise log generator
Who does what:
File	Role
openenv.yaml	Declares 3 tasks with grader.type: score and grader.endpoint: /grade/{id}
tasks.py	Stores the gold answers each task is graded against
parser.py	Extracts ROOT_CAUSE, FACTORS, FIX, SEVERITY from raw text
scorer.py	Computes the score using F1/coverage metrics, then clamps to (0.01, 0.99)
environment.py	Orchestrates reset → step → score flow
app.py	Exposes HTTP endpoints including /grade/easy, /grade/medium, /grade/hard
inference.py	Runs all 3 tasks and emits [START]/[STEP]/[END] logs
2. The Full Execution Flow
Validator/Agent calls POST /reset?task_id=easy
         │
         ▼
   ┌─────────────┐
   │ environment  │ ← Loads gold answers from tasks.py
   │   .reset()   │ ← Generates procedural logs via log_generator.py
   └──────┬──────┘
          │ returns Observation (logs, context)
          ▼
Validator/Agent calls POST /step  { "raw_text": "ROOT_CAUSE: ... FACTORS: ... FIX: ... SEVERITY: ..." }
         │
         ▼
   ┌─────────────┐
   │ environment  │
   │   .step()    │
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐     ┌──────────┐
   │  parser.py   │────▶️│ scorer.py │
   │ parse_action │     │ calculate │
   └─────────────┘     │ _score_   │
                        │ and_reward│
                        └─────┬────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ CLAMP HAPPENS    │
                    │ max(0.01, min(   │
                    │   0.99, raw))    │
                    └────────┬─────────┘
                             │
                             ▼
                  Returns { score, reward, done }
                             │
                             ▼
          Validator calls GET or POST /grade/easy
                             │
                             ▼
                    ┌──────────────────┐
                    │ CLAMP AGAIN      │
                    │ max(0.01, min(   │
                    │   0.99, score))  │
                    └────────┬─────────┘
                             │
                             ▼
                  Returns { "score": 0.XX }  ← always in (0, 1)
3. Grader Logic — Deep Dive
3.1 Where scores are computed
The scoring happens in 
scorer.py
:

python
def calculate_score_and_reward(parsed, task, best_score, raw_text, previous_action_text):
It computes 4 sub-scores, each between 0.0 and 1.0:

Component	Weight	How it's calculated
rc_score (Root Cause)	0.4	F1 between predicted and gold root cause tokens
f_score (Factors)	0.2	F1 between predicted and gold contributing factor tokens
fix_score (Fix)	0.3	Category coverage (RESTART, SCALE, OPTIMIZE, ROLLBACK)
sev_score (Severity)	0.1	Binary: 1.0 if severity matches gold, 0.0 otherwise
The raw combined score:

python
current_score_raw = (rc_score * 0.4 + f_score * 0.2 + fix_score * 0.3 + sev_score * 0.1)
IMPORTANT

This raw score CAN be exactly 0.0 or 1.0. For example:

If the agent submits garbage → all sub-scores are 0.0 → raw score = 0.0 ❌
If the agent gets everything perfect → all sub-scores are 1.0 → raw score = 1.0 ❌
Both of these would fail the validator.

3.2 The critical fix — Score Clamping (Layer 1)
Immediately after computing the raw score, 
scorer.py line 67
 clamps it:

python
# Calibration: ensure score stays within (0, 1) strictly
current_score = max(0.01, min(0.99, current_score_raw))
This is the primary safeguard. It transforms the score like this:

Raw Score	After Clamping	Valid?
0.0	0.01	✅
0.0000001	0.01	✅
0.42	0.42	✅
0.78	0.78	✅
1.0	0.99	✅
0.9999	0.99	✅
3.3 Score Clamping (Layer 2) — Grader Endpoints
Even after Layer 1, there's a second clamp in the /grade/* endpoints in 
app.py line 609
:

python
score = info.get("score", 0.0)
# Clamp to strict (0, 1) — validator rejects 0.0 and 1.0
score = max(0.01, min(0.99, score))
This is defense-in-depth. Even if a code path somehow bypasses Layer 1, the grader endpoint will never return 0.0 or 1.0.

3.4 Why two layers?
Layer	Location	Protects against
Layer 1	scorer.py:67	Raw score calculation producing 0.0 or 1.0
Layer 2	app.py:609	Edge cases like rounding, default values, or error paths returning 0.0
4. Grader Endpoint Configuration
4.1 openenv.yaml declares the graders
yaml
tasks:
  easy:
    grader:
      type: score           # ← tells validator this is a score-based grader
      endpoint: /grade/easy  # ← tells validator WHERE to call
  medium:
    grader:
      type: score
      endpoint: /grade/medium
  hard:
    grader:
      type: score
      endpoint: /grade/hard
4.2 app.py implements matching endpoints
Each endpoint supports both GET and POST (some validators use GET, some POST):

python
@app.get("/grade/easy")
@app.post("/grade/easy")
async def grade_easy(request: Request):
    # ... parse body ...
    return await _grade("easy", action)  # → returns { "score": 0.01–0.99 }
@app.get("/grade/medium")
@app.post("/grade/medium")
async def grade_medium(request: Request):
    return await _grade("medium", action)
@app.get("/grade/hard")
@app.post("/grade/hard")
async def grade_hard(request: Request):
    return await _grade("hard", action)
Plus fallback routes for robustness:

python
@app.get("/grade/{task_id}")    # dynamic catch-all
@app.post("/grade/{task_id}")
@app.get("/grade")              # generic (task_id in body)
@app.post("/grade")
4.3 Why both GET and POST matter
The validator's HTTP method is unpredictable. Your friend's fix specifically noted:

"I also enabled both GET and POST for grader routes so validator method mismatch doesn't break grading."

If you only have @app.post(...) and the validator sends a GET, it returns 405 Method Not Allowed → the validator sees no grader → ❌ fails.

5. Why This Project Does NOT Encounter The Error
Summary of all safeguards:
#	Safeguard	Where	What it prevents
1	Score clamping max(0.01, min(0.99, ...))	scorer.py:67	Raw score = 0.0 or 1.0
2	Score clamping in grader response	app.py:609	Grader endpoint returning 0.0 or 1.0
3	spec_version: 1 in openenv.yaml	openenv.yaml:1	Validator not recognizing the spec
4	grader.type: score per task	openenv.yaml:18,24,30	Validator not finding grader type
5	grader.endpoint per task	openenv.yaml:19,25,31	Validator not knowing where to call
6	Dedicated per-task routes	app.py:621-649	Endpoint not existing for a task
7	GET + POST on all grader routes	app.py:621-675	HTTP method mismatch
8	Dynamic fallback route	app.py:653-661	Unexpected task_id format
9	Generic /grade fallback	app.py:665-675	Validator calling bare /grade
The exact reason it works:
Every possible path that produces a score passes through max(0.01, min(0.99, value)).
There is no code path where a score of exactly 0.0 or 1.0 can escape to the validator.
Additionally, every grader endpoint declared in openenv.yaml actually exists server-side,
responds to both GET and POST, and always returns a score in the open interval (0, 1).

6. How To Apply This Fix To Another Project
Step 1: Find where your score is calculated
Look for the function that produces the final score number. It might look like:

python
score = some_calculation(...)
return {"score": score}
Step 2: Add clamping BEFORE returning
python
score = some_calculation(...)
score = max(0.01, min(0.99, score))  # ← ADD THIS LINE
return {"score": score}
Step 3: Add clamping in your grader endpoint too
python
@app.post("/grade/easy")
async def grade_easy(...):
    score = compute_score(...)
    score = max(0.01, min(0.99, score))  # ← DEFENSE IN DEPTH
    return {"score": score}
Step 4: Make sure grader endpoints support GET and POST
python
@app.get("/grade/easy")    # ← ADD GET
@app.post("/grade/easy")   # ← KEEP POST
async def grade_easy(...):
Step 5: Verify your openenv.yaml
yaml
tasks:
  your_task:
    grader:
      type: score              # ← must be "score"
      endpoint: /grade/your_task  # ← must match an actual route
CAUTION

The most common mistake is clamping in only one place. If your scoring function returns 0.0
and your grader endpoint doesn't clamp, the validator sees 0.0 and rejects it.
Always clamp in both places.