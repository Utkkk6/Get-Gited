"""Shared test doubles."""

from __future__ import annotations

from get_gited.adapters.command import CommandRequest, CommandResult


class FakeCommandRunner:
    """Deterministic CommandRunner for unit tests."""

    def __init__(
        self,
        responses: dict[tuple[str, ...], CommandResult] | None = None,
        *,
        default: CommandResult | None = None,
    ) -> None:
        self.responses = responses or {}
        self.default = default
        self.calls: list[CommandRequest] = []

    def run(self, request: CommandRequest) -> CommandResult:
        self.calls.append(request)
        key = tuple(request.argv)
        if key in self.responses:
            return self.responses[key]
        if self.default is not None:
            return self.default
        return CommandResult(
            argv=key,
            exit_code=0,
            stdout="",
            stderr="",
            timed_out=False,
            duration_ms=0,
        )
