"""Load a version-pinned presentation skill from its read-only mount."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path


class SkillUnavailable(RuntimeError):
    """Raised when the mounted mature presentation skill cannot be used."""


@dataclass(frozen=True)
class SkillBundle:
    root: Path
    instructions: str
    resources: tuple[str, ...]


class PresentationSkillLoader:
    """Read a skill without copying, modifying, or reimplementing it."""

    def __init__(self, root: str | Path = "/opt/skills/presentations") -> None:
        self.root = Path(root).resolve()

    def load(self) -> SkillBundle:
        skill_file = self.root / "SKILL.md"
        if not skill_file.is_file():
            raise SkillUnavailable(f"mature presentation skill is not mounted: {skill_file}")
        instructions = skill_file.read_text(encoding="utf-8")
        if not instructions.strip():
            raise SkillUnavailable(f"presentation skill is empty: {skill_file}")
        resources = tuple(
            str(path.relative_to(self.root)).replace(os.sep, "/")
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and path.name != "SKILL.md"
        )
        return SkillBundle(self.root, instructions, resources)

    def read_resource(self, relative_path: str) -> str:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("skill resource path escapes the skill directory") from exc
        if not candidate.is_file():
            raise FileNotFoundError(relative_path)
        return candidate.read_text(encoding="utf-8")


def validate_presentation_runtime(
    *,
    skill_root: str | Path,
    runtime_node: str | Path,
    runtime_node_modules: str | Path,
    runtime_bin_dir: str | Path,
) -> list[str]:
    """Return explicit blockers instead of silently substituting another PPT stack."""

    blockers: list[str] = []
    root = Path(skill_root)
    node = Path(runtime_node)
    modules = Path(runtime_node_modules)
    bin_dir = Path(runtime_bin_dir)
    if not (root / "SKILL.md").is_file():
        blockers.append(f"missing mature presentation skill at {root}")
    else:
        if not (root / "references").is_dir():
            blockers.append(f"presentation skill references are missing at {root / 'references'}")
        support_dirs = ("scripts", "container_tools", "template_following_scripts")
        if not any((root / name).is_dir() for name in support_dirs):
            blockers.append("presentation skill scripts/tooling directories are missing")
    if not node.is_file() or not os.access(node, os.X_OK):
        blockers.append(f"missing executable RUNTIME_NODE at {node}")
    if not modules.is_dir():
        blockers.append(f"missing RUNTIME_NODE_MODULES at {modules}")
    elif not (modules / "@oai" / "artifact-tool").exists():
        blockers.append("RUNTIME_NODE_MODULES does not contain @oai/artifact-tool")
    if not bin_dir.is_dir():
        blockers.append(f"missing RUNTIME_BIN_DIR at {bin_dir}")
    for module in ("numpy", "pptx", "pdf2image", "PIL"):
        if find_spec(module) is None:
            blockers.append(f"missing presentation Python dependency: {module}")
    if shutil.which("libreoffice") is None and shutil.which("soffice") is None:
        blockers.append("LibreOffice is not installed in the presentation-agent image")
    return blockers
