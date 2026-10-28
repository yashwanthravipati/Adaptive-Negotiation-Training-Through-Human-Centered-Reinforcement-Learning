"""Pages of the NegoTrain app (MVP of the five workflow stages). main.py wires them up.

The app runs locally for one person, so there is no sign-in: sessions are stored under one
implicit participant id. The first and only screen until a scenario exists is the upload
page (page_setup): case files -> parsed case -> role -> "active scenario". Then Prepare
(brief + training plan), Rehearse, Feedback (post-session only), My profile, and Real
negotiation all work on that scenario; "New scenario" in the sidebar goes back to upload.

Information hiding: the counterpart's sheet is never rendered before a session ends, and the
counterpart agent never receives the user's sheet. Without an API key (or with
NEGOTRAIN_OFFLINE=1) everything runs on the rule-based counterpart and template feedback.
"""

from __future__ import annotations

import hashlib
import os
import random
from html import escape

import streamlit as st
from pydantic import BaseModel

from negotrain import config
from negotrain.app import style
from negotrain.app.style import md
from negotrain.cases import case_library, save_private_case
from negotrain.cases.documents import UPLOAD_TYPES, extract_documents
from negotrain.cases.offers import surplus_share
from negotrain.cases.parser import parse_case, parse_documents
from negotrain.cases.scoring import score_offer
from negotrain.counterpart import TIERS, CounterpartAgent, RuleBasedCounterpart
from negotrain.counterpart.profiles import DIALS
from negotrain.curriculum import ScenarioSpec, counterpart_for, next_scenario
from negotrain.feedback import (
    CoachingReport,
    CounterfactualReport,
    Debrief,
    analyze_session,
    build_report,
    estimate_calls,
    outcome_summary,
)
from negotrain.llm import ClaudeCodeLLM, ClaudeLLM, LLMRefusal, check_api_key
from negotrain.prep import Prep, build_prep, prep_key
from negotrain.profiling import build_profile, extract_features
from negotrain.schemas import Case, CounterpartProfile, Offer, Participant, Session, Turn
from negotrain.sessions import SessionStore

# Filled in by main.py so pages can link to each other with st.switch_page.
PAGES: dict[str, st.Page] = {}

EST_COST_PER_CALL = 0.03  # USD, conservative for claude-opus-5-5 at low effort
DIAL_QUESTIONS = {
    "anchoring": "How extreme was their opening position?",
    "concession_rate": "How readily did they give ground?",
    "cooperativeness": "How open were they to trades / joint problem-solving?",
    "aggression": "How forceful or aggressive were they?",
    "disclosure": "How much did they share about their priorities?",
    "bluffing": "How much did they seem to exaggerate or bluff?",
}


# --------------------------------------------------------------------------- resources


def _key_fingerprint() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "") + os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    return hashlib.sha256(key.encode()).hexdigest()[:8]


BACKENDS = {
    "claude-code": "Claude Code (your plan, no API key)",
    "api": "Anthropic API key",
    "offline": "Offline (no AI)",
}


def default_backend() -> str:
    choice = config.backend()
    if config.offline():
        return "offline"
    if choice in BACKENDS:
        return choice
    if config.claude_bin():
        return "claude-code"
    return "api" if config.has_api_key() else "offline"


def backend() -> str:
    """The backend in use: the Settings choice, falling back to offline when its
    prerequisite (the CLI or a key) is missing."""
    choice = st.session_state.get("backend") or default_backend()
    if choice == "claude-code" and not config.claude_bin():
        return "offline"
    if choice == "api" and not config.has_api_key():
        return "offline"
    return choice


@st.cache_resource
def _llm(kind: str, effort: str, fingerprint: str) -> ClaudeLLM | ClaudeCodeLLM:
    if kind == "claude-code":
        return ClaudeCodeLLM(effort=effort)
    return ClaudeLLM(effort=effort)


def llm(effort: str | None = None) -> ClaudeLLM | ClaudeCodeLLM:
    return _llm(backend(), effort or config.effort(), _key_fingerprint())


def online() -> bool:
    return backend() != "offline"


def library() -> dict[str, tuple[Case, object]]:
    return case_library()


def participant() -> Participant:
    """Local, single-user app: one implicit participant (NEGOTRAIN_PARTICIPANT, default
    "local"). Sessions are still keyed by it so profiles and the study data work unchanged."""
    return Participant(id=config.participant_id(), consented=True)


class ActiveScenario(BaseModel):
    """The case and role everything after the upload step works on (persisted locally)."""

    case_id: str
    role_id: str


def active_scenario() -> tuple[Case, str] | None:
    state = SessionStore().load_artifact("current", "state", ActiveScenario)
    if state is None:
        return None
    lib = library()
    if state.case_id not in lib:
        return None
    case = lib[state.case_id][0]
    return (case, state.role_id) if state.role_id in [r.id for r in case.roles] else None


def set_active_scenario(case_id: str, role_id: str) -> None:
    SessionStore().save_artifact(
        "current", "state", ActiveScenario(case_id=case_id, role_id=role_id)
    )
    for key in ("session", "case", "preset", "preset_role", "feedback_session"):
        st.session_state.pop(key, None)


def clear_active_scenario() -> None:
    path = SessionStore().root / "state" / "current.json"
    path.unlink(missing_ok=True)
    st.session_state.pop("setup_case_id", None)


def counterpart_factory(session: Session, case: Case, *, use_llm: bool, effort: str):
    """A zero-argument factory. Reads Streamlit state now, because rollouts call it from
    worker threads where session state is unavailable."""
    profile = session.counterpart_profile or TIERS[3]
    role_id = session.counterpart_role_id
    if use_llm:
        client = llm(effort)
        enforce = st.session_state.get("enforce_schedule", True)
        return lambda: CounterpartAgent(case, role_id, profile, client, enforce_schedule=enforce)
    return lambda: RuleBasedCounterpart(case, role_id, profile)


def make_counterpart(session: Session, case: Case):
    return counterpart_factory(session, case, use_llm=online(), effort=config.chat_effort())()


def history(pid: str) -> list[tuple[Session, Case]]:
    lib = library()
    return [(s, lib[s.case_id][0]) for s in SessionStore().for_participant(pid) if s.case_id in lib]


