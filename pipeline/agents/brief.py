"""경기 결과 브리핑 에이전트: 수집 → 분석 → 작성 → 검증."""

from __future__ import annotations

import operator
from typing import Annotated, Protocol, TypedDict

from .. import facts as F
from ..leagues import Ranker, importance
from ..llm import LLM
from ..pandascore import form_from_matches
from ..schemas import Analysis, Context, Draft, Match, Review, TraceStep
from . import prompts


class Source(Protocol):
    def team_matches(self, team_id: int) -> list[Match]: ...


class BriefState(TypedDict, total=False):
    match: Match
    context: Context
    facts: list[str]
    tags: list[str]
    analysis: Analysis
    draft: Draft
    review: Review
    attempts: int
    generated_by: str
    importance: int
    reasons: list[str]
    trace: Annotated[list[TraceStep], operator.add]


def _step(agent: str, note: str) -> list[TraceStep]:
    return [TraceStep(agent=agent, note=note)]


def _facts_block(facts: list[str]) -> str:
    return "팩트:\n" + "\n".join(f"- {f}" for f in facts)


def build_context(match: Match, source: Source) -> Context:
    """두 팀의 '이 경기 이전' 최근 전적과 맞대결 기록을 모은다."""
    before = match.end_at or match.begin_at
    a_matches = source.team_matches(match.team_a.id)
    b_matches = source.team_matches(match.team_b.id)
    h2h = [
        m
        for m in a_matches
        if match.team_b.id in (m.team_a.id, m.team_b.id)
        and m.id != match.id
        and m.winner_id
        and (not before or (m.end_at or "") < before)
    ]
    return Context(
        form_a=form_from_matches(match.team_a.id, [m for m in a_matches if m.id != match.id], before),
        form_b=form_from_matches(match.team_b.id, [m for m in b_matches if m.id != match.id], before),
        h2h_a_wins=sum(1 for m in h2h if m.winner_id == match.team_a.id),
        h2h_b_wins=sum(1 for m in h2h if m.winner_id == match.team_b.id),
    )


# ---- 템플릿(LLM 없이도 항상 통과하는 기준선) ----


def template_draft(match: Match, facts: list[str], tags: list[str]) -> Draft:
    winner, loser = match.winner, match.loser
    assert winner and loser
    ws, ls = max(match.score_a, match.score_b), min(match.score_a, match.score_b)
    if "역스윕" in tags:
        headline = f"{winner.acronym}, {loser.acronym} 상대로 역스윕"
    elif "셧아웃" in tags:
        headline = f"{winner.acronym}, {loser.acronym} 상대로 {ws}-{ls} 완승"
    elif "풀세트" in tags:
        headline = f"{winner.acronym}, 풀세트 끝에 {loser.acronym} 제압"
    else:
        headline = f"{winner.acronym}, {loser.acronym} 상대로 {ws}-{ls} 승리"

    def pick(*keys: str) -> str | None:
        return next((f for f in facts if any(k in f for k in keys)), None)

    flow = pick("내준 뒤", "내주고", "한 세트도", "풀세트") or pick("세트별 승자") or facts[3]
    context = pick("흐름", "맞대결", "최근") or facts[0]
    return Draft(
        headline=headline,
        summary=[
            f"{winner.name}, {loser.name} 상대로 세트 스코어 {ws}-{ls} 승리.",
            f"{flow.replace(': ', ' ')}.",
            f"{context.replace(': ', ' ')}.",
        ],
    )


# ---- 노드 ----


def no_ranks(match: Match) -> tuple[int | None, int | None, int]:
    return None, None, 0


