"""Build the deterministic HACS release archive for Template Humidifier.

The archive is rooted at the integration contents so that extracting it into
``/config/custom_components/template_humidifier`` works as HACS expects. It is
byte-for-byte reproducible: entries are sorted, timestamps and permissions are
fixed, text files use LF line endings and nothing is compressed, so the result
does not depend on the platform or the zlib build.
"""

import argparse
import sys
import zipfile
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "template_humidifier"
INTEGRATION_DIR = ROOT / "custom_components" / DOMAIN
DEFAULT_OUTPUT = ROOT / "dist" / f"{DOMAIN}.zip"

# The reviewed runtime allowlist, relative to the integration directory.
RUNTIME_FILES = (
    "__init__.py",
    "brand/icon.png",
    "config.py",
    "const.py",
    "entity.py",
    "humidifier.py",
    "manifest.json",
    "services.yaml",
    "translations/en.json",
    "translations/ko.json",
)
EXCLUDED_DIRS = frozenset({"__pycache__"})
EXCLUDED_PATTERNS = (
    ".env",
    ".env.*",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.db",
    "*.db-*",
    "*token*.json",
    ".storage/*",
    "secrets.yaml",
)
TEXT_SUFFIXES = frozenset({".py", ".json"})
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_FILE_MODE = 0o100644


class ReleasePackageError(ValueError):
    """Raised when the release contents or output path are not acceptable."""


def _first_symlink(path: Path) -> Path | None:
    """Return the first symlink between the integration root and ``path``."""
    candidate = INTEGRATION_DIR
    for part in path.relative_to(INTEGRATION_DIR).parts:
        candidate /= part
        if candidate.is_symlink():
            return candidate
    return None


def _require_allowlist() -> set[Path]:
    """Return the allowlisted paths after checking they exist and are real files."""
    allowed = {INTEGRATION_DIR / name for name in RUNTIME_FILES}
    for path in sorted(allowed):
        if (link := _first_symlink(path)) is not None:
            relative = link.relative_to(INTEGRATION_DIR).as_posix()
            message = f"refusing symlinked path: {relative}"
            raise ReleasePackageError(message)

    missing = sorted(
        path.relative_to(INTEGRATION_DIR).as_posix()
        for path in allowed
        if not path.is_file()
    )
    if missing:
        message = f"missing required files: {', '.join(missing)}"
        raise ReleasePackageError(message)
    return allowed


def _inspect(path: Path) -> str | None:
    """Return the relative name of a candidate file, or None when it is skipped."""
    relative = path.relative_to(INTEGRATION_DIR)
    if path.is_symlink():
        message = f"refusing symlinked path: {relative.as_posix()}"
        raise ReleasePackageError(message)
    if not path.is_file() or EXCLUDED_DIRS.intersection(relative.parts):
        return None
    name = relative.as_posix()
    if any(fnmatch(name, pattern) for pattern in EXCLUDED_PATTERNS):
        message = f"refusing sensitive or generated file: {name}"
        raise ReleasePackageError(message)
    return name


def validate_package_files() -> list[Path]:
    """Return the files to archive after proving the tree matches the allowlist."""
    if not INTEGRATION_DIR.is_dir():
        message = f"missing integration directory: {INTEGRATION_DIR}"
        raise ReleasePackageError(message)

    allowed = _require_allowlist()
    package_files: list[Path] = []
    unexpected: list[str] = []
    for path in sorted(INTEGRATION_DIR.rglob("*")):
        if (name := _inspect(path)) is None:
            continue
        if path in allowed:
            package_files.append(path)
        else:
            unexpected.append(name)

    if unexpected:
        message = f"unexpected integration files: {', '.join(unexpected)}"
        raise ReleasePackageError(message)
    return package_files


def resolve_output(path: Path) -> Path:
    """Resolve the output path and keep it inside the repository."""
    output = (path if path.is_absolute() else ROOT / path).resolve()
    if output.suffix.lower() != ".zip":
        message = "output path must end in .zip"
        raise ReleasePackageError(message)
    if not output.is_relative_to(ROOT):
        message = f"output must stay inside the repository: {output}"
        raise ReleasePackageError(message)
    return output


def _archive_bytes(path: Path) -> bytes:
    """Return file content with platform line endings normalized for text."""
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return data


def build_archive(path: Path, package_files: list[Path] | None = None) -> Path:
    """Write the release archive and return its resolved path."""
    files = validate_package_files() if package_files is None else package_files
    output = resolve_output(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for package_file in sorted(
            files, key=lambda item: item.relative_to(INTEGRATION_DIR).as_posix()
        ):
            info = zipfile.ZipInfo(
                package_file.relative_to(INTEGRATION_DIR).as_posix(),
                date_time=ZIP_TIMESTAMP,
            )
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = ZIP_FILE_MODE << 16
            archive.writestr(info, _archive_bytes(package_file))
    return output


def main(argv: Sequence[str] | None = None) -> int:
    """Run the release builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="validate the package contents without writing an archive",
    )
    args = parser.parse_args(argv)
    output_path = Path(str(args.output))  # pyright: ignore[reportAny]

    try:
        files = validate_package_files()
        if args.check:  # pyright: ignore[reportAny]
            print(f"Release package check passed ({len(files)} files).")
            return 0
        output = build_archive(output_path, files)
    except ReleasePackageError as err:
        print(f"Release package failed: {err}", file=sys.stderr)
        return 1

    print(f"Wrote {output.relative_to(ROOT)} ({len(files)} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
