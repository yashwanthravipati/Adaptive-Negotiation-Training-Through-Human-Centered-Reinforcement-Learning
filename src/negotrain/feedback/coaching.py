"""Post-session coaching report (T-023).

All numbers come from code (scoring, features, counterfactual rollouts); the LLM only turns
them into teaching. Without an LLM, or if the call fails, a template report is built from
the same numbers, so the debrief always renders. Shown after the session only (decision
0002): it explains what mattered, it does not steer a live negotiation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from negotrain.cases.offers import feasible_best_points
from negotrain.cases.scoring import efficiency, joint_points, max_joint_offer, score_offer
from negotrain.feedback.rollouts import CounterfactualReport
from negotrain.llm import LLM
from negotrain.profiling.features import FLAG_DESCRIPTIONS, Features, extract_features, flags
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Case, Session


class Moment(BaseModel):
    turn_index: int = Field(description="The transcript turn number this moment refers to")
    title: str = Field(description="A few words naming the moment")
    what_happened: str
    what_to_try: str = Field(description="A principle to practice next time, not a script")
    evidence: str = Field(description="The numbers that support this, quoted from the input")


class CoachingReport(BaseModel):
    headline: str = Field(description="One sentence on how the negotiation went")
    strengths: list[str] = Field(description="Two or three specific things done well")
    improvements: list[str] = Field(description="Two or three specific things to work on")
    moments: list[Moment] = Field(description="Two or three moments that mattered most")
    next_focus: str = Field(description="The one skill to focus on in the next rehearsal")
    source: str = "template"  # "llm" or "template"


class OutcomeSummary(BaseModel):
    status: str
    points: float | None
    reservation_value: float
    best_possible: float
    surplus: float | None
    efficiency: float | None
    their_points: float | None
    max_joint: float
    max_joint_deal: str


def outcome_summary(session: Session, case: Case) -> OutcomeSummary:
    me = case.role(session.user_role_id)
    best_joint = max_joint_offer(case)
    pts, eff, theirs = me.reservation_value, None, None
    if session.status == "agreed" and session.agreement is not None:
        pts = score_offer(case, me.id, session.agreement).points
        eff = efficiency(case, session.agreement)
        theirs = score_offer(case, session.counterpart_role_id, session.agreement).points
    return OutcomeSummary(
        status=session.status,
        points=pts,
        reservation_value=me.reservation_value,
        best_possible=feasible_best_points(case, me.id),
        surplus=None if pts is None else pts - me.reservation_value,
        efficiency=eff,
        their_points=theirs,
        max_joint=joint_points(case, best_joint),
        max_joint_deal=best_joint.describe(case),
    )


def transcript(session: Session, case: Case) -> str:
    """Transcript annotated with each offer's points for both sides (debrief view)."""
    me, them = session.user_role_id, session.counterpart_role_id
    lines = []
    for t in session.turns:
        who = "USER" if t.speaker == "user" else "COUNTERPART"
        line = f"[{t.index}] {who}: {t.text}"
        if t.offer:
            u = score_offer(case, me, t.offer).points
            c = score_offer(case, them, t.offer).points
            scores = (
                "unscored: custom terms have no defined point values"
                if u is None or c is None
                else f"user {u:g} / counterpart {c:g} pts"
            )
            line += f"\n    offer: {t.offer.describe(case)} ({scores})"
        if t.accept:
            line += "\n    [accepts]"
        if t.walk_away:
            line += "\n    [walks away]"
        lines.append(line)
    return "\n".join(lines)


def _counterfactual_lines(report: CounterfactualReport | None) -> str:
    if report is not None and report.skipped_reason:
        return report.skipped_reason
    if report is None or not report.estimates:
        return "(no counterfactual analysis was run)"
    lines = []
    for e in report.estimates:
        lines.append(f"Turn {e.turn_index} ({e.description}):")
        for v in [e.actual, e.best_alternative]:
            if v is None:
                continue
            mean = "n/a" if v.mean is None else f"{v.mean:.3f}"
            offer = f" offer: {v.action.offer.terms}" if v.action.offer else ""
            lines.append(
                f"  - {v.action.label}: mean R={mean} over {len(v.outcomes)} fresh rollouts, "
                f"{v.agreements} agreements{offer}; hindsight={v.action.hindsight}"
            )
        lines.append(f"  Fresh-batch delta R={e.delta}; 95% paired bootstrap CI={e.delta_interval}")
    return "\n".join(lines)