def make_nodes(
    llm: LLM | None,
    source: Source,
    max_rewrites: int,
    ranker: Ranker = no_ranks,
    extra_facts: dict[int, list[str]] | None = None,
):
    def collect(state: BriefState) -> BriefState:
        match = state["match"]
        ctx = build_context(match, source)
        facts, tags = F.result_facts(match, ctx)
        # 세트별 킬·오브젝트·교전 기록이 있으면 근거에 덧붙인다(경기 후 분석의 재료).
        facts = facts + (extra_facts or {}).get(match.id, [])
        note = f"최근 전적 {len(ctx.form_a.recent)}+{len(ctx.form_b.recent)}경기, 팩트 {len(facts)}개 정리"
        return {"context": ctx, "facts": facts, "tags": tags, "attempts": 0, "trace": _step("수집", note)}

    def analyze(state: BriefState) -> BriefState:
        facts, tags = state["facts"], state["tags"]
        if llm:
            try:
                analysis = llm.structured(prompts.ANALYST, _facts_block(facts), Analysis)
                return {"analysis": analysis, "trace": _step("분석", f"관점: {analysis.angle}")}
            except Exception as exc:
                print(f"[분석] LLM 실패, 규칙 기반으로 대체: {exc}")
        angle = ", ".join(tags) if tags else "무난한 승리"
        analysis = Analysis(angle=angle, key_points=facts[3:6])
        return {"analysis": analysis, "trace": _step("분석", f"규칙 기반 관점: {angle}")}

    def write(state: BriefState) -> BriefState:
        attempt = state.get("attempts", 0) + 1
        match, facts, tags = state["match"], state["facts"], state["tags"]
        if llm:
            analysis = state["analysis"]
            user = (
                f"{_facts_block(facts)}\n\n분석가의 관점: {analysis.angle}\n"
                + "핵심 포인트:\n"
                + "\n".join(f"- {p}" for p in analysis.key_points)
            )
            review = state.get("review")
            if review and not review.ok:
                prev = state["draft"]
                user += (
                    "\n\n이전 초안이 반려됐다. 아래 문제를 고쳐 다시 쓴다.\n"
                    f"이전 헤드라인: {prev.headline}\n" + "\n".join(f"- {i}" for i in review.issues)
                )
            try:
                draft = llm.structured(prompts.WRITER, user, Draft)
                return {
                    "draft": draft,
                    "attempts": attempt,
                    "generated_by": "llm",
                    "trace": _step("작성", f"{attempt}차 초안: {draft.headline}"),
                }
            except Exception as exc:
                print(f"[작성] LLM 실패, 템플릿으로 대체: {exc}")
        draft = template_draft(match, facts, tags)
        return {
            "draft": draft,
            "attempts": attempt,
            "generated_by": "template",
            "trace": _step("작성", f"템플릿 초안: {draft.headline}"),
        }

    def verify(state: BriefState) -> BriefState:
        match, facts, draft = state["match"], state["facts"], state["draft"]
        issues = F.check_draft(draft, facts, match)
        if not issues and llm and state.get("generated_by") == "llm":
            try:
                user = f"{_facts_block(facts)}\n\n초안:\n헤드라인: {draft.headline}\n" + "\n".join(
                    f"{i}. {s}" for i, s in enumerate(draft.summary, 1)
                )
                critic = llm.structured(prompts.VERIFIER, user, Review)
                if not critic.ok:
                    issues = critic.issues or ["팩트체커가 반려함"]
            except Exception as exc:
                print(f"[검증] LLM 실패, 규칙 검증 결과만 사용: {exc}")
        review = Review(ok=not issues, issues=issues)
        note = "통과" if review.ok else "반려: " + "; ".join(issues)
        return {"review": review, "trace": _step("검증", note)}

    def fallback(state: BriefState) -> BriefState:
        draft = template_draft(state["match"], state["facts"], state["tags"])
        return {
            "draft": draft,
            "review": Review(ok=True),
            "generated_by": "template",
            "trace": _step("검증", "재작성 한도 초과 → 템플릿 브리핑으로 교체"),
        }

    def edit(state: BriefState) -> BriefState:
        score, reasons = importance(state["match"], state["tags"], ranker(state["match"]))
        note = f"주요 경기 점수 {score}" + (f" ({', '.join(reasons)})" if reasons else "")
        return {"importance": score, "reasons": reasons, "trace": _step("편집", note)}

    def route(state: BriefState) -> str:
        if state["review"].ok:
            return "publish"
        if state.get("generated_by") == "llm" and state["attempts"] <= max_rewrites:
            return "rewrite"
        return "fallback"

    return collect, analyze, write, verify, fallback, edit, route