def go(page: str) -> None:
    """Switch page (falls back to a rerun when pages aren't registered, as in tests)."""
    if page in PAGES:
        st.switch_page(PAGES[page])
    st.rerun()


# --------------------------------------------------------------------------- rendering


def render_sheet(case: Case, role_id: str, *, title: str) -> None:
    role = case.role(role_id)
    st.markdown(f"**{title}: {md(role.name)}**")
    if role.inferred:
        st.caption("This sheet was estimated by the parser, not taken from the case materials.")
    st.write(md(role.confidential_brief))
    style.points_block(
        [(i.name, [(o.label, role.points[i.id][o.id]) for o in i.options]) for i in case.issues],
        role.reservation_value,
    )
    for c in role.constraints:
        st.caption(f"Constraint: {md(c.description)}")


def offer_html(case: Case, offer: Offer, role_id: str, title: str = "Formal offer") -> str:
    result = score_offer(case, role_id, offer)
    terms = [(i.name, label) for i in case.issues if (label := offer.label(i))]
    badge = (
        "Custom terms · not scored" if result.points is None else f"{result.points:g} pts to you"
    )
    if not offer.is_complete(case):
        badge += " · partial"
    return style.offer_card(title, terms, badge)


def describe_offer(case: Case, offer: Offer, role_id: str) -> str:
    result = score_offer(case, role_id, offer)
    worth = (
        "custom terms, not scored"
        if result.points is None
        else f"worth **{result.points:g}** to you"
    )
    if not offer.is_complete(case):
        worth += " on the issues it covers (partial offer)"
    return f"{offer.describe(case)} — {worth}"


def render_turn(case: Case, session: Session, turn: Turn) -> None:
    is_user = turn.speaker == "user"
    name = "You" if is_user else case.role(session.counterpart_role_id).name
    with st.chat_message("user" if is_user else "assistant", avatar="🧑" if is_user else "🎭"):
        marker = '<span class="nt-me"></span>' if is_user else ""
        turn_no = f"<span class='nt-empty'>· turn {turn.index}</span>"
        style.html(f"{marker}<b>{escape(name)}</b> {turn_no}")
        if turn.text:
            st.write(md(turn.text))
        if turn.offer:
            style.html(offer_html(case, turn.offer, session.user_role_id))
        if turn.accept:
            style.banner("✅ Accepts the latest offer.", "good")
        if turn.walk_away:
            style.banner("🚪 Walks away.", "bad")


def outcome_metrics(session: Session, case: Case) -> None:
    o = outcome_summary(session, case)
    style.stats(
        [
            (
                "Result",
                {"agreed": "Deal", "impasse": "No deal"}.get(o.status, o.status),
                "",
                "",
            ),
            (
                "Your points",
                "Not scored" if o.points is None else f"{o.points:g}",
                "Custom terms" if o.surplus is None else f"{o.surplus:+g} vs walk-away",
                "gray"
                if o.surplus is None
                else "green"
                if o.surplus > 0
                else "red"
                if o.surplus < 0
                else "gray",
            ),
            ("Best listed outcome for you", f"{o.best_possible:g}", "", ""),
            (
                "Joint efficiency",
                f"{o.efficiency:.0%}" if o.efficiency is not None else "—",
                "among listed options",
                "gray",
            ),
        ]
    )


# --------------------------------------------------------------------------- sidebar


def sidebar() -> None:
    style.inject()
    style.brand()
    with st.sidebar:
        current = active_scenario()
        if current:
            case, role_id = current
            style.scenario_badge(case.title, case.role(role_id).name)
            if st.button("📂 New scenario", width="stretch"):
                clear_active_scenario()
                st.rerun()
        with st.expander("⚙️ Settings"):
            _settings()


def _settings() -> None:
    st.session_state.setdefault("backend", default_backend())
    st.radio(
        "Connect to Claude via",
        list(BACKENDS),
        format_func=BACKENDS.get,
        key="backend",
        help="Claude Code uses your logged-in Claude plan through the local `claude` CLI "
        "(personal use). The API key option bills an Anthropic API account. Offline uses "
        "a rule-based counterpart and template feedback.",
    )
    choice = st.session_state["backend"]
    if choice == "api":
        _api_key_input()
    if choice == "claude-code" and not config.claude_bin():
        st.warning("Claude Code CLI not found on this machine; running offline.")
    if online():
        where = "plan usage" if backend() == "claude-code" else "API usage"
        st.caption(f"Claude: `{config.model()}` · chat effort `{config.chat_effort()}`")
        st.caption(
            f"{where.capitalize()} this run: {_total_calls()} calls "
            f"(≈ ${_total_cost():.2f} at API prices)"
        )
    else:
        st.caption("Running offline: rule-based counterpart, template feedback.")
    st.toggle(
        "Facilitator mode",
        key="facilitator",
        help="Shows full case files, including confidential sheets. Off for participants.",
    )
    st.checkbox(
        "Enforce concession schedule in code",
        value=True,
        key="enforce_schedule",
        help="Off = prompt-only counterpart (for the T-017 comparison).",
    )


# --------------------------------------------------------------------------- pages


def _apply_key(widget_key: str) -> None:
    """on_change callback: validate the pasted key, use it for this app process, and clear
    the field (callbacks run before widgets render, so the field can be reset here)."""
    key = st.session_state.get(widget_key, "").strip()
    st.session_state[widget_key] = ""
    if not key:
        return
    problem = check_api_key(key)
    if problem:
        st.session_state["api_key_error"] = f"Key not saved: {problem}."
        return
    os.environ["ANTHROPIC_API_KEY"] = key
    st.session_state.pop("api_key_error", None)
    st.session_state["backend"] = "api"
    st.session_state["api_key_ok"] = True


