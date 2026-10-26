"""Visual layer for the app: injected CSS and small HTML components.

Colors, fonts, and radii live in .streamlit/config.toml (the theme). This module adds what
the theme can't: a hero banner, page headers, cards, chips, offer cards, and chat-bubble
styling. Every dynamic string is HTML-escaped here, so callers pass plain text.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

CSS = """
<style>
.block-container {max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem;}
h1, h2, h3 {letter-spacing: -0.015em;}

.nt-hero {
  background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 55%, #0EA5E9 100%);
  color: #fff; border-radius: 20px; padding: 2.4rem 2.6rem; margin-bottom: 1.6rem;
  box-shadow: 0 12px 32px rgba(79, 70, 229, .25);
}
.nt-hero h1 {color: #fff; font-size: 2.4rem; margin: 0 0 .5rem 0; padding: 0;}
.nt-hero p {color: rgba(255, 255, 255, .92); font-size: 1.08rem; margin: 0; max-width: 760px;
  line-height: 1.55;}
.nt-eyebrow {text-transform: uppercase; letter-spacing: .09em; font-size: .74rem;
  font-weight: 650; color: #6366F1; margin-bottom: .25rem;}
.nt-hero .nt-eyebrow {color: rgba(255, 255, 255, .78);}

.nt-header {margin-bottom: 1.3rem;}
.nt-header h1 {margin: 0; padding: 0; font-size: 2.05rem;}
.nt-header p {color: #6B7280; margin: .35rem 0 0 0; font-size: 1.02rem; max-width: 820px;}

.nt-card {background: #fff; border: 1px solid #E3E6F0; border-radius: 16px;
  padding: 1.15rem 1.25rem; height: 100%; box-shadow: 0 1px 3px rgba(16, 24, 40, .05);}
.nt-card h4 {margin: .45rem 0 .3rem 0; font-size: 1.02rem; padding: 0;}
.nt-card p {color: #6B7280; font-size: .92rem; margin: 0; line-height: 1.5;}
.nt-icon {font-size: 1.45rem; width: 2.6rem; height: 2.6rem; border-radius: 12px;
  background: #EEF0FA; display: flex; align-items: center; justify-content: center;}

.nt-step {display: flex; gap: .85rem; align-items: flex-start; padding: .5rem 0;}
.nt-step-num {flex: 0 0 1.9rem; height: 1.9rem; border-radius: 999px; background: #EEF0FA;
  color: #4F46E5; font-weight: 700; display: flex; align-items: center;
  justify-content: center; font-size: .88rem;}
.nt-step b {display: block; font-size: .98rem;}
.nt-step span {color: #6B7280; font-size: .9rem;}

.nt-chips {margin: .1rem 0 .9rem 0;}
.nt-chip {display: inline-block; padding: .2rem .65rem; border-radius: 999px; font-size: .78rem;
  font-weight: 600; margin: 0 .35rem .35rem 0; background: #EEF0FA; color: #4338CA;
  border: 1px solid #E0E3F7;}
.nt-chip.green {background: #ECFDF5; color: #047857; border-color: #D1FAE5;}
.nt-chip.amber {background: #FFFBEB; color: #B45309; border-color: #FDE68A;}
.nt-chip.red {background: #FEF2F2; color: #B91C1C; border-color: #FECACA;}
.nt-chip.gray {background: #F3F4F6; color: #374151; border-color: #E5E7EB;}

.nt-offer {border: 1px solid #C7D2FE; background: #F5F7FF; border-radius: 12px;
  padding: .7rem .9rem .45rem; margin-top: .5rem;}
.nt-offer-head {display: flex; justify-content: space-between; align-items: center;
  font-size: .74rem; font-weight: 650; color: #4338CA; text-transform: uppercase;
  letter-spacing: .06em; margin-bottom: .5rem;}
.nt-points {background: #4F46E5; color: #fff; border-radius: 999px; padding: .16rem .65rem;
  font-size: .78rem; text-transform: none; letter-spacing: 0;}
.nt-term {display: inline-block; background: #fff; border: 1px solid #E0E3F7;
  border-radius: 8px; padding: .22rem .55rem; margin: 0 .35rem .35rem 0; font-size: .86rem;}
.nt-term b {color: #6B7280; font-weight: 500;}
.nt-issue {margin: 0 0 .55rem 0;}
.nt-issue-name {font-weight: 600; font-size: .86rem; margin-bottom: .25rem; color: #374151;}
.nt-pt {display: inline-block; border: 1px solid #E3E6F0; background: #fff; border-radius: 8px;
  padding: .16rem .5rem; margin: 0 .3rem .3rem 0; font-size: .82rem;}
.nt-pt strong {color: #4338CA; margin-left: .25rem;}
.nt-pt.best {background: #ECFDF5; border-color: #A7F3D0;}
.nt-pt.best strong {color: #047857;}
.nt-stats {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: .7rem; margin: .4rem 0 1rem;}
.nt-stat {background: #fff; border: 1px solid #E3E6F0; border-radius: 14px; padding: .8rem 1rem;
  box-shadow: 0 1px 3px rgba(16, 24, 40, .04);}
.nt-stat-label {font-size: .78rem; color: #6B7280; font-weight: 500;}
.nt-stat-value {font-size: 1.55rem; font-weight: 700; color: #111827; line-height: 1.25;}
.nt-stat-sub {font-size: .78rem; font-weight: 600; margin-top: .15rem;}
.nt-stat-sub.green {color: #047857;} .nt-stat-sub.red {color: #B91C1C;}
.nt-stat-sub.gray {color: #6B7280;}
.nt-empty {color: #9CA3AF; font-size: .9rem; font-style: italic;}

.nt-banner {border-radius: 14px; padding: 1rem 1.2rem; margin: .4rem 0 1rem;
  font-weight: 500; line-height: 1.5;}
.nt-banner.good {background: #ECFDF5; border: 1px solid #A7F3D0; color: #065F46;}
.nt-banner.bad {background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B;}
.nt-banner.info {background: #EEF2FF; border: 1px solid #C7D2FE; color: #3730A3;}

.nt-user {border: 1px solid rgba(165, 180, 252, .25); background: rgba(99, 102, 241, .12);
  border-radius: 12px; padding: .6rem .8rem; font-size: .88rem; margin-bottom: .5rem;}
.nt-user b {font-size: 1rem;}

div[data-testid="stMetric"] {background: #fff; border: 1px solid #E3E6F0;
  border-radius: 14px; padding: .85rem 1rem; box-shadow: 0 1px 3px rgba(16, 24, 40, .04);}
div[data-testid="stChatMessage"] {background: #fff; border: 1px solid #E3E6F0;
  border-radius: 16px; padding: .85rem 1rem; margin-bottom: .7rem;}
div[data-testid="stChatMessage"]:has(.nt-me) {background: #EEF2FF; border-color: #C7D2FE;}
div[data-testid="stForm"] {background: #fff; border-radius: 16px;}
</style>
"""


def md(text: object) -> str:
    """Escape text for st.markdown/st.write: a pair of "$" would otherwise render as LaTeX
    (case materials and chat are full of dollar amounts)."""
    return str(text).replace("$", "\\$")


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def hero(eyebrow: str, title: str, text: str) -> None:
    _html(
        f'<div class="nt-hero"><div class="nt-eyebrow">{escape(eyebrow)}</div>'
        f"<h1>{escape(title)}</h1><p>{escape(text)}</p></div>"
    )


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eb = f'<div class="nt-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    sub = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    _html(f'<div class="nt-header">{eb}<h1>{escape(title)}</h1>{sub}</div>')


def cards(items: list[tuple[str, str, str]]) -> None:
    """A row of (icon, title, text) cards."""
    for col, (icon, title, text) in zip(st.columns(len(items)), items, strict=True):
        with col:
            _html(
                f'<div class="nt-card"><div class="nt-icon">{escape(icon)}</div>'
                f"<h4>{escape(title)}</h4><p>{escape(text)}</p></div>"
            )


def steps(items: list[tuple[str, str]]) -> None:
    _html(
        "".join(
            f'<div class="nt-step"><div class="nt-step-num">{n}</div>'
            f"<div><b>{escape(title)}</b><span>{escape(text)}</span></div></div>"
            for n, (title, text) in enumerate(items, start=1)
        )
    )


def chips(items: list[tuple[str, str]]) -> None:
    """Inline pills; tone is one of '', 'green', 'amber', 'red', 'gray'."""
    _html(
        '<div class="nt-chips">'
        + "".join(f'<span class="nt-chip {tone}">{escape(text)}</span>' for text, tone in items)
        + "</div>"
    )


def offer_card(title: str, terms: list[tuple[str, str]], badge: str) -> str:
    """HTML for a structured offer: issue/option pills and a points badge."""
    body = "".join(
        f'<span class="nt-term"><b>{escape(name)}:</b> {escape(label)}</span>'
        for name, label in terms
    )
    return (
        f'<div class="nt-offer"><div class="nt-offer-head"><span>{escape(title)}</span>'
        f'<span class="nt-points">{escape(badge)}</span></div>{body}</div>'
    )


def points_block(rows: list[tuple[str, list[tuple[str, float]]]], walk_away: float) -> None:
    """A role's point table as one line of option pills per issue; the best option is green."""
    out = []
    for name, options in rows:
        top = max(pts for _, pts in options)
        pills = "".join(
            f'<span class="nt-pt{" best" if pts == top else ""}">{escape(label)}'
            f"<strong>{pts:g}</strong></span>"
            for label, pts in options
        )
        out.append(
            f'<div class="nt-issue"><div class="nt-issue-name">{escape(name)}</div>{pills}</div>'
        )
    out.append(f'<span class="nt-chip amber">Walk-away (no deal): {walk_away:g} points</span>')
    _html("".join(out))


def stats(items: list[tuple[str, str, str, str]]) -> None:
    """Responsive stat cards: (label, value, sub-text, tone of sub-text)."""
    cells = "".join(
        f'<div class="nt-stat"><div class="nt-stat-label">{escape(label)}</div>'
        f'<div class="nt-stat-value">{escape(value)}</div>'
        + (f'<div class="nt-stat-sub {tone}">{escape(sub)}</div>' if sub else "")
        + "</div>"
        for label, value, sub, tone in items
    )
    _html(f'<div class="nt-stats">{cells}</div>')


def html(markup: str) -> None:
    _html(markup)


def banner(text: str, tone: str = "info") -> None:
    _html(f'<div class="nt-banner {tone}">{escape(text)}</div>')


ASSETS = Path(__file__).parent / "assets"


def brand() -> None:
    """Logo at the top of the sidebar (above the page navigation)."""
    st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))


def user_badge(pid: str, detail: str) -> None:
    _html(f'<div class="nt-user">Signed in as<br><b>{escape(pid)}</b><br>{escape(detail)}</div>')
