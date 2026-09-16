"""Deterministic publish preflight safety scans."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from get_gited.adapters.command import CommandRequest, CommandRunner

SECRET_FILENAMES = frozenset(
    {
        ".env",
        "credentials.json",
        ".npmrc",
    }
)
SECRET_NAME_PATTERNS = (
    re.compile(r"^\.env\..+$"),
    re.compile(r".*\.pem$", re.I),
    re.compile(r".*\.key$", re.I),
    re.compile(r".*\.p12$", re.I),
    re.compile(r".*\.pfx$", re.I),
    re.compile(r"^service-account.*\.json$", re.I),
    re.compile(r".*\.session$"),
    re.compile(r".*\.session-journal$"),
)

SECRET_CONTENT_PATTERNS = (
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "Possible GitHub token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "Possible GitHub token"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "Possible API token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "Possible AWS access key"),
    (
        re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"),
        "Possible private key",
    ),
)

# GitHub hard limit is 100 MiB
GITHUB_HARD_LIMIT = 100 * 1024 * 1024
LARGE_FILE_WARN = 50 * 1024 * 1024

SKIP_SCAN_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


class FindingSeverity(StrEnum):
    WARNING = "warning"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class Finding:
    kind: str
    path: str | None
    summary: str
    severity: FindingSeverity


@dataclass(frozen=True, slots=True)
class SafetyReport:
    findings: tuple[Finding, ...]

    @property
    def risk(self) -> str:
        if any(f.severity == FindingSeverity.BLOCK for f in self.findings):
            return "BLOCKED"
        if self.findings:
            return "WARNING"
        return "SAFE"


def redact_secret(value: str) -> str:
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def filename_looks_secret(name: str) -> bool:
    return name in SECRET_FILENAMES or any(p.match(name) for p in SECRET_NAME_PATTERNS)


def scan_paths_for_secrets(root: Path, rel_paths: tuple[str, ...]) -> SafetyReport:
    """Scan specific repo-relative paths (staged files). No git add."""

    findings: list[Finding] = []
    for rel in rel_paths:
        path = root / Path(rel)
        if filename_looks_secret(path.name):
            findings.append(
                Finding(
                    kind="secret_file",
                    path=rel,
                    summary=f"Sensitive filename: {rel}",
                    severity=FindingSeverity.BLOCK,
                )
            )
            continue
        if not path.is_file():
            continue
        findings.extend(_content_and_size_findings(path, rel))
    return SafetyReport(findings=tuple(findings))


def scan_tree_for_publish(root: Path) -> SafetyReport:
    findings: list[Finding] = []
    for path in _iter_files(root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if filename_looks_secret(path.name):
            findings.append(
                Finding(
                    kind="secret_file",
                    path=rel,
                    summary=f"Sensitive filename: {rel}",
                    severity=FindingSeverity.BLOCK,
                )
            )
            continue
        findings.extend(_content_and_size_findings(path, rel))

    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        findings.append(
            Finding(
                kind="gitignore",
                path=".gitignore",
                summary="Missing .gitignore",
                severity=FindingSeverity.WARNING,
            )
        )
    return SafetyReport(findings=tuple(findings))


def scan_git_history_for_secrets(
    runner: CommandRunner, repo_root: Path
) -> SafetyReport:
    """Scan tracked history for secret filenames (no full blob dump)."""

    findings: list[Finding] = []
    result = runner.run(
        CommandRequest(
            argv=[
                "git",
                "-c",
                "core.quotepath=false",
                "log",
                "--all",
                "--name-only",
                "--pretty=format:",
            ],
            cwd=repo_root,
        )
    )
    if result.exit_code != 0:
        return SafetyReport(findings=())

    seen: set[str] = set()
    for line in result.stdout.splitlines():
        name = Path(line.strip()).name
        if not name or name in seen:
            continue
        if filename_looks_secret(name):
            seen.add(name)
            findings.append(
                Finding(
                    kind="secret_history",
                    path=line.strip(),
                    summary=(
                        "Potential credential exists in Git history: "
                        f"{line.strip()}. Manual review required."
                    ),
                    severity=FindingSeverity.BLOCK,
                )
            )
    return SafetyReport(findings=tuple(findings))


def _content_and_size_findings(path: Path, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        size = path.stat().st_size
    except OSError:
        return findings
    if size >= GITHUB_HARD_LIMIT:
        findings.append(
            Finding(
                kind="large_file",
                path=rel,
                summary=f"File exceeds GitHub hard limit: {rel}",
                severity=FindingSeverity.BLOCK,
            )
        )
    elif size >= LARGE_FILE_WARN:
        findings.append(
            Finding(
                kind="large_file",
                path=rel,
                summary=f"Large file: {rel} ({size} bytes)",
                severity=FindingSeverity.WARNING,
            )
        )
    if size > 1_000_000:
        return findings
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    for pattern, label in SECRET_CONTENT_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(
                Finding(
                    kind="secret_content",
                    path=rel,
                    summary=f"{label}: {redact_secret(match.group(0))}",
                    severity=FindingSeverity.BLOCK,
                )
            )
            break
    return findings


def combine_reports(*reports: SafetyReport) -> SafetyReport:
    findings: list[Finding] = []
    for report in reports:
        findings.extend(report.findings)
    return SafetyReport(findings=tuple(findings))


def _iter_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & SKIP_SCAN_DIRS:
            continue
        yield path
