"""Terminal chrome themes for Get Gited. Presentation only."""

from __future__ import annotations

from enum import StrEnum

SLOGAN = "SIMPLE. SAFE. SYNCED."
PRODUCT = "Get Gited"
TAGLINE = "One workspace. All your Git repos."

_MIN_WIDTH = 72


class UiTheme(StrEnum):
    FRAME = "frame"
    MINIMAL = "minimal"
    HUD = "hud"
    CARDS = "cards"
    POSTER = "poster"


THEME_ORDER: tuple[UiTheme, ...] = (
    UiTheme.FRAME,
    UiTheme.MINIMAL,
    UiTheme.HUD,
    UiTheme.CARDS,
    UiTheme.POSTER,
)

THEME_BLURBS: dict[UiTheme, str] = {
    UiTheme.FRAME: "Classic boxed banner (the first chrome, unclipped)",
    UiTheme.MINIMAL: "One rule, wide table, leftover width goes to About",
    UiTheme.HUD: "Double-line cockpit. Dense and sharp",
    UiTheme.CARDS: "Two lines per project. About is not a stump",
    UiTheme.POSTER: "Stacked title, lots of air, table underneath",
}


def parse_ui_theme(raw: str) -> UiTheme | None:
    text = raw.strip().lower()
    aliases: dict[str, UiTheme] = {
        "1": UiTheme.FRAME,
        "frame": UiTheme.FRAME,
        "box": UiTheme.FRAME,
        "classic": UiTheme.FRAME,
        "2": UiTheme.MINIMAL,
        "minimal": UiTheme.MINIMAL,
        "min": UiTheme.MINIMAL,
        "clean": UiTheme.MINIMAL,
        "3": UiTheme.HUD,
        "hud": UiTheme.HUD,
        "4": UiTheme.CARDS,
        "cards": UiTheme.CARDS,
        "card": UiTheme.CARDS,
        "5": UiTheme.POSTER,
        "poster": UiTheme.POSTER,
    }
    return aliases.get(text)


def next_ui_theme(current: UiTheme) -> UiTheme:
    index = THEME_ORDER.index(current)
    return THEME_ORDER[(index + 1) % len(THEME_ORDER)]


def format_ui_menu(current: UiTheme) -> str:
    lines = [
        f"{PRODUCT}  ·  UI",
        SLOGAN,
        "",
        "Pick a terminal look:",
        "",
    ]
    for index, theme in enumerate(THEME_ORDER, start=1):
        mark = "*" if theme is current else " "
        lines.append(f" {mark} {index}  {theme:<8}  {THEME_BLURBS[theme]}")
    lines.extend(
        [
            "",
            "  gg ui 2          select by number",
            "  gg ui cards      select by name",
            "  u1-u5            switch live inside the picker",
            "",
            f"Current: {current}",
        ]
    )
    return "\n".join(lines)


def format_frame(
    *,
    section: str,
    body: str,
    footer: str,
    hint: str = "",
    theme: UiTheme = UiTheme.MINIMAL,
    width: int = 120,
) -> str:
    """One-screen layout. Body lines are never clipped by the chrome."""

    body = body.rstrip("\n")
    footer = footer.rstrip("\n")
    width = max(_MIN_WIDTH, min(width, 240))
    if theme is UiTheme.FRAME:
        return _layout_frame(section, body, footer, hint, width)
    if theme is UiTheme.HUD:
        return _layout_hud(section, body, footer, hint, width)
    if theme is UiTheme.POSTER:
        return _layout_poster(section, body, footer, hint, width)
    return _layout_minimal(section, body, footer, hint, width)


def format_quit_screen(theme: UiTheme = UiTheme.MINIMAL, width: int = 120) -> str:
    return format_frame(
        section="quit",
        body="No changes.",
        footer=SLOGAN,
        theme=theme,
        width=width,
    )


def content_width(theme: UiTheme, terminal_width: int) -> int:
    """Usable width for the table/cards inside a theme."""

    cols = max(_MIN_WIDTH, terminal_width)
    if theme in {UiTheme.FRAME, UiTheme.HUD}:
        return max(60, cols - 4)
    return max(60, cols)


def _layout_frame(section: str, body: str, footer: str, hint: str, width: int) -> str:
    inner = width - 2
    banner = [
        f"┌{'─' * inner}┐",
        f"│{_banner_row(inner)}│",
        f"│{_fit(f'  {TAGLINE}', inner).ljust(inner)}│",
        f"└{'─' * inner}┘",
    ]
    label = f" {section} "
    dash = max(0, inner - len(label) - 1)
    lines = [
        *banner,
        "",
        f"┌─{label}{'─' * dash}┐",
        *_box_rows(body, inner, "│ ", " │"),
        f"└{'─' * inner}┘",
        "",
        footer,
    ]
    if hint:
        lines.extend(["", hint])
    return "\n".join(lines)


def _layout_hud(section: str, body: str, footer: str, hint: str, width: int) -> str:
    inner = width - 2
    lines = [
        f"╔{'═' * inner}╗",
        f"║{_banner_row(inner)}║",
        f"║{_fit(f'  {section.upper()}', inner).ljust(inner)}║",
        f"╠{'═' * inner}╣",
        *_box_rows(body, inner, "║ ", " ║"),
        f"╚{'═' * inner}╝",
        "",
        footer,
    ]
    if hint:
        lines.extend(["", hint])
    return "\n".join(lines)


def _layout_minimal(section: str, body: str, footer: str, hint: str, width: int) -> str:
    rule = "─" * width
    lines = [
        _banner_row(width).rstrip(),
        TAGLINE,
        rule,
        f"{section}",
        "",
        body,
        "",
        rule,
        footer,
    ]
    if hint:
        lines.extend(["", hint])
    return "\n".join(lines)


def _layout_poster(section: str, body: str, footer: str, hint: str, width: int) -> str:
    lines = [
        PRODUCT.upper(),
        SLOGAN,
        TAGLINE,
        "",
        f"· {section} ·",
        "",
        body,
        "",
        footer,
    ]
    if hint:
        lines.extend(["", hint])
    return "\n".join(lines)


def _banner_row(inner: int) -> str:
    brand = f"  {PRODUCT.upper()}"
    slogan = f"{SLOGAN}  "
    gap = inner - len(brand) - len(slogan)
    if gap < 1:
        return _fit(f"{brand}  {SLOGAN}", inner).ljust(inner)
    return f"{brand}{' ' * gap}{slogan}"


def _box_rows(body: str, inner: int, left: str, right: str) -> list[str]:
    usable = inner - (len(left) - 1) - (len(right) - 1)
    rows: list[str] = []
    for line in body.splitlines() or [""]:
        rows.append(f"{left}{_pad(line, usable)}{right}")
    return rows


def _pad(text: str, width: int) -> str:
    if width <= 0:
        return ""
    return _fit(text, width).ljust(width)


def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"
