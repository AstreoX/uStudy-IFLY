from pathlib import Path

import pytest

from presentation_agent.skill_loader import (
    PresentationSkillLoader,
    SkillUnavailable,
    validate_presentation_runtime,
)


def test_loads_complete_skill_and_lists_support_files(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("# Full instructions\nDo the work.", encoding="utf-8")
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "layout.md").write_text("layout", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "render.py").write_text("pass", encoding="utf-8")

    bundle = PresentationSkillLoader(tmp_path).load()

    assert bundle.instructions == "# Full instructions\nDo the work."
    assert bundle.resources == ("references/layout.md", "scripts/render.py")


def test_missing_skill_is_a_blocker(tmp_path: Path):
    with pytest.raises(SkillUnavailable, match="not mounted"):
        PresentationSkillLoader(tmp_path).load()


def test_resource_read_cannot_escape_skill_mount(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("instructions", encoding="utf-8")
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes"):
        PresentationSkillLoader(tmp_path).read_resource("../secret.txt")


def test_dependency_validation_reports_missing_real_runtime(tmp_path: Path, monkeypatch):
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("instructions", encoding="utf-8")
    monkeypatch.setattr("presentation_agent.skill_loader.shutil.which", lambda _: None)

    blockers = validate_presentation_runtime(
        skill_root=skill,
        runtime_node=tmp_path / "node",
        runtime_node_modules=tmp_path / "modules",
        runtime_bin_dir=tmp_path / "bin",
    )

    assert any("references" in item for item in blockers)
    assert any("scripts/tooling" in item for item in blockers)
    assert any("RUNTIME_NODE" in item for item in blockers)
    assert any("RUNTIME_NODE_MODULES" in item for item in blockers)
    assert any("LibreOffice" in item for item in blockers)
