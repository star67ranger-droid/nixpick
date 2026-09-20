"""Feuilles de style Textual générées depuis la palette."""

from __future__ import annotations

from theme import TuiColors


def build_app_css(c: TuiColors) -> str:
    return f"""
    Screen {{
        background: {c.background};
        layout: vertical;
    }}

    #chrome {{
        height: 1;
        color: {c.text};
        padding: 0 1;
        background: {c.surface};
    }}

    #search-row {{
        height: 3;
        padding: 0 1;
        background: {c.surface};
    }}

    #search-icon {{
        width: 3;
        height: 3;
        content-align: center middle;
        color: {c.primary};
        background: {c.surface};
    }}

    #search {{
        height: 3;
        border: round {c.text_muted};
        background: {c.surface};
        color: {c.text};
        padding: 0 1;
    }}

    #search:focus {{
        border: round {c.primary};
    }}

    #main {{
        height: 1fr;
        padding: 0 1 0 1;
    }}

    #results {{
        width: 1fr;
        border: round {c.text_muted};
        border-title-color: {c.primary};
        border-title-align: left;
        background: {c.surface};
        scrollbar-color: {c.primary};
        scrollbar-background: {c.background};
    }}

    #detail-panel {{
        width: 1fr;
        border: round {c.text_muted};
        border-title-color: {c.detail_title};
        border-title-align: left;
        background: {c.surface};
        padding: 1 2;
    }}

    OptionList > .option-list--option-highlighted {{
        background: {c.list_highlight_bg};
        color: {c.accent};
        text-style: bold;
    }}

    #detail-name {{
        text-style: bold;
        color: {c.primary};
    }}

    #detail-meta {{
        color: {c.text_muted};
        margin-bottom: 1;
    }}

    #detail-body {{
        color: {c.text};
    }}

    #detail-hint {{
        color: {c.success};
        margin-top: 2;
    }}

    #footerbar {{
        height: 1;
        color: {c.text_muted};
        padding: 0 1;
        background: {c.surface};
    }}

    .key {{
        color: {c.accent};
    }}

    #help-box {{
        width: 64;
        background: {c.surface_elevated};
        border: round {c.accent_alt};
        padding: 1 2;
        margin: 2 4;
    }}

    Screen.transparent {{
        background: ansi_default;
    }}
    Screen.transparent #chrome,
    Screen.transparent #search-row,
    Screen.transparent #search-icon,
    Screen.transparent #footerbar,
    Screen.transparent #main {{
        background: ansi_default;
    }}
    Screen.transparent #search {{
        background: ansi_default;
        border: round {c.text_muted};
    }}
    Screen.transparent #search:focus {{
        border: round {c.primary};
    }}
    Screen.transparent #results {{
        background: ansi_default;
        border: round {c.text_muted};
        scrollbar-background: ansi_default;
        scrollbar-background-hover: ansi_default;
        scrollbar-background-active: ansi_default;
    }}
    Screen.transparent #detail-panel {{
        background: ansi_default;
        border: round {c.text_muted};
    }}
    Screen.transparent OptionList {{
        background: ansi_default;
    }}
    Screen.transparent OptionList > .option-list--option-highlighted {{
        background: ansi_default;
        color: {c.accent};
        text-style: bold;
    }}
    Screen.transparent #help-box {{
        background: ansi_default;
    }}
    """


def build_confirm_add_css(c: TuiColors) -> str:
    return f"""
    ConfirmAddModal {{
        align: center middle;
    }}

    #confirm-box {{
        width: 78;
        background: {c.surface_elevated};
        border: round {c.accent};
        padding: 1 2;
    }}

    #modal-title {{
        color: {c.text};
        margin-bottom: 0;
    }}

    #modal-attr {{
        text-style: bold;
        color: {c.primary};
        margin-top: 1;
    }}

    #modal-path {{
        color: {c.text_muted};
    }}

    #modal-desc {{
        color: {c.text};
        margin: 1 0 0 0;
    }}

    #modal-badge {{
        color: {c.warning};
        margin-top: 1;
    }}

    #diff-panel {{
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 0 1 1 1;
        background: {c.background};
        border: round {c.text_muted};
        border-title-color: {c.detail_title};
        border-title-align: left;
    }}

    #diff {{
        width: 1fr;
        height: auto;
    }}

    #modal-actions {{
        height: 1;
        margin-top: 1;
        color: {c.text_muted};
    }}

    ConfirmAddModal.transparent {{
        background: ansi_default;
    }}

    ConfirmAddModal.transparent #confirm-box {{
        background: ansi_default;
        border: round {c.text_muted};
    }}

    ConfirmAddModal.transparent #diff-panel {{
        background: ansi_default;
        border: round {c.text_muted};
    }}
    """


def build_confirm_remove_css(c: TuiColors) -> str:
    return f"""
    ConfirmRemoveModal {{
        align: center middle;
    }}

    #confirm-box {{
        width: 78;
        background: {c.surface_elevated};
        border: round {c.danger};
        padding: 1 2;
    }}

    #modal-title {{
        color: {c.danger};
        margin-bottom: 0;
    }}

    #modal-attr {{
        text-style: bold;
        color: {c.primary};
        margin-top: 1;
    }}

    #modal-path {{
        color: {c.text_muted};
    }}

    #modal-badge {{
        color: {c.warning};
        margin-top: 1;
    }}

    #diff-panel {{
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 0 1 1 1;
        background: {c.background};
        border: round {c.text_muted};
        border-title-color: {c.danger};
        border-title-align: left;
    }}

    #diff {{
        width: 1fr;
        height: auto;
    }}

    #modal-actions {{
        height: 1;
        margin-top: 1;
        color: {c.text_muted};
    }}

    ConfirmRemoveModal.transparent {{
        background: ansi_default;
    }}

    ConfirmRemoveModal.transparent #confirm-box {{
        background: ansi_default;
        border: round {c.danger};
    }}

    ConfirmRemoveModal.transparent #diff-panel {{
        background: ansi_default;
        border: round {c.text_muted};
    }}
    """


def build_full_tui_css(c: TuiColors) -> str:
    return (
        build_app_css(c)
        + build_confirm_add_css(c)
        + build_confirm_remove_css(c)
    )