def _api_key_input(where: str = "settings") -> None:
    """Enter, replace, or remove the API key. Kept in this process's environment only
    (never written to disk); a key from .env can be replaced the same way."""
    current = os.getenv("ANTHROPIC_API_KEY", "")
    widget_key = f"api_key_{where}"
    if current:
        st.caption(f"API key in use: …{current[-4:]}")
    st.text_input(
        "Replace API key" if current else "Anthropic API key",
        type="password",
        key=widget_key,
        placeholder="sk-ant-…",
        on_change=_apply_key,
        args=(widget_key,),
        help="Press Enter to apply. Checked against the API (free), kept in memory only. "
        "To make it permanent, put ANTHROPIC_API_KEY in .env.",
    )
    if error := st.session_state.get("api_key_error"):
        st.error(error)
    elif st.session_state.pop("api_key_ok", False):
        st.success("Key works and is now in use.")
    if current and st.button("Remove key", key=f"remove_key_{where}"):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        st.rerun()


def page_setup() -> None:
    style.hero(
        "Negotiation rehearsal studio",
        "Start with your case.",
        "Upload everything you were given for the negotiation: general instructions, your "
        "confidential role sheet, score tables. We'll turn it into a practice scenario with a "
        "preparation brief, AI counterparts to rehearse against, and a debrief after each "
        "round.",
    )
    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("#### 📂 Upload your case files")
        if not online():
            style.banner(
                "Reading your files needs Claude: sign in to Claude Code on this machine, or "
                "paste an Anthropic API key below. Saved cases on the right work offline.",
                "info",
            )
            _api_key_input("setup")
        elif backend() == "claude-code":
            st.caption("Using Claude Code with your Claude plan (no API key needed).")
        files = st.file_uploader(
            "Case materials",
            type=list(UPLOAD_TYPES),
            accept_multiple_files=True,
            help="PDF, Word, text, or a ZIP containing these files. "
            "Scanned PDFs without a text layer can't be read.",
        )
        infer = st.checkbox(
            "If the other side's instructions aren't included, estimate them", value=True
        )
        if st.button(
            "Build scenario", type="primary", disabled=not files or not online(), width="stretch"
        ):
            _build_scenario(participant(), files, infer)
    with right, st.container(border=True):
        st.markdown("#### 📚 Or use a saved case")
        lib = library()
        ids = sorted(lib)
        if ids:
            chosen = st.selectbox("Case", ids, format_func=lambda c: lib[c][0].title)
            if st.button("Use this case", width="stretch"):
                st.session_state["setup_case_id"] = chosen
        else:
            st.caption("No saved cases yet.")

    lib = library()
    case_id = st.session_state.get("setup_case_id")
    if case_id not in lib:
        return
    case = lib[case_id][0]
    st.write("")
    with st.container(border=True):
        st.markdown(f"### {md(case.title)}")
        st.caption(md(case.public_brief))
        style.chips([(i.name, "gray") for i in case.issues])
        role_ids = [r.id for r in case.roles]
        provided = [r.id for r in case.roles if not r.inferred]
        role_id = st.radio(
            "Which role are you playing?",
            role_ids,
            index=role_ids.index(provided[0]) if len(provided) == 1 else 0,
            format_func=lambda r: case.role(r).name,
            horizontal=True,
            key=f"setup_role_{case_id}",
        )
        if case.role(role_id).inferred:
            st.warning("This role's instructions were estimated, not uploaded. Is this your role?")
        elif case.other_role(role_id).inferred:
            st.caption(
                "The other side's instructions weren't uploaded, so the AI counterpart plays an "
                "estimated version of them. Each rehearsal varies its style to cover the range "
                "of opponents you might meet."
            )
        if st.button("Start training →", type="primary", width="stretch"):
            set_active_scenario(case.id, role_id)
            st.rerun()


TRAINING_PLAN = [
    (2, "Warm-up", "A cooperative counterpart: practice your opening and asking questions."),
    (3, "Realistic", "A guarded counterpart: practice packaging trades across issues."),
    (
        4,
        "Tough",
        "A hard-anchoring counterpart: practice holding your ground and conceding slowly.",
    ),
]


def page_prepare() -> None:
    case, role_id = active_scenario()
    p = participant()
    style.page_header(
        "Prepare",
        f"{case.title}: you are the {case.role(role_id).name}. Read your brief, then work "
        "through the training plan below.",
        "Step 1 · Get ready",
    )
    store = SessionStore()
    key = prep_key(p.id, case.id, role_id)
    prep = store.load_artifact(key, "prep", Prep)
    if prep is None:
        with st.spinner("Writing your preparation brief…"):
            prep = build_prep(case, role_id, llm() if online() else None)
            store.save_artifact(key, "prep", prep)
    _render_prep(case, prep)
    if st.button("↻ Regenerate brief"):
        with st.spinner("Writing your preparation brief…"):
            store.save_artifact(key, "prep", build_prep(case, role_id, llm() if online() else None))
        st.rerun()
    _training_plan(p, case, role_id)


def _build_scenario(p: Participant, files: list, infer: bool) -> None:
    documents, warnings = extract_documents((f.name, f.getvalue()) for f in files)
    for warning in warnings:
        st.warning(warning)
    if not documents:
        st.error("None of the files had readable text.")
        return
    with st.spinner(
        f"Reading {len(documents)} file(s) and building the scenario (about a minute)…"
    ):
        try:
            case = parse_documents(
                documents,
                llm("medium"),
                infer_missing=infer,
                source=f"Uploaded: {', '.join(documents)}.",
            )
        except Exception as e:  # noqa: BLE001 - surface parse/API errors to the user
            st.error(f"Couldn't build a scenario from these files: {md(e)}")
            return
    save_private_case(case)
    st.session_state["setup_case_id"] = case.id
    st.success(f"Built **{md(case.title)}** with {len(case.issues)} issues.")


