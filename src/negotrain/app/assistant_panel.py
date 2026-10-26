"""Persistent right-hand chat, rendered as a fragment so asking preserves page drafts."""

from __future__ import annotations

import streamlit as st

from negotrain.app.style import md
from negotrain.assistant import (
    AssistantConversation,
    AssistantMessage,
    answer_question,
    context_sections,
    conversation_key,
    visible_sources,
)
from negotrain.cases.documents import UPLOAD_TYPES, extract_documents
from negotrain.feedback import Debrief
from negotrain.llm import LLMRefusal
from negotrain.prep import Prep, prep_key
from negotrain.profiling import build_profile
from negotrain.schemas import Case, Session, SourceDocument
from negotrain.sessions import SessionStore


def _selected_session(case: Case, role_id: str, page: str, pid: str) -> Session | None:
    store = SessionStore()
    if page == "Feedback":
        sid = st.session_state.get("assistant_feedback_session")
        try:
            session = store.load(sid) if sid else None
        except (OSError, ValueError):
            session = None
    elif page == "Real negotiation":
        sessions = [
            s
            for s in store.for_participant(pid)
            if s.case_id == case.id and s.user_role_id == role_id and s.kind == "real"
        ]
        session = sessions[-1] if sessions else None
    else:
        session = st.session_state.get("session")
    if session is not None and (
        session.case_id != case.id
        or session.user_role_id != role_id
        or session.participant_id != pid
    ):
        return None
    return session


def _draw_chat(slot, conversation: AssistantConversation) -> None:
    with slot.container():
        if not conversation.messages and not conversation.pending_question:
            st.caption(
                "Ask a factual question, unpack your brief, or explore how a message might land."
            )
        for message in conversation.messages:
            with st.chat_message(message.role):
                st.markdown(md(message.content))
        if conversation.pending_question:
            with st.chat_message("user"):
                st.markdown(md(conversation.pending_question))


@st.fragment
def render(page: str) -> None:
    # Import here to keep the pure assistant service independent from page/UI state.
    from negotrain.app import views

    with st.container(key="personal_assistant"):
        st.markdown("### Your assistant")
        current = views.active_scenario()
        if current is None:
            st.caption("Choose a case and your role to ask questions about your materials.")
            return
        case, role_id = current
        pid = views.participant().id
        key = conversation_key(pid, case.id, role_id)
        store = SessionStore()
        conversation = store.load_artifact(key, "assistant", AssistantConversation)
        if (
            conversation is None
            or conversation.case_id != case.id
            or conversation.role_id != role_id
        ):
            conversation = AssistantConversation(case_id=case.id, role_id=role_id)
        st.caption(f"{case.role(role_id).name} · Your chat follows you between steps.")
        if st.button("New chat", key=f"assistant_clear_{key}", type="tertiary"):
            conversation.messages.clear()
            conversation.pending_question = None
            store.save_artifact(key, "assistant", conversation)

        with st.expander("Sources and context"):
            st.caption(
                "I use your case, your role sheet, your brief, and the conversation or feedback "
                "you can see. Possible responses are hypotheses."
            )
            st.caption(
                "Add documents you can read as this role. "
                "Older case imports may not have retained their original text."
            )
            files = st.file_uploader(
                "Add source documents",
                type=list(UPLOAD_TYPES),
                accept_multiple_files=True,
                key=f"assistant_sources_{key}",
            )
            if st.button(
                "Add to assistant", disabled=not files, key=f"assistant_add_sources_{key}"
            ):
                documents, warnings = extract_documents((f.name, f.getvalue()) for f in files)
                for warning in warnings:
                    st.warning(warning)
                by_name = {s.name: s for s in conversation.sources}
                for name, text in documents.items():
                    label = f"Added: {name}"
                    by_name[label] = SourceDocument(name=label, text=text, visible_to=[role_id])
                conversation.sources = list(by_name.values())
                store.save_artifact(key, "assistant", conversation)
                if documents:
                    st.success(f"Added {len(documents)} source document(s).")
            sources = visible_sources(case, role_id, conversation)
            if sources:
                selected = st.selectbox(
                    "Read a source",
                    range(len(sources)),
                    format_func=lambda i: sources[i].name,
                    key=f"assistant_source_view_{key}",
                )
                source = sources[selected]
                st.text_area(
                    "Extracted text",
                    source.text[:20000],
                    height=160,
                    disabled=True,
                    key=f"assistant_source_text_{key}_{selected}",
                )
                st.download_button(
                    "Download source text",
                    source.text,
                    file_name="source.txt",
                    mime="text/plain",
                    key=f"assistant_source_download_{key}",
                )
            else:
                st.caption(
                    "No original source text is available for this role yet. "
                    "Your case and brief are still available."
                )

        with st.container(height=420, border=False, key="assistant_transcript", autoscroll=True):
            chat_slot = st.empty()
            _draw_chat(chat_slot, conversation)
        online = views.online()
        if not online:
            st.caption(
                "Choose Claude Code or an API key in Settings to ask questions. "
                "Your saved chat and sources remain available."
            )
        prompt = st.chat_input(
            "Ask about your case or a possible response…",
            key=f"assistant_question_{key}",
            max_chars=4000,
            disabled=not online,
        )
        retry_slot = st.empty()
        retry = False
        retry_shown = bool(conversation.pending_question)
        if retry_shown:
            with retry_slot:
                retry = st.button("Retry answer", key=f"assistant_retry_{key}", disabled=not online)
        if not online or not (prompt or retry):
            return
        if prompt:
            conversation.pending_question = prompt.strip()
        question = conversation.pending_question
        if not question:
            return
        store.save_artifact(key, "assistant", conversation)
        _draw_chat(chat_slot, conversation)
        session = _selected_session(case, role_id, page, pid)
        prep = store.load_artifact(prep_key(pid, case.id, role_id), "prep", Prep)
        debrief = (
            store.load_artifact(session.id, "feedback", Debrief)
            if session and page == "Feedback"
            else None
        )
        recent_questions = " ".join(
            m.content for m in conversation.messages[-4:] if m.role == "user"
        )
        sections = context_sections(
            case,
            role_id,
            page,
            question=f"{question} {recent_questions}",
            sources=sources,
            prep=prep,
            session=session,
            debrief=debrief,
            profile=build_profile(pid, views.history(pid)).model_dump()
            if page == "My profile"
            else None,
        )
        try:
            with st.spinner("Reading your context…"):
                answer = answer_question(question, conversation, sections, page, views.llm("low"))
            conversation.messages.extend(
                [
                    AssistantMessage(role="user", content=question),
                    AssistantMessage(role="assistant", content=answer),
                ]
            )
            conversation.pending_question = None
            store.save_artifact(key, "assistant", conversation)
            retry_slot.empty()
            _draw_chat(chat_slot, conversation)
        except Exception as error:  # noqa: BLE001 - keep the question available for retry
            st.error(
                "The assistant couldn't answer that. Rephrase your question or retry."
                if isinstance(error, LLMRefusal)
                else "The assistant couldn't connect or finish the reply. "
                "Your question is saved; retry when ready."
            )
            if not retry_shown:
                with retry_slot:
                    st.button("Retry answer", key=f"assistant_retry_{key}", disabled=not online)
