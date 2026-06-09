from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SKILL_NAME = "business-process-excel-analyst"


def default_target(kind: str) -> Path:
    home = Path.home()
    if kind == "hermes":
        return home / ".hermes" / "skills" / SKILL_NAME
    if kind == "claude":
        return home / ".claude" / "skills" / SKILL_NAME
    if kind == "codex":
        return home / ".agents" / "skills" / SKILL_NAME
    raise ValueError(f"Unknown target kind: {kind}")


def install(target: Path, force: bool = False) -> Path:
    root = Path(__file__).resolve().parent
    source = root / "agent_skill" / SKILL_NAME
    if not source.exists():
        raise FileNotFoundError(f"Skill source not found: {source}")
    target = target.expanduser().resolve()
    if target.exists():
        if not force:
            raise FileExistsError(f"Target already exists: {target}. Use --force to replace it.")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    (target / "engine_path.txt").write_text(str(root), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Business Process Excel Analyst agent skill")
    parser.add_argument("--target", choices=["hermes", "claude", "codex", "custom"], default="hermes", help="Skill target harness")
    parser.add_argument("--path", default="", help="Custom target path when --target custom, or override target directory")
    parser.add_argument("--force", action="store_true", help="Replace existing skill directory")
    args = parser.parse_args()
    if args.path:
        target = Path(args.path)
    else:
        target = default_target(args.target)
    installed = install(target, force=args.force)
    print(f"Installed {SKILL_NAME} to {installed}")
    print(f"Engine path recorded in {installed / 'engine_path.txt'}")
    print("Test with:")
    print(f"  python {installed / 'scripts' / 'business_excel_skill.py'} templates list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
