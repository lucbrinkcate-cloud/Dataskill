from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


def safe_slug(value: str, fallback: str = "session") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "").strip()).strip("_")
    return slug[:80] or fallback


def make_session_id(label: str = "run") -> str:
    now = datetime.now()
    return f"{now.strftime('%Y-%m-%d_%H-%M-%S')}_{safe_slug(label)}_{uuid.uuid4().hex[:6]}"


def session_output_dir(base_dir: str, label: str = "run", session_id: Optional[str] = None, create: bool = True) -> Path:
    base = Path(base_dir).expanduser().resolve()
    sid = safe_slug(session_id, fallback="session") if session_id else make_session_id(label)
    # Date-first hierarchy makes it easy to find runs by day.
    date_prefix = sid[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", sid) else datetime.now().strftime("%Y-%m-%d")
    out = base / date_prefix / sid
    if create:
        out.mkdir(parents=True, exist_ok=True)
    return out