SYSTEM = """You are an experienced negotiation coach writing a debrief for a student who \
just finished a practice negotiation against an AI counterpart. The negotiation is over; \
both confidential sheets are now revealed.

Teach, don't grade. Be specific: refer to transcript turn numbers and quote the numbers \
you are given. Use only the numbers in the input; never compute or invent new ones. \
"Moments" should be the two or three decisions that mattered most, preferring turns where \
the counterfactual simulation shows a large gap between what the student did and an \
alternative. Treat simulation estimates as rough evidence from a few rollouts, not as \
certainty. "What to try" should be a transferable principle (for example, "make each \
concession smaller than the last and ask for something in return"), not a script for this \
exact case. Custom terms are legitimate proposals but have no defined points. For these, \
discuss creativity, interests, feasibility, and tradeoffs qualitatively; never invent \
points, claim that a numeric walk-away was met, or treat missing metrics as zero. \
The best listed deal is only a benchmark within the predefined options, not a bound on \
custom solutions. Write in second person, plainly, without hype."""


def _prompt(
    session: Session,
    case: Case,
    outcome: OutcomeSummary,
    features: Features,
    flag_keys: list[str],
    report: CounterfactualReport | None,
) -> str:
    me = case.role(session.user_role_id)
    them = case.role(session.counterpart_role_id)

    def sheet(role) -> str:
        pts = "; ".join(
            f"{case.issue(i).name}: " + ", ".join(f"{o}={p:g}" for o, p in t.items())
            for i, t in role.points.items()
        )
        return (
            f"{role.name}: {role.confidential_brief}\nPoints: {pts}\n"
            f"Walk-away: {role.reservation_value:g}"
        )

    feats = ", ".join(f"{k}={v:.2f}" for k, v in features.items() if v is not None)
    flag_text = "\n".join(f"- {FLAG_DESCRIPTIONS[k]}" for k in flag_keys) or "- none"
    dials = session.counterpart_profile.model_dump() if session.counterpart_profile else "n/a"
    return f"""# Case: {case.title}
{case.public_brief}

# Student's role
{sheet(me)}

# Counterpart's role (revealed after the session)
{sheet(them)}
Counterpart behavior profile: {dials}

# Transcript
{transcript(session, case)}

# Outcome (computed by code)
{outcome.model_dump_json(indent=1)}

# Behavioral features (computed by code)
{feats}

# Error patterns detected
{flag_text}

# Counterfactual simulation (alternatives played forward against the same counterpart)
{_counterfactual_lines(report)}

# Focus
{session.counterpart_profile.focus if session.counterpart_profile else None}
Lead with observed moments tied to this focus. Do not manufacture an example if none arose.
Counterfactual values are normalized surplus R, not raw points. Hindsight alternatives use
both sheets and must be labeled hindsight. Intervals with four rollouts are exploratory.

# Opportunity/occurrence counts
{observe(session, case).model_dump_json()}

Write the debrief."""


