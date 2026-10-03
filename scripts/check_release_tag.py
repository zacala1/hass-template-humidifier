"""Check that a release tag matches the integration manifest version.

Stable versions are ``X.Y.Z``; preview versions are ``X.Y.ZbN`` (beta) or
``X.Y.ZrcN`` (release candidate). Previews are published as GitHub
pre-releases and never become the *Latest* release.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "custom_components" / "template_humidifier" / "manifest.json"

_VERSION = re.compile(r"\d+\.\d+\.\d+(?P<preview>(?:b|rc)\d+)?")


class ReleaseTagError(ValueError):
    """Raised when the release tag or version metadata is not acceptable."""


def manifest_version() -> str:
    """Return the version declared in the integration manifest."""
    try:
        raw = cast("object", json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as err:
        message = f"cannot read integration manifest: {err}"
        raise ReleaseTagError(message) from err

    manifest = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}
    version = manifest.get("version")
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        message = f"manifest version must be X.Y.Z, X.Y.ZbN or X.Y.ZrcN: {version!r}"
        raise ReleaseTagError(message)
    return version


def validate_release_tag(tag: str) -> None:
    """Raise unless ``tag`` is exactly ``v`` plus the manifest version."""
    expected = f"v{manifest_version()}"
    if tag != expected:
        message = f"release tag {tag!r} does not match manifest version {expected!r}"
        raise ReleaseTagError(message)


def release_is_prerelease(version: str) -> bool:
    """Return whether ``version`` is a beta or release candidate."""
    match = _VERSION.fullmatch(version)
    if match is None:
        message = f"unsupported version format: {version!r}"
        raise ReleaseTagError(message)
    return match.group("preview") is not None


def write_github_output(version: str) -> None:
    """Expose the ``prerelease`` flag to later GitHub Actions steps."""
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        message = "GITHUB_OUTPUT is required with --github-output"
        raise ReleaseTagError(message)
    try:
        with Path(target).open("a", encoding="utf-8", newline="\n") as output:
            flag = str(release_is_prerelease(version)).lower()
            _ = output.write(f"prerelease={flag}\n")
    except OSError as err:
        message = f"cannot write GitHub output: {err}"
        raise ReleaseTagError(message) from err


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the given tag, or the current GitHub ref name."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--github-output", action="store_true")
    _ = parser.add_argument("tag", nargs="?", default=os.environ.get("GITHUB_REF_NAME"))
    args = parser.parse_args(argv)
    tag = str(args.tag) if args.tag else ""  # pyright: ignore[reportAny]
    if not tag:
        parser.error("a release tag or GITHUB_REF_NAME is required")

    try:
        validate_release_tag(tag)
        if args.github_output:  # pyright: ignore[reportAny]
            write_github_output(manifest_version())
    except ReleaseTagError as err:
        print(f"Release tag validation failed: {err}", file=sys.stderr)
        return 1

    print(f"Release tag {tag} matches the integration manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
