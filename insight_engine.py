from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


def stable_id(kind: str, title: str, evidence: Any = "") -> str:
    raw = json.dumps({"kind": kind, "title": title, "evidence": evidence}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_insight(impact: float = 0.5, confidence: float = 0.5, actionability: float = 0.5, relevance: float = 0.5, urgency: float = 0.3) -> Dict[str, float]:
    impact = clamp(float(impact))
    confidence = clamp(float(confidence))
    actionability = clamp(float(actionability))
    relevance = clamp(float(relevance))
    urgency = clamp(float(urgency))
    overall = impact * 0.34 + confidence * 0.24 + actionability * 0.20 + relevance * 0.14 + urgency * 0.08
    return {
        "overall": round(overall, 3),
        "impact": round(impact, 3),
        "confidence": round(confidence, 3),
        "actionability": round(actionability, 3),
        "relevance": round(relevance, 3),
        "urgency": round(urgency, 3),
    }


def make_insight(
    kind: str,
    title: str,
    summary: str,
    evidence: Dict[str, Any] | None = None,
    recommendation: str = "Review and validate with the responsible business owner.",
    impact: float = 0.5,
    confidence: float = 0.5,
    actionability: float = 0.5,
    relevance: float = 0.5,
    urgency: float = 0.3,
    status: str = "new",
) -> Dict[str, Any]:
    evidence = evidence or {}
    scores = score_insight(impact, confidence, actionability, relevance, urgency)
    return {
        "id": stable_id(kind, title, evidence),
        "kind": kind,
        "title": title,
        "summary": summary,
        "recommendation": recommendation,
        "scores": scores,
        "status": status,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence": evidence,
    }


def sort_insights(insights: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(insights, key=lambda i: (i.get("scores", {}).get("overall", 0), i.get("scores", {}).get("confidence", 0)), reverse=True)


def review_queue_path(session_dir: str | Path) -> Path:
    return Path(session_dir).expanduser().resolve() / "insights_review_queue.json"


def load_review_queue(session_dir: str | Path) -> Dict[str, Any]:
    path = review_queue_path(session_dir)
    if not path.exists():
        return {"items": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def save_review_queue(session_dir: str | Path, insights: Sequence[Dict[str, Any]], merge: bool = True) -> str:
    path = review_queue_path(session_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_review_queue(path.parent) if merge else {"items": []}
    by_id = {item.get("id"): item for item in existing.get("items", []) if item.get("id")}
    for insight in insights:
        old = by_id.get(insight.get("id"))
        if old:
            # Preserve human review status/notes while refreshing evidence/scores.
            status = old.get("status", insight.get("status", "new"))
            notes = old.get("review_notes", "")
            old.update(insight)
            old["status"] = status
            if notes:
                old["review_notes"] = notes
        else:
            by_id[insight.get("id")] = dict(insight)
    payload = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "items": sort_insights(list(by_id.values())),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)


def set_insight_status(session_dir: str | Path, insight_id: str, status: str, notes: str = "") -> Dict[str, Any]:
    allowed = {"new", "reviewing", "accepted", "rejected", "needs_more_data", "converted_to_action"}
    if status not in allowed:
        raise ValueError(f"Invalid insight status {status}. Use one of {sorted(allowed)}")
    queue = load_review_queue(session_dir)
    found = False
    for item in queue.get("items", []):
        if item.get("id") == insight_id:
            item["status"] = status
            item["reviewed_utc"] = datetime.now(timezone.utc).isoformat()
            if notes:
                item["review_notes"] = notes
            found = True
    if not found:
        raise KeyError(f"Insight id not found: {insight_id}")
    review_queue_path(session_dir).write_text(json.dumps(queue, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return queue


def insights_to_table_rows(insights: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for i in sort_insights(insights):
        scores = i.get("scores", {})
        rows.append({
            "ID": i.get("id"),
            "Status": i.get("status", "new"),
            "Type": i.get("kind"),
            "Title": i.get("title"),
            "Score": scores.get("overall"),
            "Impact": scores.get("impact"),
            "Confidence": scores.get("confidence"),
            "Actionability": scores.get("actionability"),
            "Summary": i.get("summary"),
            "Recommendation": i.get("recommendation"),
        })
    return rows


def goal_state_path(session_dir: str | Path) -> Path:
    return Path(session_dir).expanduser().resolve() / "goal_state.json"


def load_goal_state(session_dir: str | Path) -> Dict[str, Any]:
    path = goal_state_path(session_dir)
    if not path.exists():
        return {"runs": [], "accepted_insights": [], "rejected_insights": [], "next_search_areas": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"runs": [], "accepted_insights": [], "rejected_insights": [], "next_search_areas": []}


def update_goal_state(session_dir: str | Path, goal: str, insights: Sequence[Dict[str, Any]], next_search_areas: Sequence[str] | None = None) -> str:
    path = goal_state_path(session_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = load_goal_state(path.parent)
    queue = load_review_queue(path.parent)
    accepted = [i.get("id") for i in queue.get("items", []) if i.get("status") == "accepted"]
    rejected = [i.get("id") for i in queue.get("items", []) if i.get("status") == "rejected"]
    state["goal"] = goal
    state["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
    state["accepted_insights"] = sorted(set(state.get("accepted_insights", []) + accepted))
    state["rejected_insights"] = sorted(set(state.get("rejected_insights", []) + rejected))
    state.setdefault("runs", []).append({
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "insight_ids": [i.get("id") for i in insights],
        "top_insight_ids": [i.get("id") for i in sort_insights(insights)[:10]],
        "insight_count": len(insights),
    })
    suggested = list(next_search_areas or [])
    if not suggested:
        suggested = [
            "Validate high-scoring market matches with product managers.",
            "Collect missing material/labor/handling cost components for weak factory cost explanations.",
            "Review accepted insights and convert them into pricing or production actions.",
        ]
    state["next_search_areas"] = suggested
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)
