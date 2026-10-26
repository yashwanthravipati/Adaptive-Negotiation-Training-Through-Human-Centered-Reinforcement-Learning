"""NegoTrain: the participant-facing rehearsal app.

    streamlit run src/negotrain/app/main.py

Runs locally for one person. The first screen asks for the case files; the other pages
unlock once a scenario (case + role) is chosen. Set ANTHROPIC_API_KEY in .env (or paste it
on the first screen) for Claude; without one, or with NEGOTRAIN_OFFLINE=1, the app runs on
the rule-based counterpart.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="NegoTrain", page_icon="🤝", layout="wide")

from negotrain.app import assistant_panel, views  # noqa: E402

views.sidebar()
views.PAGES.clear()
if views.active_scenario() is None:
    # Nothing is unlocked until there is a scenario: the upload step is the whole app.
    views.PAGES["setup"] = st.Page(views.page_setup, title="Upload case", icon="📂", default=True)
    current_page = st.navigation([views.PAGES["setup"]], position="hidden")
else:
    views.PAGES.update(
        {
            "prepare": st.Page(views.page_prepare, title="Prepare", icon="📋", default=True),
            "rehearse": st.Page(
                views.page_rehearse, title="Rehearse", icon="💬", url_path="rehearse"
            ),
            "feedback": st.Page(
                views.page_feedback, title="Feedback", icon="📊", url_path="feedback"
            ),
            "profile": st.Page(
                views.page_profile, title="My profile", icon="🧭", url_path="profile"
            ),
            "real": st.Page(views.page_real, title="Real negotiation", icon="🤝", url_path="real"),
            "cases": st.Page(views.page_cases, title="Case library", icon="📚", url_path="cases"),
        }
    )
    pages = views.PAGES
    current_page = st.navigation(
        {
            "Practice": [pages["prepare"], pages["rehearse"], pages["feedback"]],
            "Progress": [pages["profile"], pages["real"]],
            "More": [pages["cases"]],
        }
    )

with st.container(key="workspace_shell"):
    main_column, assistant_column = st.columns([3, 1.3], gap="large")
    with main_column, st.container(key="main_page"):
        current_page.run()
    with assistant_column:
        assistant_panel.render(current_page.title)
