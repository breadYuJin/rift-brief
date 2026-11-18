"""LangGraph 그래프 정의.

브리핑 그래프 (검증 실패 시 작성 단계로 되돌아가는 루프):

    수집 → 분석 → 작성 → 검증 ─ 통과 ─────────────→ 편집 → 끝
                    ↑        ├ 반려 ─→ (작성으로 되돌림, 최대 MAX_REWRITES 회)
                    └────────┘
                             └ 한도 초과 → 템플릿 폴백 → 편집 → 끝

편집 단계는 스테이지·순위·경기 특징으로 주요 경기 점수를 매긴다.

프리뷰 그래프 (양측 패널을 병렬 실행한 뒤 사회자가 합침):

    수집 ─┬→ A측 패널 ─┬→ 사회자 → 편집 → 끝
          └→ B측 패널 ─┘
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .agents import brief, preview
from .leagues import Ranker
from .llm import LLM


def build_brief_graph(
    llm: LLM | None,
    source: brief.Source,
    max_rewrites: int = 2,
    ranker: Ranker = brief.no_ranks,
    extra_facts: dict[int, list[str]] | None = None,
):
    collect, analyze, write, verify, fallback, edit, route = brief.make_nodes(
        llm, source, max_rewrites, ranker, extra_facts
    )
    g = StateGraph(brief.BriefState)
    g.add_node("collect", collect)
    g.add_node("analyze", analyze)
    g.add_node("write", write)
    g.add_node("verify", verify)
    g.add_node("fallback", fallback)
    g.add_node("edit", edit)
    g.add_edge(START, "collect")
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "write")
    g.add_edge("write", "verify")
    g.add_conditional_edges("verify", route, {"publish": "edit", "rewrite": "write", "fallback": "fallback"})
    g.add_edge("fallback", "edit")
    g.add_edge("edit", END)
    return g.compile()


def build_preview_graph(llm: LLM | None, source: brief.Source, ranker: Ranker = brief.no_ranks):
    collect, advocate_a, advocate_b, moderate, finalize = preview.make_nodes(llm, source, ranker)
    g = StateGraph(preview.PreviewState)
    g.add_node("collect", collect)
    g.add_node("advocate_a", advocate_a)
    g.add_node("advocate_b", advocate_b)
    g.add_node("moderate", moderate)
    g.add_node("finalize", finalize)
    g.add_edge(START, "collect")
    g.add_edge("collect", "advocate_a")
    g.add_edge("collect", "advocate_b")
    g.add_edge(["advocate_a", "advocate_b"], "moderate")
    g.add_edge("moderate", "finalize")
    g.add_edge("finalize", END)
    return g.compile()