def _render_prep(case: Case, prep: Prep) -> None:
    n, b = prep.numbers, prep.brief
    st.subheader("Your preparation brief")
    style.banner(b.overview, "info")
    style.stats(
        [
            ("Walk-away value", f"{n.walk_away:g}", "never accept less", "red"),
            ("Ambitious target", f"{n.target:g}", "aim here", "green"),
            ("Best possible", f"{n.best_possible:g}", "everything goes your way", "gray"),
        ]
    )
    st.caption(f"Your best possible deal: {md(n.best_deal)}")
    st.markdown("**What's at stake for you, by issue**")
    st.dataframe(
        [
            {
                "Priority": pr.rank,
                "Issue": pr.name,
                "You want": pr.best_option,
                "Worst for you": pr.worst_option,
                "Points at stake": pr.spread,
                "Share": f"{pr.share:.0%}",
            }
            for pr in n.priorities
        ],
        hide_index=True,
        width="stretch",
    )

    def bullets(title: str, items: list[str]) -> None:
        st.markdown(f"**{title}**")
        for item in items:
            st.markdown(f"- {md(item)}")

    left, right = st.columns(2)
    with left:
        bullets("Key facts", b.key_facts)
        bullets("Your interests", b.your_interests)
        bullets("Where to hold and where to give", b.tradeoffs)
    with right:
        bullets("The other side (hypotheses to test)", b.their_likely_interests)
        bullets("Questions to ask", b.questions_to_ask)
        bullets("Pitfalls to avoid", b.pitfalls)
    with st.container(border=True):
        st.markdown("**🎯 Opening plan**")
        st.write(md(b.opening_plan))
    with st.container(border=True):
        bullets("✅ Checklist", b.checklist)
    with st.expander("Your confidential sheet"):
        render_sheet(case, prep.role_id, title="Your role")
    if b.source == "template":
        st.caption("Template brief (offline or the model was unavailable).")


def _training_plan(p: Participant, case: Case, role_id: str) -> None:
    st.subheader("Training plan for this scenario")
    st.caption(
        "Rehearse this exact case against counterparts of increasing difficulty, then check "
        "the Feedback page after each one. The last step adapts to your profile."
    )
    hist = history(p.id)
    done: dict[int, int] = {}
    for s, _ in hist:
        if (
            s.kind == "rehearsal"
            and s.case_id == case.id
            and s.user_role_id == role_id
            and s.status in ("agreed", "impasse")
            and s.counterpart_profile
        ):
            done[s.counterpart_profile.tier] = done.get(s.counterpart_profile.tier, 0) + 1
    spec = next_scenario(build_profile(p.id, hist), hist, [case.id])
    steps = [
        ScenarioSpec(tier=t, case_id=case.id, rationale=f"{title}: {why}")
        for t, title, why in TRAINING_PLAN
    ]
    steps.append(spec.model_copy(update={"rationale": f"Recommended for you: {spec.rationale}"}))
    for n, step in enumerate(steps):
        with st.container(border=True):
            left, right = st.columns([5, 1])
            title, _, why = step.rationale.partition(": ")
            with left:
                st.markdown(f"**{n + 1}. {title}**")
                chips = [(f"Tier {step.tier} · {TIERS[step.tier].name}", "")]
                if done.get(step.tier):
                    chips.append((f"✓ done {done[step.tier]}×", "green"))
                style.chips(chips)
                st.caption(md(why))
            if right.button("Start", key=f"plan_{n}", width="stretch", type="primary"):
                start_rehearsal(p, case, role_id, step, counterpart_opens=False)
                go("rehearse")


def _require_participant() -> Participant:
    return participant()


def _setup_rehearsal(p: Participant) -> None:
    case, role_id = active_scenario()
    st.subheader("Set up a rehearsal")
    st.caption("Tip: the training plan on the Prepare page starts rehearsals in one click.")
    hist = history(p.id)
    profile = build_profile(p.id, hist)
    spec = next_scenario(profile, hist, [case.id])
    preset: ScenarioSpec | None = st.session_state.get("preset")
    mode = st.radio(
        "Counterpart",
        ["Recommended for me", "I'll choose the difficulty"],
        index=0,
        horizontal=True,
    )
    if mode == "Recommended for me":
        chosen = preset or spec
        style.banner(f"Tier {chosen.tier} counterpart. {chosen.rationale}", "info")
    else:
        tier = st.select_slider(
            "Difficulty tier",
            options=list(TIERS),
            value=3,
            format_func=lambda t: f"{t} · {TIERS[t].name}",
        )
        chosen = ScenarioSpec(tier=tier, rationale=f"Chosen by you: tier {tier}.")
    opener = st.radio("Who opens?", ["Me", "The counterpart"], horizontal=True)
    if st.button("Start rehearsal", type="primary"):
        start_rehearsal(p, case, role_id, chosen, counterpart_opens=opener == "The counterpart")
        st.rerun()


def start_rehearsal(
    p: Participant, case: Case, role_id: str, spec: ScenarioSpec, *, counterpart_opens: bool
) -> Session:
    """Create and save a session against a freshly sampled counterpart for ``spec``."""
    seed = random.randrange(1_000_000)
    session = Session(
        participant_id=p.id,
        case_id=case.id,
        user_role_id=role_id,
        counterpart_role_id=case.other_role(role_id).id,
        counterpart_profile=counterpart_for(spec, random.Random(seed)),
        seed=seed,
        notes=spec.rationale,
    )
    st.session_state["session"] = session
    st.session_state["case"] = case
    st.session_state.pop("preset", None)
    st.session_state.pop("preset_role", None)
    SessionStore().save(session)
    if counterpart_opens or spec.focus == "error:3":
        _counterpart_reply(session, case)
    return session


def _counterpart_reply(session: Session, case: Case) -> None:
    with st.spinner(f"{case.role(session.counterpart_role_id).name} is responding…"):
        try:
            reply = make_counterpart(session, case).respond(session)
            session.add_turn(reply, case)
        except LLMRefusal:
            st.error("The model declined to respond to that. Rephrase your message and retry.")
        except Exception as e:  # noqa: BLE001 - surface API errors without losing the session
            st.error(f"Counterpart error: {md(e)}. Use **Retry counterpart** below.")
    SessionStore().save(session)


def _user_move(session: Session, case: Case, turn: Turn) -> None:
    try:
        session.add_turn(turn, case)
    except ValueError as e:
        st.error(str(e))
        return
    SessionStore().save(session)
    if session.status == "active":
        _counterpart_reply(session, case)
    st.rerun()


