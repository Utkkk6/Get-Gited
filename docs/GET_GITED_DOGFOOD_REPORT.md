# Get Gited dogfood report

Date: 2026-09-17

This report records observations from using the current local Get Gited build
against the real Windows workspace. It is documentation only; the underlying
Get Gited behaviours are intentionally not fixed in this task.

## Environment

- OS: Windows
- Get Gited version: `0.1.0`
- Audit branch: `wip/commit-support`
- Audit commit before this report: `37b77b3`
- Launch method: `.venv\Scripts\get-gited.exe` after editable install from the
  local checkout
- GitHub access: `gh` authenticated as the local user
- Workspace roots scanned: 10 explicit development roots (Desktop, Documents,
  PycharmProjects, source, Express Audit, hometasks, moysklad-avito-ops,
  pipeline-benchmark, vk-turn-proxy, youtube-long-video-bookmarklet)
- Measured size of those roots: 21,067,193,868 bytes (19.62 GiB)
- Discovery result: 75 local project entries, 56 unique valid Git roots after
  native physical-root deduplication, 18 project-looking directories without
  Git, and 3 GitHub remote-only repositories

## What worked

- Recursive discovery across multiple Windows roots.
- GitHub matching through the authenticated `gh` CLI, including exact remote
  identities and remote-only repositories.
- Workspace status aggregation with clean, dirty, local-ahead, remote-ahead,
  no-remote, no-Git, and error states.
- Native-Git-compatible ahead/behind inspection after an explicit refresh.
- Sync planning and dry-run preview without changing working trees, refs,
  GitHub, or configuration.
- Fast-forward-only pull planning and push planning with verification-oriented
  operation descriptions.
- Blocking of dirty pulls, existing-remote publish attempts, and other unsafe
  bulk operations.
- Secret and large-file preflight mechanisms; detected values were redacted.
- Doctor checks for Python, Git, `gh`, authentication, and config readability.

## Bugs / incorrect behavior

### Junction duplicate

`PARTY_BOT` was discovered both through a Windows junction and through its
physical target. The planner consequently produced two `PUBLISH` entries for
one physical Git repository.

Expected behavior: one physical Git root must be represented once, regardless
of how many junction/symlink paths reach it.

Minimal regression scenario: scan a root containing a junction to a nested Git
root and also scan the target root; assert one project id and one planned
operation.

### Dubious ownership

Several valid repositories were classified as `ERROR` because Git rejected the
working tree with a dubious-ownership/safe-directory error. Native Git worked
when invoked with a one-process, exact-path override:

```text
git -c safe.directory=<exact path> ...
```

Expected behavior: surface a precise ownership blocker or support an explicit
per-repository safe-directory inspection path. Never require or suggest the
unsafe global setting `safe.directory=*`.

Minimal regression scenario: inspect a repository that Git rejects for
ownership; verify the result distinguishes ownership from repository
corruption and does not mutate global Git config.

### Remote exists but no upstream

Repositories with an existing GitHub remote but no configured upstream were
sometimes displayed as `LOCAL_ONLY`. The planner then proposed `PUBLISH`,
which was correctly blocked because a remote already existed.

Expected behavior: represent this as an exact GitHub match with an explicit
`NO_UPSTREAM`/unknown sync state, not as absence from GitHub. Publishing must
not be proposed when the existing remote is already the canonical remote.

Minimal regression scenario: create a local repository with an exact GitHub
remote, no tracking branch, and a valid commit; assert the status is
`NO_UPSTREAM`/unknown and the planner does not emit `PUBLISH`.

## Missing / weak capabilities observed

- Physical-root deduplication is not reliable for Windows junction paths.
- Ownership errors are not represented distinctly enough for a safe native
  inspection fallback.
- The status model does not preserve the distinction between an exact remote
  match and a genuinely local-only project when no upstream exists.

No additional wishlist items are recorded here.

## Dogfood conclusion

The scan/status/preview workflow was useful for a real multi-root workspace and
prevented unsafe bulk writes. Before using an execute-all path, the three
behaviors above require explicit handling or manual native-Git verification.

## Post-action verification

After the approved repository preservation actions, `status` and `sync --dry-run`
were rerun on `public-main` (`b326e73`) against the same 10 roots. Both exited 0.
Native inspection with exact-path safe.directory returned 75 local entries,
74 physical entries, 56 Git roots and 18 no-Git directories. The PARTY_BOT
junction was counted once by the native reconciliation.

The Get Gited status displayed 83 rows. Dry-run proposed 3 publishes, 8 clones,
18 initializations, 40 blockers and 14 skips. These proposals were not executed.
Several of the 8 apparent remote-only rows were ownership-error local copies,
including newly published PARTY_BOT and SYNQ; they are not truly missing clones.
This is a downstream effect of the observed ownership/matching weakness, not
authorization to clone or publish again. `study` remained LOCAL_ONLY despite an
existing private remote; native Git/GitHub confirmed both sides were empty.

The native verifier confirmed matching published branch SHAs for psycho,
Get Gited WIP, both bot_aiogram variants, Utopia's preserved kostyak branch,
SYNQ and EPBL. PARTY_BOT GitHub SHAs matched via direct `ls-remote`; fetch
failed on a pre-existing invalid internal refs/codex/turn-diffs checkpoint.
That local-ref error was kept separate from successful GitHub publication.
LOPS's external remote could not be authenticated, so its cached AHEAD 4 was
not treated as a current remote fact.

One further observed matching limitation: kostyak has origin pointing to its
original repository and an upstream on the utopia remote (TELECODE_AI). Status
labels it with origin's identity even though the checked-out branch tracks the
product repository. Regression extension: use two GitHub remotes with the
current branch tracking the second and verify identity/sync context stays clear.
