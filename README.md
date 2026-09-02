# CodeReview OpenEnv

Real-world code-review environment with three difficulty-ranked pull requests. Agents inspect diffs, flag issues with line/severity, ask clarifying questions, and decide approve vs. request_changes. Deterministic graders provide shaped rewards for partial progress, and a FastAPI server plus Dockerfile make it Hugging Face Space ready.

## Why this environment?
Code review is a core agent workflow: catching bugs, perf and security risks, and avoiding noisy false positives. The tasks model realistic PRs (style/docs, logic correctness, security/performance), with deterministic scoring that rewards precision and penalizes missed critical issues.

## Action & Observation spaces
- Observation (`code_review_env.models.Observation`)
  - `task_id` (str), `difficulty` (str)
  - `files` (list[{path, before, after}])
  - `tests_status` (pass|fail|not_run), `checklist` (list[str])
  - `step` (int), `max_steps` (int), `ground_truth_count` (int)
  - `feedback` (list[str]) formative hints
- Action (`code_review_env.models.Action`)
  - `findings` (list[{path:str, line:int, severity:nit|minor|major|critical, title:str, message:str}])
  - `decision` (approve|request_changes|null)
  - `questions` (optional list[str])
- Reward: shaped each step using TP/FP weights, miss penalties, decision consistency, question bonus, and a small step cost.

## Tasks & graders
1. **easy_style_docs** — renamed email helper; docstring stale + missing type hints. Expect two nits. Penalties for false positives.
2. **medium_logic_correctness** — pagination off-by-one and missing None guard before `.lower()`. Two majors; request_changes encouraged if missed.
3. **hard_security_perf** — SQL injection via f-string + N+1 profile query; harmless audit log line. Critical + major with bonus for recommending parameterized query; approving while missing the critical is penalized.
Graders are deterministic with explicit weights per issue; line matching ±1 and severity calibration produce partial credit.

## Project layout
- `code_review_env/` — environment package (models, tasks, env logic)
- `code_review_env/server/app.py` — FastAPI reset/step/state endpoints
- `openenv.yaml` — OpenEnv metadata
- `baseline.py` — baseline agent (OpenAI API or heuristic fallback)
- `Dockerfile` — container entrypoint `uvicorn code_review_env.server.app:app`
- `requirements.txt` — dependencies

## Running locally
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn code_review_env.server.app:app --host 0.0.0.0 --port 8000
```

Quick sanity check:
```bash
python - <<'PY'
from code_review_env.env import CodeReviewEnv
env = CodeReviewEnv()
obs = env.reset(task_id="easy_style_docs")
print("Observation files:", [f.path for f in obs.files])
result = env.step({
    "findings": [{"path": "service/emailer.py", "line": 2, "severity": "nit", "title": "Docstring", "message": "Update docstring to new name"}],
    "decision": None,
    "questions": ["Should compose_welcome return bool?"]
})
print(result)
print(env.state())
PY
```

## Baseline agent
Runs across all tasks; uses OpenAI if `OPENAI_API_KEY` is set, otherwise a deterministic heuristic.
```bash
OPENAI_API_KEY=sk-... python baseline.py
# or offline
python baseline.py
```
Outputs per-task and average scores.

## Docker
```bash
docker build -t code-review-openenv .
docker run -p 8000:8000 code-review-openenv
```

## Hugging Face Space
Mark the Space with tag `openenv` and point to the Dockerfile. The container starts `uvicorn` on port 8000 as required by the spec.

## Notes
- Episodes end when `decision` is provided or `max_steps` (default 3) is reached.
- Rewards: TP weighted by issue severity, penalties for misses/FPs, bonus for remediation hints and relevant questions, step cost for verbosity, decision penalty if approving with missed criticals.
- All graders are deterministic and seeded; `openenv.yaml` declares typed models for automated validation.