def _move_controls(session: Session, case: Case) -> None:
    last = session.turns[-1] if session.turns else None
    if last is not None and last.speaker == "user":
        st.warning("The counterpart hasn't replied yet.")
        if st.button("Retry counterpart"):
            _counterpart_reply(session, case)
            st.rerun()
        return

    with st.form("move", clear_on_submit=True):
        text = st.text_area("Your message", placeholder="Say what you'd say across the table…")
        attach = st.checkbox("Attach a formal offer")
        st.caption(
            "Choose a suggestion or type your own solution and press Enter. "
            "Leave undecided issues blank."
        )
        if not online():
            st.caption(
                "The offline counterpart only evaluates listed options. "
                "Use the AI counterpart to negotiate custom solutions."
            )
        cols = st.columns(min(2, len(case.issues)))
        picks = {}
        for n, issue in enumerate(case.issues):
            picks[issue.id] = cols[n % len(cols)].selectbox(
                issue.name,
                [o.label for o in issue.options],
                index=None,
                placeholder="Choose or type a solution",
                accept_new_options=True,
                help="Suggestions are optional. Type any proposal for this issue and press Enter.",
                key=f"o_{issue.id}",
            )
        if st.form_submit_button("Send", type="primary"):
            offer = Offer.from_labels(case, picks) if attach else None
            if offer is not None and not (offer.terms or offer.custom_terms):
                offer = None
            if not text.strip() and offer is None:
                st.error("Write a message or attach an offer.")
            else:
                _user_move(
                    session,
                    case,
                    Turn(index=len(session.turns), speaker="user", text=text.strip(), offer=offer),
                )

    theirs = session.latest_offer_from("counterpart")
    c1, c2 = st.columns(2)
    with c1:
        can_accept = theirs is not None and theirs.is_complete(case)
        if st.button(
            "✅ Accept their latest offer",
            disabled=not can_accept,
            help=None if can_accept else "They haven't made a complete offer yet.",
            width="stretch",
        ):
            _user_move(
                session,
                case,
                Turn(index=len(session.turns), speaker="user", text="I accept.", accept=True),
            )
    with c2:
        sure = st.checkbox("I'm sure I want to walk away")
        if st.button("🚪 Walk away", disabled=not sure, width="stretch"):
            _user_move(
                session,
                case,
                Turn(
                    index=len(session.turns),
                    speaker="user",
                    text="I'm going to walk away.",
                    walk_away=True,
                ),
            )


def page_rehearse() -> None:
    style.page_header(
        "Rehearse",
        "Negotiate as you would for real. Feedback comes afterwards.",
        "Step 2 · Practice",
    )
    p = _require_participant()
    session: Session | None = st.session_state.get("session")
    case: Case | None = st.session_state.get("case")
    current, _ = active_scenario()
    if session is None or case is None or session.case_id != current.id:
        _setup_rehearsal(p)
        return

    them = case.role(session.counterpart_role_id)
    st.markdown(f"### {md(case.title)}")
    tier = session.counterpart_profile.tier if session.counterpart_profile else None
    status = {
        "active": ("● In progress", "amber"),
        "agreed": ("✓ Deal", "green"),
        "impasse": ("✕ No deal", "red"),
        "abandoned": ("Abandoned", "gray"),
    }
    style.chips(
        [
            (f"You: {case.role(session.user_role_id).name}", ""),
            (f"Counterpart: {them.name}", "gray"),
            (f"Tier {tier} · {TIERS[tier].name}" if tier else "Tier ?", "gray"),
            (f"{len(session.turns)} turn{'' if len(session.turns) == 1 else 's'}", "gray"),
            status[session.status],
        ]
    )

    st.caption(f"Deadline: {session.max_user_turns - session.user_turns} user moves remaining.")
    chat, side = st.columns([3, 2], gap="large")
    with side:
        mine, theirs = session.latest_offer_from("user"), session.latest_offer_from("counterpart")
        st.markdown("**On the table**")
        empty = "<div class='nt-offer'><span class='nt-empty'>{} none yet</span></div>"
        style.html(
            offer_html(case, theirs, session.user_role_id, "Their latest offer")
            if theirs
            else empty.format("Their latest offer:")
        )
        style.html(
            offer_html(case, mine, session.user_role_id, "Your latest offer")
            if mine
            else empty.format("Your latest offer:")
        )
        st.write("")
        with st.expander("Your confidential sheet", expanded=True):
            render_sheet(case, session.user_role_id, title="Your role")
        prep = SessionStore().load_artifact(
            prep_key(session.participant_id, case.id, session.user_role_id), "prep", Prep
        )
        if prep is not None:
            with st.expander("Your prep checklist"):
                for item in prep.brief.checklist:
                    st.markdown(f"- {md(item)}")
        with st.expander("Public information", expanded=False):
            st.write(md(case.public_brief))
    with chat:
        if not session.turns:
            style.banner(
                "You open. Introduce yourself, ask questions, or put an offer on the table.",
                "info",
            )
        for turn in session.turns:
            render_turn(case, session, turn)
        if session.status == "active":
            _move_controls(session, case)
            with st.expander("End without an outcome"):
                if st.button("Abandon this rehearsal"):
                    session.status = "abandoned"
                    SessionStore().save(session)
                    st.session_state.pop("session", None)
                    st.rerun()
        else:
            _finished(session, case)


def _finished(session: Session, case: Case) -> None:
    st.divider()
    if session.status == "agreed" and session.agreement:
        style.banner("🎉 Deal reached.", "good")
        style.html(offer_html(case, session.agreement, session.user_role_id, "Final agreement"))
        st.write("")
    else:
        style.banner(
            "No deal this time. The debrief will show what might have changed that.", "bad"
        )
    outcome_metrics(session, case)
    with st.expander("Debrief: the counterpart's confidential sheet"):
        render_sheet(case, session.counterpart_role_id, title="Their role")
    c1, c2 = st.columns(2)
    if c1.button("Get my feedback →", type="primary", width="stretch"):
        st.session_state["feedback_session"] = session.id
        go("feedback")
    if c2.button("New rehearsal", width="stretch"):
        st.session_state.pop("session", None)
        st.rerun()


