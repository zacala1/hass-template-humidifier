---
applyTo: "**"
---

# Home Assistant development contract

This is an original first-party Home Assistant custom integration. Do not introduce fork, upstream-sync, or patch-carrying assumptions unless repository history proves they apply.

- Canonical domain: `template_humidifier`. Keep it synchronized across the integration directory, manifest, translations, services, tests, HACS metadata, archive, and documentation.
- Supported baseline: Home Assistant `2026.8.3` on its required Python `3.14.2` runtime. Verify both from official HA sources and the APIs actually used; never copy another project's floor.
- Use SemVer base versions with PEP 440 prereleases. Before `1.0`, incompatible changes increment minor; compatible features increment minor; compatible fixes increment patch. Both `X.Y.ZbN` and `X.Y.ZrcN` are valid preview channels: use beta while feedback may change behavior or scope, and RC when the owner deliberately declares a release candidate whose intended scope is complete and final or manual validation remains. Honor an explicit owner choice and never silently switch channels; after publishing an RC for a base version, do not move that base version back to beta.
- Treat tags and published assets as immutable. Tag exactly `v<manifest-version>`, increase prerelease serials monotonically, and promote stable from a fresh fully validated commit.
- Keep all version declarations, compatibility metadata, lock data, documentation, release checks, archive name, and GitHub tag synchronized.
- Declare and exactly pin external runtime requirements in `manifest.json`; prove the release ZIP works from a clean Home Assistant installation at the minimum and latest supported patch.
- Keep Config Entry setup, refresh, reload, unload, maintenance, persistence, and backup lifecycles atomic, idempotent, rollback-safe, and off the event loop for blocking I/O.
- Document storage, privacy defaults, retention, export, migration, backup, and destructive operations. Require authorization and explicit confirmation for irreversible actions.
- Run Ruff lint/format, strict BasedPyright, pytest with branch coverage at least 95%, HACS, Hassfest, deterministic archive checks, and clean artifact smoke tests before publishing.
- Pin third-party Actions by full SHA, use minimum workflow permissions, maintain weekly dependency updates, and review HA deprecations and Python-runtime changes before compatibility releases.
- Publish beta/RC tags only as GitHub prereleases and never as Latest. Require explicit owner approval and a fresh full validation run before every stable release.

