"""Release packaging, version metadata, and CI guardrails."""

import json
import os
import re
import subprocess
import tomllib
import zipfile
from pathlib import Path
from typing import cast

import pytest
from scripts import build_release, check_release_tag

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "template_humidifier"
WORKFLOWS = ROOT / ".github" / "workflows"
MAX_MODULE_LINES = 250
HACS_ALLOWED_KEYS = {
    "content_in_root",
    "country",
    "filename",
    "hacs",
    "hide_default_branch",
    "homeassistant",
    "name",
    "persistent_directory",
    "render_readme",
    "zip_release",
}
SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.jsonl",
    "*.log",
    "*token*.json",
    "secrets.yaml",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(_read(path)))


@pytest.fixture
def fake_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the builder at a throwaway copy of the integration layout."""
    integration = tmp_path / "custom_components" / "template_humidifier"
    for name in build_release.RUNTIME_FILES:
        target = integration / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_bytes(f"# {name}\n".encode())
    monkeypatch.setattr(build_release, "ROOT", tmp_path)
    monkeypatch.setattr(build_release, "INTEGRATION_DIR", integration)
    return integration


# --- release archive -------------------------------------------------------


def test_real_package_is_exactly_the_runtime_allowlist() -> None:
    packaged = {
        path.relative_to(INTEGRATION).as_posix()
        for path in build_release.validate_package_files()
    }

    assert packaged == set(build_release.RUNTIME_FILES)


def test_package_rejects_unexpected_files(fake_tree: Path) -> None:
    _ = (fake_tree / "scratch.txt").write_text("draft\n", encoding="utf-8")

    with pytest.raises(
        build_release.ReleasePackageError, match=re.escape("scratch.txt")
    ):
        _ = build_release.validate_package_files()


@pytest.mark.parametrize("name", [".env", "api-token.json", "debug.log"])
def test_package_rejects_sensitive_files(fake_tree: Path, name: str) -> None:
    _ = (fake_tree / name).write_text("secret\n", encoding="utf-8")

    with pytest.raises(build_release.ReleasePackageError, match="sensitive"):
        _ = build_release.validate_package_files()


def test_package_rejects_missing_files(fake_tree: Path) -> None:
    (fake_tree / "humidifier.py").unlink()

    with pytest.raises(
        build_release.ReleasePackageError, match=re.escape("humidifier.py")
    ):
        _ = build_release.validate_package_files()


def test_package_rejects_symlinked_files(fake_tree: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    _ = outside.write_text("SECRET = True\n", encoding="utf-8")
    target = fake_tree / "const.py"
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError as err:
        pytest.skip(f"symlinks are unavailable: {err}")

    with pytest.raises(build_release.ReleasePackageError, match="symlinked path"):
        _ = build_release.validate_package_files()


def test_package_ignores_bytecode_directories(fake_tree: Path) -> None:
    cache = fake_tree / "__pycache__"
    cache.mkdir()
    _ = (cache / "const.cpython-314.pyc").write_bytes(b"\x00")

    assert len(build_release.validate_package_files()) == len(
        build_release.RUNTIME_FILES
    )


@pytest.mark.usefixtures("fake_tree")
def test_archive_is_rooted_at_the_integration_contents(tmp_path: Path) -> None:
    output = build_release.build_archive(tmp_path / "out" / "release.zip")

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        archive.extractall(tmp_path / "custom_components" / "extracted")

    assert names == set(build_release.RUNTIME_FILES)
    assert (tmp_path / "custom_components" / "extracted" / "manifest.json").is_file()
    assert not any(name.startswith("custom_components") for name in names)


@pytest.mark.usefixtures("fake_tree")
def test_archive_entries_are_stored_with_fixed_metadata(tmp_path: Path) -> None:
    output = build_release.build_archive(tmp_path / "release.zip")

    with zipfile.ZipFile(output) as archive:
        infos = archive.infolist()

    assert [info.filename for info in infos] == sorted(build_release.RUNTIME_FILES)
    for info in infos:
        assert info.date_time == build_release.ZIP_TIMESTAMP
        assert info.compress_type == zipfile.ZIP_STORED
        assert info.external_attr >> 16 == build_release.ZIP_FILE_MODE


def test_archive_is_reproducible_across_mtimes_and_line_endings(
    fake_tree: Path, tmp_path: Path
) -> None:
    target = fake_tree / "const.py"
    _ = target.write_bytes(b"VALUE = 1\nOTHER = 2\n")
    os.utime(target, (946684800, 946684800))
    first = build_release.build_archive(tmp_path / "first.zip")

    _ = target.write_bytes(b"VALUE = 1\r\nOTHER = 2\r\n")
    os.utime(target, (1767225600, 1767225600))
    second = build_release.build_archive(tmp_path / "second.zip")

    assert first.read_bytes() == second.read_bytes()


def test_binary_files_are_archived_unchanged(fake_tree: Path, tmp_path: Path) -> None:
    payload = b"\x89PNG\r\n\x1a\n\r\n"
    _ = (fake_tree / "brand" / "icon.png").write_bytes(payload)

    output = build_release.build_archive(tmp_path / "release.zip")

    with zipfile.ZipFile(output) as archive:
        assert archive.read("brand/icon.png") == payload


@pytest.mark.parametrize("name", ["release.txt", "../escape.zip"])
@pytest.mark.usefixtures("fake_tree")
def test_output_must_be_a_zip_inside_the_repository(name: str) -> None:
    with pytest.raises(build_release.ReleasePackageError):
        _ = build_release.resolve_output(Path(name))


def test_builder_cli_reports_success_and_failure(
    fake_tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert build_release.main(["--check"]) == 0
    assert "check passed" in capsys.readouterr().out
    assert build_release.main(["--output", "dist/release.zip"]) == 0

    _ = (fake_tree / "extra.py").write_text("x = 1\n", encoding="utf-8")

    assert build_release.main(["--check"]) == 1
    assert "unexpected integration files" in capsys.readouterr().err


# --- release tag -----------------------------------------------------------


def test_tag_must_match_manifest_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_release_tag, "manifest_version", lambda: "0.1.0b1")

    check_release_tag.validate_release_tag("v0.1.0b1")
    for wrong in ("0.1.0b1", "v0.1.0", "v0.1.0b2", "v0.1.0b1 "):
        with pytest.raises(check_release_tag.ReleaseTagError, match="does not match"):
            check_release_tag.validate_release_tag(wrong)


@pytest.mark.parametrize(
    ("version", "prerelease"),
    [("0.1.0", False), ("1.12.3", False), ("0.1.0b1", True), ("0.1.0rc12", True)],
)
def test_prerelease_classification(
    version: str,
    prerelease: bool,  # noqa: FBT001
) -> None:
    assert check_release_tag.release_is_prerelease(version) is prerelease


@pytest.mark.parametrize(
    "version", ["0.1", "0.1.0a1", "0.1.0-beta", "v0.1.0", "0.1.0b", "0.1.0.dev1", ""]
)
def test_unsupported_versions_are_rejected(version: str) -> None:
    with pytest.raises(check_release_tag.ReleaseTagError, match="unsupported"):
        _ = check_release_tag.release_is_prerelease(version)


def test_manifest_version_is_read_and_validated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(check_release_tag, "MANIFEST_PATH", manifest)

    with pytest.raises(check_release_tag.ReleaseTagError, match="cannot read"):
        _ = check_release_tag.manifest_version()

    _ = manifest.write_text('{"version": "0.1.0-beta"}', encoding="utf-8")
    with pytest.raises(check_release_tag.ReleaseTagError, match="must be"):
        _ = check_release_tag.manifest_version()

    _ = manifest.write_text('{"version": "0.2.0rc1"}', encoding="utf-8")
    assert check_release_tag.manifest_version() == "0.2.0rc1"


def test_github_output_receives_the_prerelease_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    check_release_tag.write_github_output("0.1.0b1")
    check_release_tag.write_github_output("0.1.0")

    assert output.read_text(encoding="utf-8") == "prerelease=true\nprerelease=false\n"

    monkeypatch.delenv("GITHUB_OUTPUT")
    with pytest.raises(check_release_tag.ReleaseTagError, match="GITHUB_OUTPUT"):
        check_release_tag.write_github_output("0.1.0")


def test_tag_cli_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(check_release_tag, "manifest_version", lambda: "0.1.0b1")
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    assert check_release_tag.main(["v0.1.0b1", "--github-output"]) == 0
    assert output.read_text(encoding="utf-8") == "prerelease=true\n"
    assert check_release_tag.main(["v9.9.9"]) == 1
    assert "does not match" in capsys.readouterr().err

    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    with pytest.raises(SystemExit):
        _ = check_release_tag.main([])


# --- version and metadata --------------------------------------------------


def test_every_version_source_agrees() -> None:
    manifest = _json(INTEGRATION / "manifest.json")["version"]
    pyproject = cast(
        "dict[str, dict[str, object]]", tomllib.loads(_read(ROOT / "pyproject.toml"))
    )["project"]["version"]
    lock = cast(
        "dict[str, list[dict[str, object]]]", tomllib.loads(_read(ROOT / "uv.lock"))
    )
    locked = next(
        package["version"]
        for package in lock["package"]
        if package["name"] == "hass-template-humidifier"
    )

    assert manifest == pyproject == locked


def test_manifest_invariants() -> None:
    manifest = _json(INTEGRATION / "manifest.json")

    assert manifest["domain"] == "template_humidifier"
    assert manifest["requirements"] == []
    assert manifest["iot_class"] == "local_push"
    assert "config_flow" not in manifest
    assert manifest["issue_tracker"]
    assert manifest["documentation"]


def test_hacs_metadata_matches_the_archive_and_ha_baseline() -> None:
    hacs = _json(ROOT / "hacs.json")
    dev_dependencies = cast(
        "dict[str, dict[str, list[str]]]",
        tomllib.loads(_read(ROOT / "pyproject.toml")),
    )["dependency-groups"]["dev"]
    ha_pin = next(
        item.partition("==")[2]
        for item in dev_dependencies
        if item.startswith("homeassistant==")
    )

    assert set(hacs) <= HACS_ALLOWED_KEYS
    assert hacs["zip_release"] is True
    assert hacs["filename"] == f"{build_release.DOMAIN}.zip"
    assert hacs["homeassistant"] == ha_pin
    assert hacs["render_readme"] is True


def test_custom_components_contains_only_this_integration() -> None:
    names = [
        path.name
        for path in (ROOT / "custom_components").iterdir()
        if path.is_dir() and not path.name.startswith("__")
    ]

    assert names == ["template_humidifier"]


def test_runtime_modules_stay_small() -> None:
    for module in INTEGRATION.glob("*.py"):
        lines = [
            line
            for line in _read(module).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) < MAX_MODULE_LINES, module.name


def test_no_sensitive_files_are_tracked() -> None:
    try:
        tracked = subprocess.run(
            ["git", "ls-files"],  # noqa: S607
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as err:
        pytest.skip(f"git is unavailable: {err}")

    from fnmatch import fnmatch  # noqa: PLC0415

    for path in tracked:
        name = Path(path).name
        assert not any(fnmatch(name, pattern) for pattern in SENSITIVE_PATTERNS), path


def test_license_and_readme_describe_the_install_layout() -> None:
    readme = _read(ROOT / "README.md")

    assert (ROOT / "LICENSE").is_file()
    assert "/config/custom_components/template_humidifier" in readme
    assert "Show beta versions" in readme
    assert "template_humidifier:" in readme


# --- workflows -------------------------------------------------------------


def test_release_workflow_runs_every_gate_before_publishing() -> None:
    release = _read(WORKFLOWS / "release.yml")
    required = (
        "uv run ruff check .",
        "uv run basedpyright",
        "uv run pytest",
        "scripts/check_release_tag.py",
        "home-assistant/actions/hassfest@",
        "hacs/action@",
        "scripts/build_release.py",
        "cmp release/",
        "softprops/action-gh-release@",
    )

    positions = [release.index(step) for step in required]

    assert positions == sorted(positions)
    assert '- "v*"' in release


def test_release_marks_previews_as_prereleases_and_never_latest() -> None:
    release = _read(WORKFLOWS / "release.yml")

    assert "prerelease: ${{ steps.release_metadata.outputs.prerelease }}" in release
    assert (
        "make_latest: ${{ steps.release_metadata.outputs.prerelease == 'false' }}"
        in release
    )


def test_release_write_access_is_limited_to_the_publish_job() -> None:
    release = _read(WORKFLOWS / "release.yml")

    assert re.search(r"(?m)^permissions:\n  contents: read$", release)
    publish_job = (
        r"(?ms)^  release:\n.*?^    needs: validate$.*?"
        r"^    permissions:\n      contents: write$"
    )
    assert re.search(publish_job, release)
    assert release.count("contents: write") == 1


@pytest.mark.parametrize("workflow", ["release.yml", "validate.yml"])
def test_actions_are_pinned_and_checkout_drops_credentials(workflow: str) -> None:
    text = _read(WORKFLOWS / workflow)
    revisions = cast(
        "list[str]", re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*[^@\s]+@([^\s#]+)", text)
    )

    assert revisions
    for revision in revisions:
        assert re.fullmatch(r"[0-9a-f]{40}", revision), revision
    assert text.count("persist-credentials: false") == text.count(
        "uses: actions/checkout@"
    )


def test_validation_workflow_is_read_only_and_runs_the_gates() -> None:
    text = _read(WORKFLOWS / "validate.yml")

    assert re.search(r"(?m)^permissions:\n  contents: read$", text)
    assert "contents: write" not in text
    for gate in (
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run basedpyright",
        "uv run pytest --cov --cov-branch --cov-fail-under=95",
        "home-assistant/actions/hassfest@",
        "!github.event.repository.private",
    ):
        assert gate in text, gate


def test_dependabot_tracks_actions_and_python_dependencies_weekly() -> None:
    text = _read(ROOT / ".github" / "dependabot.yml")

    assert 'package-ecosystem: "github-actions"' in text
    assert 'package-ecosystem: "uv"' in text
    assert text.count('interval: "weekly"') == 2