def page_feedback() -> None:
    style.page_header(
        "Feedback",
        "Your debrief: the outcome, a coaching report, and the moments that mattered.",
        "Step 3 · Debrief",
    )
    p = _require_participant()
    store = SessionStore()
    lib = library()
    done = [
        s
        for s in reversed(store.for_participant(p.id))
        if s.kind == "rehearsal" and s.status in ("agreed", "impasse") and s.case_id in lib
    ]
    if not done:
        st.info("Finish a rehearsal first; feedback appears here afterwards.")
        return
    wanted = st.session_state.get("feedback_session")
    ids = [s.id for s in done]
    by_id = {s.id: s for s in done}
    sid = st.selectbox(
        "Rehearsal",
        ids,
        index=ids.index(wanted) if wanted in ids else 0,
        format_func=lambda i: (
            f"{by_id[i].created_at:%b %d %H:%M} · {lib[by_id[i].case_id][0].title}"
            f" · {by_id[i].status}"
        ),
    )
    session = by_id[sid]
    st.session_state["assistant_feedback_session"] = sid
    case = lib[session.case_id][0]
    outcome_metrics(session, case)

    debrief = store.load_artifact(session.id, "feedback", Debrief)
    if session.has_custom_terms:
        use_llm, cap, k, n, horizon = False, 3, 2, 1, 4
        st.caption(
            "Custom proposals receive qualitative coaching. Point-based simulations "
            "are unavailable because these terms have no defined point values."
        )
    else:
        with st.expander("Feedback settings", expanded=debrief is None):
            on_plan = backend() == "claude-code"
            sim_choice = st.radio(
                "Simulate alternatives against",
                [
                    "Same AI counterpart (slower, uses " + ("your plan)" if on_plan else "API)"),
                    "Fast rule-based simulator (free)",
                ],
                # On a plan, ~30 rollout calls eat into rate limits: opt in, don't default.
                index=0 if online() and not on_plan else 1,
                disabled=not online(),
            )
            use_llm = online() and sim_choice.startswith("Same")
            c = st.columns(4)
            cap = c[0].number_input("Moments to analyze", 1, 5, 3)
            k = c[1].number_input("Alternatives each", 1, 4, 2)
            n = c[2].number_input("Rollouts each", 1, 6, 2 if use_llm else 1)
            horizon = c[3].number_input("AI turns per rollout", 2, 10, 4)
            if use_llm:
                calls = estimate_calls(int(cap), int(k), int(n), int(horizon)) + 1
                if on_plan:
                    st.caption(
                        f"Up to ~{calls} Claude Code calls against your plan's limits, "
                        "typically 2–5 min."
                    )
                else:
                    st.caption(
                        f"Up to ~{calls} API calls (≈ ${calls * EST_COST_PER_CALL:.2f}), "
                        "typically 1–3 min."
                    )
    if st.button("Generate feedback" if debrief is None else "Regenerate feedback", type="primary"):
        with st.spinner(
            "Writing your debrief…"
            if session.has_custom_terms
            else "Simulating alternatives and writing your debrief…"
        ):
            calls_before = _total_calls()
            cost_before = _total_cost()
            counterfactuals = analyze_session(
                session,
                case,
                counterpart_factory(session, case, use_llm=use_llm, effort="low"),
                opponent="llm" if use_llm else "rule-based",
                cap=int(cap),
                k=int(k),
                n=int(n),
                horizon=int(horizon),
                max_workers=3 if backend() == "claude-code" else 8,
            )
            report = build_report(session, case, counterfactuals, llm() if online() else None)
            debrief = Debrief(
                counterfactuals=counterfactuals,
                report=report,
                llm_calls=_total_calls() - calls_before,
                est_cost=_total_cost() - cost_before,
            )
            store.save_artifact(session.id, "feedback", debrief)

    if debrief is None:
        return
    tabs = st.tabs(["Coaching", "Moments that mattered", "Transcript", "Both sheets", "Numbers"])
    with tabs[0]:
        _render_report(debrief.report)
        st.divider()
        rating = st.radio(
            "How useful was this feedback? (1 = not at all, 5 = very)",
            [1, 2, 3, 4, 5],
            index=(debrief.usefulness - 1) if debrief.usefulness else None,
            horizontal=True,
        )
        if rating and rating != debrief.usefulness:
            debrief.usefulness = rating
            store.save_artifact(session.id, "feedback", debrief)
            st.toast("Thanks!")
    with tabs[1]:
        _render_counterfactuals(debrief.counterfactuals, session, case)
    with tabs[2]:
        for turn in session.turns:
            render_turn(case, session, turn)
    with tabs[3]:
        a, b = st.columns(2)
        with a:
            render_sheet(case, session.user_role_id, title="Your role")
        with b:
            render_sheet(case, session.counterpart_role_id, title="Their role")
        o = outcome_summary(session, case)
        st.caption(
            f"Best joint deal among listed options: {md(o.max_joint_deal)} "
            f"({o.max_joint:g} joint points)."
        )
    with tabs[4]:
        f = extract_features(session, case)
        st.dataframe([{"feature": k, "value": v} for k, v in f.items()], hide_index=True)
        if session.counterpart_profile:
            st.caption(
                "Counterpart dials: "
                + ", ".join(f"{d}={getattr(session.counterpart_profile, d):.2f}" for d in DIALS)
            )
        st.caption(
            f"Feedback cost: {debrief.llm_calls} API calls (~${debrief.est_cost:.2f}); "
            f"simulation took {debrief.counterfactuals.seconds:.0f}s"
            if debrief.counterfactuals
            else ""
        )


def _total_calls() -> int:
    if not online():
        return 0
    kind, fp = backend(), _key_fingerprint()
    return sum(_llm(kind, e, fp).usage.calls for e in ("low", "medium", "high"))


def _total_cost() -> float:
    if not online():
        return 0.0
    kind, fp = backend(), _key_fingerprint()
    return sum(_llm(kind, e, fp).usage.cost() for e in ("low", "medium", "high"))


