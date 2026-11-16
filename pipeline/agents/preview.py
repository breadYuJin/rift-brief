"""경기 프리뷰 토론 에이전트: 수집 → (A측 패널 ∥ B측 패널) → 사회자 → 점검."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from .. import facts as F
from ..llm import LLM
from ..schemas import Case, Context, Match, Team, TeamForm, TraceStep, WatchPoints
from . import prompts
from .brief import Source, _facts_block, _step, build_context


class PreviewState(TypedDict, total=False):
    match: Match
    context: Context
    facts: list[str]
    case_a: list[str]
    case_b: list[str]
    watch_points: list[str]
    # 병렬 패널이 동시에 써도 되도록 누적(reducer) 채널로 둔다.
    llm_used: Annotated[list[bool], operator.add]
    generated_by: str
    trace: Annotated[list[TraceStep], operator.add]


def template_case(team: Team, form: TeamForm, h2h_wins: int, h2h_losses: int) -> list[str]:
    points: list[str] = []
    if form.streak >= 2:
        points.append(f"{team.name} 쪽은 {form.streak}연승으로 흐름이 좋다.")
    elif form.recent and form.wins > form.losses:
        points.append(f"{team.name} 쪽은 최근 {len(form.recent)}경기 {F.form_text(form)}로 승이 더 많다.")
    if h2h_wins > h2h_losses:
        points.append(f"최근 맞대결에서 {h2h_wins}승 {h2h_losses}패로 우위다.")
    if not points:
        points.append(f"{team.name} 쪽은 최근 기록에서 뚜렷한 우위는 없지만 다전제 변수는 열려 있다.")
    return points


def template_watch_points(match: Match, ctx: Context) -> list[str]:
    points = [f"{match.best_of}전제 승부에서 1세트 기선을 어느 쪽이 잡는지."]
    for team, form in ((match.team_a, ctx.form_a), (match.team_b, ctx.form_b)):
        if form.streak >= 2:
            points.append(f"{team.name} 쪽의 {form.streak}연승 흐름이 이어질지.")
        elif form.streak <= -2:
            points.append(f"{team.name} 쪽이 {-form.streak}연패를 끊을 수 있을지.")
    if len(points) < 2:
        points.append("최근 성적이 비슷한 두 팀이라 세트마다 흐름이 갈릴 수 있다.")
    return points[:3]


def make_nodes(llm: LLM | None, source: Source):
    def collect(state: PreviewState) -> PreviewState:
        match = state["match"]
        ctx = build_context(match, source)
        facts = F.preview_facts(match, ctx)
        return {"context": ctx, "facts": facts, "trace": _step("수집", f"팩트 {len(facts)}개 정리")}

    def advocate(side: str):
        def node(state: PreviewState) -> PreviewState:
            match, ctx = state["match"], state["context"]
            is_a = side == "a"
            team = match.team_a if is_a else match.team_b
            form = ctx.form_a if is_a else ctx.form_b
            wins, losses = (ctx.h2h_a_wins, ctx.h2h_b_wins) if is_a else (ctx.h2h_b_wins, ctx.h2h_a_wins)
            key = f"case_{side}"
            if llm:
                try:
                    user = f"{_facts_block(state['facts'])}\n\n맡은 팀: {team.name}"
                    case = llm.structured(prompts.ADVOCATE, user, Case)
                    if not F.check_text(case.points, state["facts"], match):
                        return {
                            key: case.points,
                            "llm_used": [True],
                            "trace": _step(f"{team.acronym} 패널", case.points[0]),
                        }
                    print(f"[{team.acronym} 패널] 팩트 검사 실패, 템플릿으로 대체")
                except Exception as exc:
                    print(f"[{team.acronym} 패널] LLM 실패, 템플릿으로 대체: {exc}")
            points = template_case(team, form, wins, losses)
            return {key: points, "llm_used": [False], "trace": _step(f"{team.acronym} 패널", points[0])}

        return node

    def moderate(state: PreviewState) -> PreviewState:
        match, ctx = state["match"], state["context"]
        if llm:
            try:
                user = (
                    f"{_facts_block(state['facts'])}\n\n"
                    f"{match.team_a.name} 측 주장:\n" + "\n".join(f"- {p}" for p in state["case_a"]) + "\n\n"
                    f"{match.team_b.name} 측 주장:\n" + "\n".join(f"- {p}" for p in state["case_b"])
                )
                wp = llm.structured(prompts.MODERATOR, user, WatchPoints)
                if not F.check_text(wp.points, state["facts"], match):
                    return {
                        "watch_points": wp.points,
                        "llm_used": [True],
                        "trace": _step("사회자", f"관전 포인트 {len(wp.points)}개 정리"),
                    }
                print("[사회자] 팩트 검사 실패, 템플릿으로 대체")
            except Exception as exc:
                print(f"[사회자] LLM 실패, 템플릿으로 대체: {exc}")
        points = template_watch_points(match, ctx)
        return {
            "watch_points": points,
            "llm_used": [False],
            "trace": _step("사회자", f"관전 포인트 {len(points)}개 정리"),
        }

    def finalize(state: PreviewState) -> PreviewState:
        used = state.get("llm_used", [])
        return {"generated_by": "llm" if any(used) else "template"}

    return collect, advocate("a"), advocate("b"), moderate, finalize
