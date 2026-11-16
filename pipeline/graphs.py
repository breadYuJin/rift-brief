"""LangGraph 그래프 정의.

브리핑 그래프 (검증 실패 시 작성 단계로 되돌아가는 루프):

    수집 → 분석 → 작성 → 검증 ─ 통과 ─→ 끝
                    ↑        ├ 반려 ─→ (작성으로 되돌림, 최대 MAX_REWRITES 회)
                    └────────┘
                             └ 한도 초과 → 템플릿 폴백 → 끝

프리뷰 그래프 (양측 패널을 병렬 실행한 뒤 사회자가 합침):

    수집 ─┬→ A측 패널 ─┬→ 사회자 → 마무리 → 끝
          └→ B측 패널 ─┘
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .agents import brief, preview
from .llm import LLM


def build_brief_graph(llm: LLM | None, source: brief.Source, max_rewrites: int = 2):
    collect, analyze, write, verify, fallback, route = brief.make_nodes(llm, source, max_rewrites)
    g = StateGraph(brief.BriefState)
    g.add_node("collect", collect)
    g.add_node("analyze", analyze)
    g.add_node("write", write)
    g.add_node("verify", verify)
    g.add_node("fallback", fallback)
    g.add_edge(START, "collect")
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "write")
    g.add_edge("write", "verify")
    g.add_conditional_edges("verify", route, {"publish": END, "rewrite": "write", "fallback": "fallback"})
    g.add_edge("fallback", END)
    return g.compile()


def build_preview_graph(llm: LLM | None, source: brief.Source):
    collect, advocate_a, advocate_b, moderate, finalize = preview.make_nodes(llm, source)
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