def _render_report(report: CoachingReport) -> None:
    style.banner(report.headline, "info")
    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown("**💪 What went well**")
        for s in report.strengths:
            st.markdown(f"- {md(s)}")
    with b, st.container(border=True):
        st.markdown("**🎯 What to work on**")
        for s in report.improvements:
            st.markdown(f"- {md(s)}")
    if report.moments:
        st.markdown("**Moments that mattered**")
        for m in report.moments:
            with st.container(border=True):
                st.markdown(f"**Turn {m.turn_index}: {md(m.title)}**")
                st.write(md(m.what_happened))
                st.markdown(f"*Try:* {md(m.what_to_try)}")
                st.caption(md(m.evidence))
    style.banner(f"Next focus: {report.next_focus}", "good")
    if report.source == "template":
        st.caption("Template feedback (offline or the coaching model was unavailable).")


def _render_counterfactuals(
    report: CounterfactualReport | None, session: Session, case: Case
) -> None:
    if report is not None and report.skipped_reason:
        st.info(report.skipped_reason)
        return
    if report is None or not report.estimates:
        st.info("No offers, acceptances, or walk-aways to analyze in this session.")
        return
    st.caption(
        f"Each option was played forward {report.n_rollouts}× against "
        f"{'the same AI counterpart' if report.opponent == 'llm' else 'a rule-based simulator'}"
        " by a simulated version of you. Points are your expected outcome; treat small "
        "differences as noise."
    )
    for e in report.estimates:
        turn = session.turns[e.turn_index]
        with st.container(border=True):
            delta = e.delta
            head = f"**Turn {e.turn_index}: {md(e.description)}**"
            if delta is not None:
                head += f" · best alternative {delta:+.0f} pts"
            st.markdown(head)
            if turn.text:
                st.caption(f"You said: “{md(turn.text)}”")
            rows = []
            for v in e.values:
                a = v.action
                what = (
                    a.offer.describe(case)
                    if a.offer
                    else "accept"
                    if a.accept
                    else "walk away"
                    if a.walk_away
                    else f"“{a.text}”"
                )
                rows.append(
                    {
                        "Option": a.label,
                        "Move": what,
                        "Expected points": round(v.mean) if v.mean is not None else None,
                        "Deals": f"{v.agreements}/{len(v.outcomes)}",
                    }
                )
            st.dataframe(rows, hide_index=True, width="stretch")
            errors = sum(v.errors for v in e.values)
            if errors:
                st.caption(f"{errors} rollout(s) failed (API errors) and were skipped.")


