#!/usr/bin/env python3
"""Wrapper used by agent skills to run the Local Business AI engine CLI.

The wrapper supports three deployment modes:
1. BUSINESS_AI_HOME points at the local_business_ai engine directory.
2. engine_path.txt exists in the skill root and contains the engine directory.
3. The skill folder still lives inside the source tree at local_business_ai/agent_skill/...
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def find_engine_home() -> Path:
    candidates = []
    env_home = os.environ.get("BUSINESS_AI_HOME")
    if env_home:
        candidates.append(Path(env_home).expanduser())
    skill_root = Path(__file__).resolve().parents[1]
    engine_txt = skill_root / "engine_path.txt"
    if engine_txt.exists():
        candidates.append(Path(engine_txt.read_text(encoding="utf-8").strip()).expanduser())
    # Source-tree layout: local_business_ai/agent_skill/business-process-excel-analyst/scripts/this.py
    try:
        candidates.append(Path(__file__).resolve().parents[3])
    except Exception:
        pass
    candidates.append(Path.cwd())
    for c in candidates:
        c = c.resolve()
        if (c / "skill_cli.py").exists() and (c / "core").exists():
            return c
    raise SystemExit(
        "Could not find Local Business AI engine. Set BUSINESS_AI_HOME to the local_business_ai folder "
        "or create engine_path.txt in the skill root containing that path."
    )


def main() -> None:
    engine = find_engine_home()
    sys.path.insert(0, str(engine))
    sys.argv[0] = str(engine / "skill_cli.py")
    runpy.run_path(str(engine / "skill_cli.py"), run_name="__main__")


if __name__ == "__main__":
    main()