def template_report(
    session: Session,
    case: Case,
    outcome: OutcomeSummary,
    flag_keys: list[str],
    report: CounterfactualReport | None,
) -> CoachingReport:
    if session.status == "agreed" and outcome.points is None:
        headline = (
            "You reached a deal with custom terms. This agreement has no defined point score."
        )
    elif session.status == "agreed":
        headline = (
            f"You reached a deal worth {outcome.points:g} points "
            f"({outcome.surplus:+g} vs walking away)"
            + (
                f", at {outcome.efficiency:.0%} of the best joint outcome."
                if outcome.efficiency
                else "."
            )
        )
    elif session.status == "impasse":
        headline = f"No deal: you ended at your walk-away value of {outcome.points:g} points."
    else:
        headline = "The negotiation did not finish."
    strengths = []
    if (
        not session.has_custom_terms
        and "weak_anchor" not in flag_keys
        and session.latest_offer_from("user")
    ):
        strengths.append("You opened ambitiously, which set a favorable range.")
    if (
        not session.has_custom_terms
        and "early_concession" not in flag_keys
        and "big_concessions" not in flag_keys
    ):
        strengths.append("You conceded with discipline rather than in big unreciprocated jumps.")
    if "no_questions" not in flag_keys and any(
        "?" in t.text for t in session.turns if t.speaker == "user"
    ):
        strengths.append("You asked questions to learn about the other side.")
    if session.status == "agreed" and outcome.surplus is not None and outcome.surplus > 0:
        strengths.append("You closed a deal better than your walk-away value.")
    improvements = [FLAG_DESCRIPTIONS[k] + "." for k in flag_keys] or [
        "Keep practicing against tougher counterparts to test these habits under pressure."
    ]
    if session.has_custom_terms:
        improvements.insert(
            0,
            "Review whether your custom terms are specific, feasible, "
            "and address both sides' interests.",
        )
    moments = []
    if report:
        ranked = sorted(
            (e for e in report.estimates if e.delta is not None),
            key=lambda e: (
                session.counterpart_profile is None
                or session.counterpart_profile.focus not in e.errors,
                -(e.delta or 0),
            ),
        )
        for e in ranked[:3]:
            best = e.best_alternative
            actual = e.actual.mean
            if best is None or actual is None:
                continue
            better = (e.delta or 0) > 0
            moments.append(
                Moment(
                    turn_index=e.turn_index,
                    title=e.description,
                    what_happened=f"{e.description} (turn {e.turn_index}).",
                    what_to_try=(
                        f"Consider the '{best.action.label.lower()}' option next time."
                        if better
                        else "Your choice here held up well against the alternatives."
                    ),
                    evidence=(
                        f"Fresh rollouts: actual R={actual:.3f}; "
                        f"'{best.action.label}' R={best.mean:.3f}; "
                        f"95% paired bootstrap interval for delta: {e.delta_interval}. "
                        + (
                            "Hindsight: uses the counterpart sheet."
                            if best.action.hindsight
                            else ""
                        )
                    ),
                )
            )
    profile_focus = {
        "weak_anchor": "anchoring",
        "early_concession": "concession discipline",
        "big_concessions": "concession discipline",
        "no_logroll": "trading across issues",
        "no_questions": "asking questions",
        "accepted_low": "claiming value",
        "below_walkaway": "knowing your walk-away",
        "impasse_with_zopa": "closing",
    }
    focus = profile_focus.get(flag_keys[0], "consistency") if flag_keys else "consistency"
    observations = observe(session, case)
    concrete = [
        f"{ERRORS[key]}: {count.occurrences}/{count.opportunities} opportunities."
        for key, count in observations.counts.items()
        if key in ERRORS and count.occurrences
    ]
    if concrete:
        improvements = concrete
    if session.counterpart_profile and session.counterpart_profile.focus:
        focus = session.counterpart_profile.focus
        focus = ERRORS.get(focus, focus)
    return CoachingReport(
        headline=headline,
        strengths=strengths[:3] or ["You completed the rehearsal."],
        improvements=improvements[:3],
        moments=moments,
        next_focus=focus,
        source="template",
    )


def build_report(
    session: Session,
    case: Case,
    counterfactuals: CounterfactualReport | None = None,
    llm: LLM | None = None,
) -> CoachingReport:
    if session.status not in ("agreed", "impasse"):
        raise ValueError("coaching is available only after the session")
    outcome = outcome_summary(session, case)
    features = extract_features(session, case)
    flag_keys = flags(session, case, features)
    if llm is not None:
        try:
            report = llm.parse(
                SYSTEM,
                [
                    {
                        "role": "user",
                        "content": _prompt(
                            session, case, outcome, features, flag_keys, counterfactuals
                        ),
                    }
                ],
                CoachingReport,
            )
            return report.model_copy(update={"source": "llm"})
        except Exception:  # noqa: BLE001 - fall back to the template; the debrief must render
            pass
    return template_report(session, case, outcome, flag_keys, counterfactuals)


class Debrief(BaseModel):
    """Everything the Feedback page stores per session (data/sessions/feedback/<id>.json)."""

    counterfactuals: CounterfactualReport | None = None
    report: CoachingReport
    usefulness: int | None = Field(default=None, description="Participant rating, 1-5")
    llm_calls: int = 0
    est_cost: float = 0.0