def page_profile() -> None:
    style.page_header("My profile", "Strengths, weaknesses, and what to practice next.", "Progress")
    p = _require_participant()
    hist = history(p.id)
    prof = build_profile(p.id, hist)
    st.caption(
        f"Based on {prof.n_sessions} finished sessions. Estimates use opportunities "
        "and occurrences, with older evidence discounted once per session."
    )
    rows = []
    for key, posterior in prof.belief.components.items():
        lo, hi = posterior.interval()
        rows.append(
            {
                "Component": prof.labels[key],
                "Probability": round(posterior.mean, 3),
                "95% credible interval": f"{lo:.2f}–{hi:.2f}",
                "Opportunities": posterior.opportunities,
                "Meaning": "error rate" if key.startswith("error:") else "success rate",
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    if prof.untagged_user_turns:
        st.caption(
            f"{prof.untagged_user_turns} user turns lack fact/rapport annotations; "
            "they are excluded from those estimates."
        )

    lib = library()
    current, _ = active_scenario()
    spec = next_scenario(prof, hist, [current.id])
    st.subheader("Recommended next rehearsal")
    case_title = lib[spec.case_id][0].title if spec.case_id in lib else "any case"
    st.info(f"**{md(case_title)}, tier {spec.tier}.** {md(spec.rationale)}")
    if st.button("Start this rehearsal →", type="primary"):
        st.session_state["preset"] = spec
        st.session_state.pop("session", None)
        go("rehearse")

    if hist:
        st.subheader("History")
        rows = []
        for s, c in hist:
            f = extract_features(s, c)
            rows.append(
                {
                    "When": f"{s.created_at:%b %d %H:%M}",
                    "Kind": s.kind,
                    "Case": c.title,
                    "Tier": s.counterpart_profile.tier if s.counterpart_profile else None,
                    "Result": s.status,
                    "Points": f["points"],
                    "Surplus share": None
                    if f["surplus_share"] is None
                    else round(f["surplus_share"], 2),
                }
            )
        st.dataframe(rows, hide_index=True, width="stretch")


def page_real() -> None:
    style.page_header(
        "Real negotiation",
        "After the real negotiation (for example, the class simulation), log the outcome. "
        "We compare it with your rehearsals of the same case to see what rehearsal got "
        "right and wrong.",
        "Progress",
    )
    p = _require_participant()
    case, role_id = active_scenario()
    style.chips([(case.title, ""), (f"You: {case.role(role_id).name}", "gray")])
    with st.form("real"):
        status = st.radio(
            "Outcome",
            ["agreed", "impasse"],
            horizontal=True,
            format_func=lambda s: "Deal" if s == "agreed" else "No deal",
        )
        st.markdown("Agreed terms (if there was a deal):")
        st.caption("Choose a suggestion or type the terms you agreed to and press Enter.")
        picks = {}
        cols = st.columns(min(3, len(case.issues)))
        for n, issue in enumerate(case.issues):
            picks[issue.id] = cols[n % len(cols)].selectbox(
                issue.name,
                [o.label for o in issue.options],
                key=f"real_{issue.id}",
                accept_new_options=True,
            )
        st.markdown("How did the other side behave? (0 = not at all, 1 = very)")
        observed = {
            d: st.slider(q, 0.0, 1.0, 0.5, 0.1, key=f"real_{d}") for d, q in DIAL_QUESTIONS.items()
        }
        notes = st.text_area("Notes or transcript (optional; no names, please)")
        if st.form_submit_button("Save real outcome", type="primary"):
            agreement = None
            if status == "agreed":
                agreement = Offer.from_labels(case, picks)
                if not agreement.is_complete(case):
                    st.error("Enter the agreed terms for every issue before saving a deal.")
                    return
            SessionStore().save(
                Session(
                    participant_id=p.id,
                    case_id=case.id,
                    user_role_id=role_id,
                    counterpart_role_id=case.other_role(role_id).id,
                    kind="real",
                    status=status,
                    agreement=agreement,
                    notes=notes,
                    observed_counterpart=observed,
                )
            )
            st.success("Saved.")

    _sim2real(p, case, role_id)


def _sim2real(p: Participant, case: Case, role_id: str) -> None:
    sessions = [
        s
        for s in SessionStore().for_participant(p.id)
        if s.case_id == case.id and s.user_role_id == role_id and s.status in ("agreed", "impasse")
    ]
    rehearsals = [s for s in sessions if s.kind == "rehearsal"]
    reals = [s for s in sessions if s.kind == "real"]
    if not reals:
        return
    st.subheader("Rehearsal vs real")
    real = reals[-1]
    real_pts = outcome_summary(real, case).points
    rows = [
        {
            "Session": f"Rehearsal {s.created_at:%b %d %H:%M}",
            "Tier": s.counterpart_profile.tier if s.counterpart_profile else None,
            "Result": s.status,
            "Your points": outcome_summary(s, case).points,
        }
        for s in rehearsals
    ]
    rows.append({"Session": "Real", "Tier": None, "Result": real.status, "Your points": real_pts})
    st.dataframe(rows, hide_index=True, width="stretch")
    if not rehearsals:
        st.caption("No rehearsals of this case and role yet to compare against.")
        return
    scored = [r["Your points"] for r in rows[:-1] if r["Your points"] is not None]
    if real_pts is not None and scored:
        mean_pts = sum(scored) / len(scored)
        share = surplus_share(case, role_id, real_pts) - surplus_share(case, role_id, mean_pts)
        st.metric(
            "Real outcome vs scored rehearsal average",
            f"{real_pts:g} pts",
            f"{real_pts - mean_pts:+.0f} pts ({share:+.0%} of your range)",
        )
    if real_pts is None or len(scored) != len(rehearsals):
        st.caption(
            "Agreements with custom terms have no point score "
            "and are excluded from numeric comparisons."
        )
    profiles: list[CounterpartProfile] = [
        s.counterpart_profile for s in rehearsals if s.counterpart_profile
    ]
    if profiles and real.observed_counterpart:
        st.markdown("**Counterpart behavior: rehearsal vs what you observed**")
        st.dataframe(
            [
                {
                    "Behavior": DIAL_QUESTIONS[d],
                    "Rehearsal counterpart": round(
                        sum(getattr(pr, d) for pr in profiles) / len(profiles), 2
                    ),
                    "Real counterpart (your rating)": real.observed_counterpart.get(d),
                }
                for d in DIALS
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Large gaps show where rehearsal didn't match reality (RQ2): for example, a real "
            "counterpart that conceded far less than the rehearsal one."
        )


def page_cases() -> None:
    style.page_header(
        "Case library",
        "All scenarios available for rehearsal. Imported cases stay private to this machine.",
        "Facilitator",
    )
    lib = library()
    facilitator = st.session_state.get("facilitator", False)
    for cid, (case, path) in sorted(lib.items()):
        private = "private" in str(path)
        with st.expander(f"{case.title} ({cid}){' · private' if private else ''}"):
            st.write(md(case.public_brief))
            for issue in case.issues:
                st.markdown(md(f"- **{issue.name}**: " + ", ".join(o.label for o in issue.options)))
            st.caption(
                "Roles: "
                + ", ".join(r.name + (" (inferred)" if r.inferred else "") for r in case.roles)
            )
            if case.source:
                st.caption(md(case.source))
            if facilitator:
                st.json(case.model_dump(), expanded=False)

    st.subheader("Add a case")
    st.caption(
        "Imported cases are saved to data/cases/private/ (never committed). Review the point "
        "tables before using a case in the study."
    )
    paste, upload = st.tabs(["Paste case text (uses Claude)", "Upload JSON"])
    with paste:
        if not online():
            st.info("Parsing needs Claude: choose Claude Code or an API key in Settings.")
        with st.form("parse"):
            public = st.text_area("Public / general information", height=150)
            c1, c2 = st.columns(2)
            name1 = c1.text_input("Role 1 name", "Buyer")
            sheet1 = c1.text_area("Role 1 confidential sheet", height=200)
            name2 = c2.text_input("Role 2 name", "Seller")
            sheet2 = c2.text_area(
                "Role 2 confidential sheet (leave empty if you don't have it)", height=200
            )
            infer = st.checkbox("Estimate the missing sheet if only one is given", value=True)
            go = st.form_submit_button("Parse case", type="primary", disabled=not online())
        if go:
            roles = {name1: sheet1} | ({name2: sheet2} if sheet2.strip() else {})
            if not public.strip() or not sheet1.strip():
                st.error("Need the public information and at least one confidential sheet.")
            else:
                with st.spinner("Parsing (this can take a minute)…"):
                    try:
                        parsed = parse_case(
                            public,
                            roles,
                            llm("medium"),
                            infer_missing=infer,
                            source="Imported via the app.",
                        )
                        st.session_state["parsed_case"] = parsed
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Parsing failed: {md(e)}")
        parsed: Case | None = st.session_state.get("parsed_case")
        if parsed is not None:
            st.success(f"Parsed **{md(parsed.title)}** with {len(parsed.issues)} issues.")
            for issue in parsed.issues:
                st.markdown(md(f"- **{issue.name}**: " + ", ".join(o.label for o in issue.options)))
            st.caption(md(parsed.source))
            show = st.checkbox(
                "Show full JSON for review (reveals both confidential sheets, including any "
                "estimated one: spoils the rehearsal for that role)"
            )
            text = parsed.model_dump_json(indent=2)
            edited = st.text_area("Case JSON", text, height=400) if show else text
            if st.button("Save case"):
                try:
                    case = Case.model_validate_json(edited)
                    path = save_private_case(case)
                    st.session_state.pop("parsed_case", None)
                    st.success(f"Saved to {path}. It's now available in Rehearse.")
                except ValueError as e:
                    st.error(f"Invalid case: {e}")
    with upload:
        file = st.file_uploader("Case JSON", type="json")
        if file is not None and st.button("Validate and save"):
            try:
                case = Case.model_validate_json(file.getvalue())
                st.success(f"Saved to {save_private_case(case)}.")
            except ValueError as e:
                st.error(f"Invalid case: {e}")
