"""AI 끼리 하는 모의 밴픽.

양 팀을 맡은 에이전트가 표준 밴픽 순서대로 한 수씩 번갈아 두고, 끝나면 해설 에이전트가 정리한다.
각 에이전트는 밴픽 예측 모델이 뽑은 후보 가운데서만 고른다. LLM 이 없으면 후보 1순위를 고르는
정책으로 같은 그래프가 그대로 돈다.

    둔다 ─(20수가 찰 때까지 반복)─→ 둔다 ... → 해설 → 끝
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ..draft_model import DraftModel
from ..gamedata import DRAFT_ORDER, ROLES
from ..llm import LLM
from ..schemas import Team

CANDIDATES = 6

TEAM_AGENT = """\
너는 LoL 프로팀의 밴픽 코치다. 지금 차례에 금지하거나 고를 챔피언 하나를 후보 목록에서 정한다.
규칙:
- 반드시 후보 목록에 있는 이름 그대로 하나만 고른다.
- 이유는 한국어 한 문장(40자 이내)으로, 주어진 정보(후보의 근거, 현재 밴픽 상황)만 써서 적는다.
- 목록에 없는 사실(패치 내용, 선수 컨디션 등)은 지어내지 않는다."""

COMMENTATOR = """\
너는 LoL 중계 해설자다. 끝난 모의 밴픽을 보고 관전 포인트를 한국어 두 문장으로 정리한다.
주어진 밴픽 결과만 근거로 쓰고, 누가 이길지는 말하지 않는다."""


class Choice(BaseModel):
    champion: str = Field(description="후보 목록에 있는 챔피언 이름")
    reason: str = Field(description="한국어 한 문장, 40자 이내")


class Commentary(BaseModel):
    text: str = Field(description="한국어 두 문장")


class Move(BaseModel):
    kind: str
    team_id: int
    champion: str
    role: str = ""
    reason: str = ""


class MockState(TypedDict, total=False):
    moves: Annotated[list[Move], operator.add]
    commentary: str
    by: str


def build_mock_draft_graph(
    model: DraftModel,
    llm: LLM | None,
    first: Team,
    second: Team,
    when: str,
    unavailable: set[str],
    series_bans: dict[int, set[str]] | None = None,
    name: Callable[[str], str] = str,
):
    """first 가 먼저 밴픽하는 팀. unavailable 은 피어리스로 이미 소진된 챔피언.

    name 은 기록의 챔피언 이름을 에이전트에게 보여 줄 이름(한국어)으로 바꾸는 함수다.
    """
    series_bans = series_bans or {}
    teams = {"F": first, "S": second}

    def turn(state: MockState) -> MockState:
        moves = state.get("moves", [])
        kind, who, _i = DRAFT_ORDER[len(moves)]
        team, opp = teams[who], teams["S" if who == "F" else "F"]
        taken = unavailable | {m.champion for m in moves}
        p = model.predict(
            team.id,
            opp.id,
            when,
            unavailable=taken,
            series_bans=series_bans.get(team.id, ()),
            series_denied=series_bans.get(opp.id, ()),
            top=40,
        )
        if kind == "ban":
            options = [(c, "", "상대가 자주 고르거나 최근 자주 금지된 챔피언") for c, _ in p.bans[:CANDIDATES]]
        else:
            filled = {m.role for m in moves if m.kind == "pick" and m.team_id == team.id}
            options = []
            for c, _ in p.picks:
                role = model.likely_role(c)
                if role and role not in filled:
                    options.append((c, role, f"이 팀이 최근 자주 고른 {role} 챔피언"))
                if len(options) == CANDIDATES:
                    break
            if not options:  # 기록이 모자라 포지션을 못 채우면 남은 포지션을 표시만 한다.
                left = next((r for r in ROLES if r not in filled), "")
                options = [(c, left, "기록이 적어 대회 전체 흐름으로 고름") for c, _ in p.picks[:CANDIDATES]]
        if not options:
            return {"moves": [Move(kind=kind, team_id=team.id, champion="(후보 없음)")]}

        champion, role, reason = options[0]
        used_llm = False
        if llm:
            board = "\n".join(
                f"- {'금지' if m.kind == 'ban' else '선택'} {first.name if m.team_id == first.id else second.name}: {name(m.champion)}"
                for m in moves
            ) or "- 아직 없음"
            listing = "\n".join(f"- {name(c)} ({r or '금지 후보'}): {why}" for c, r, why in options)
            user = (
                f"맡은 팀: {team.name} / 상대: {opp.name}\n지금 차례: {'금지' if kind == 'ban' else '선택'}\n\n"
                f"현재까지의 밴픽:\n{board}\n\n후보:\n{listing}"
            )
            try:
                choice = llm.structured(TEAM_AGENT, user, Choice)
                picked = next((o for o in options if choice.champion.strip() in (o[0], name(o[0]))), None)
                if picked:
                    champion, role, reason = picked[0], picked[1], choice.reason
                    used_llm = True
            except Exception as exc:
                print(f"[모의 밴픽] LLM 실패, 1순위 후보로 진행: {exc}")
        out: MockState = {"moves": [Move(kind=kind, team_id=team.id, champion=champion, role=role, reason=reason)]}
        if used_llm:
            out["by"] = "llm"
        return out

    def more(state: MockState) -> str:
        return "turn" if len(state.get("moves", [])) < len(DRAFT_ORDER) else "commentate"

    def commentate(state: MockState) -> MockState:
        moves = state["moves"]

        def comp(team: Team) -> str:
            return ", ".join(f"{m.role} {name(m.champion)}" for m in moves if m.kind == "pick" and m.team_id == team.id)

        if llm:
            try:
                user = f"{first.name} 조합: {comp(first)}\n{second.name} 조합: {comp(second)}"
                return {"commentary": llm.structured(COMMENTATOR, user, Commentary).text}
            except Exception as exc:
                print(f"[모의 밴픽] 해설 LLM 실패: {exc}")
        return {"commentary": f"{first.name} 쪽은 {comp(first)}, {second.name} 쪽은 {comp(second)} 조합으로 예상된다."}

    g = StateGraph(MockState)
    g.add_node("turn", turn)
    g.add_node("commentate", commentate)
    g.add_edge(START, "turn")
    g.add_conditional_edges("turn", more, {"turn": "turn", "commentate": "commentate"})
    g.add_edge("commentate", END)
    return g.compile()


def run_mock_draft(
    model: DraftModel,
    llm: LLM | None,
    first: Team,
    second: Team,
    when: str,
    unavailable: set[str] | None = None,
    series_bans: dict[int, set[str]] | None = None,
    name: Callable[[str], str] = str,
) -> dict[str, Any]:
    graph = build_mock_draft_graph(model, llm, first, second, when, set(unavailable or ()), series_bans, name)
    out = graph.invoke({"moves": []}, config={"recursion_limit": 80})
    return {
        "first_id": first.id,
        "second_id": second.id,
        "moves": [m.model_dump() for m in out["moves"]],
        "commentary": out.get("commentary", ""),
        "by": out.get("by", "policy"),
    }
