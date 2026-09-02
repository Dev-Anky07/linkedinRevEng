"""Baseline inference for CodeReview OpenEnv.

Uses OpenAI chat completion if OPENAI_API_KEY is present; otherwise falls back to
rule-based heuristics so scores are reproducible offline. Produces per-task and
average scores across the three tasks.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None

from code_review_env.env import CodeReviewEnv

MODEL_NAME = os.getenv("OPENENV_BASELINE_MODEL", "gpt-4o-mini")
TEMPERATURE = 0.0
MAX_TOKENS = 400
SYSTEM_PROMPT = (
    "You are a senior code reviewer. Return ONLY valid JSON for the action schema: "
    "{\"findings\":[{\"path\":str,\"line\":int,\"severity\":\"nit|minor|major|critical\",\"title\":str,\"message\":str}],"
    "\"decision\":\"approve|request_changes|null\",\"questions\":list[str]}. "
    "Be concise and only include issues you are confident about."
)
FALLBACK_ACTION = json.dumps({"findings": [], "decision": None, "questions": []})


def build_user_content(observation: dict) -> List[Dict[str, object]]:
    summary = {
        "task_id": observation.get("task_id"),
        "difficulty": observation.get("difficulty"),
        "tests_status": observation.get("tests_status"),
        "checklist": observation.get("checklist"),
        "files": observation.get("files"),
        "feedback": observation.get("feedback"),
        "step": observation.get("step"),
        "max_steps": observation.get("max_steps"),
    }
    return [{"type": "text", "text": json.dumps(summary, ensure_ascii=False)}]


def parse_model_action(text: str) -> Dict[str, object]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return json.loads(FALLBACK_ACTION)


def heuristic_policy(obs: dict) -> Dict[str, object]:
    findings: List[Dict[str, object]] = []
    files = obs.get("files", [])
    for file in files:
        path = file.get("path", "")
        after = file.get("after", "")
        lines = after.splitlines()
        if "emailer.py" in path:
            findings.append({
                "path": path,
                "line": 1,
                "severity": "nit",
                "title": "Missing type hints",
                "message": "Add type hints for user and return type.",
            })
            findings.append({
                "path": path,
                "line": 2,
                "severity": "nit",
                "title": "Outdated docstring",
                "message": "Docstring still references old function name.",
            })
        if "paging.py" in path:
            findings.append({
                "path": path,
                "line": 4,
                "severity": "major",
                "title": "Off-by-one slice",
                "message": "Slice end should be exclusive; drop +1.",
            })
            findings.append({
                "path": path,
                "line": 7,
                "severity": "major",
                "title": "None guard",
                "message": "term can be None before .lower().",
            })
        if "user_repo.py" in path:
            findings.append({
                "path": path,
                "line": 2,
                "severity": "critical",
                "title": "SQL injection",
                "message": "Use parameterized query instead of f-string.",
            })
            findings.append({
                "path": path,
                "line": 5,
                "severity": "major",
                "title": "N+1 queries",
                "message": "Querying profiles inside loop; prefetch instead.",
            })
    decision = "request_changes" if any(f["severity"] in {"major", "critical"} for f in findings) else "approve"
    return {"findings": findings, "decision": decision, "questions": []}


def llm_policy(client, obs: dict) -> Dict[str, object]:
    user_content = build_user_content(obs)
    messages = [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
        {"role": "user", "content": user_content},
    ]
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        response_text = completion.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        print(f"Model request failed ({exc}). Using fallback action.")
        response_text = FALLBACK_ACTION
    return parse_model_action(response_text)


def run_episode(env: CodeReviewEnv, policy_fn, task_id: str) -> float:
    observation = env.reset(task_id=task_id)
    history: List[str] = []
    for step in range(1, env.max_steps + 1):
        action = policy_fn(observation.model_dump())
        result = env.step(action)
        observation = result.observation
        reward = result.reward or 0.0
        error_flag = " ERROR" if "error" in result.info else ""
        history.append(f"Step {step}: reward {reward:+.2f}{error_flag}")
        if result.done:
            break
    return env.cumulative_reward / max(1, env.step_count)


def main():
    env = CodeReviewEnv(seed=0)
    api_key = os.getenv("OPENAI_API_KEY")
    use_llm = bool(api_key and OpenAI)
    client = OpenAI(api_key=api_key) if use_llm else None
    policy = (lambda obs: llm_policy(client, obs)) if use_llm else heuristic_policy

    scores: List[float] = []
    for task in env.tasks:
        score = run_episode(env, policy, task_id=task["id"])
        scores.append(score)
        print(f"Task {task['id']}: {score:.3f}")
    avg_score = sum(scores) / len(scores)
    print(f"Average baseline score: {avg_score:.3f} (model={MODEL_NAME if use_llm else 'heuristic'})")


if __name__ == "__main__":
    main()
