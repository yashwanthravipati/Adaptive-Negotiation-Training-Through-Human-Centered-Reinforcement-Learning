"""NegoTrain: the participant-facing rehearsal app.

    streamlit run src/negotrain/app/main.py

Set ANTHROPIC_API_KEY in .env (or paste it in the sidebar) for the Claude counterpart;
without one, or with NEGOTRAIN_OFFLINE=1, the app runs on the rule-based counterpart.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="NegoTrain", page_icon="🤝", layout="wide")

from negotrain.app import views  # noqa: E402

views.PAGES.update(
    {
        "start": st.Page(
            views.page_start, title="Start", icon="👋", url_path="start", default=True
        ),
        "prepare": st.Page(views.page_prepare, title="Prepare", icon="📂", url_path="prepare"),
        "rehearse": st.Page(views.page_rehearse, title="Rehearse", icon="💬", url_path="rehearse"),
        "feedback": st.Page(views.page_feedback, title="Feedback", icon="📊", url_path="feedback"),
        "profile": st.Page(views.page_profile, title="My profile", icon="🧭", url_path="profile"),
        "real": st.Page(views.page_real, title="Real negotiation", icon="🤝", url_path="real"),
        "cases": st.Page(views.page_cases, title="Case library", icon="📚", url_path="cases"),
    }
)
views.sidebar()
st.navigation(list(views.PAGES.values())).run()
