"""네트워크·API 키 없이 도는 테스트. LLM 은 스텁으로 대체한다."""
from __future__ import annotations

from pipeline import facts as F
from pipeline.agents.brief import build_context
from pipeline.graphs import build_brief_graph, build_preview_graph
from pipeline.pandascore import normalize_match
from pipeline.sample import SampleSource
from pipeline.schemas import Analysis, Case, Draft, Review, WatchPoints


class StubLLM:
    """스키마별로 미리 정해 둔 응답을 순서대로 돌려준다."""

    name = "stub"

    def __init__(self, **responses):
        self.responses = {k: list(v) for k, v in responses.items()}
        self.calls: list[str] = []

    def structured(self, system, user, schema):
        self.calls.append(schema.__name__)
        queue = self.responses[schema.__name__]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item


SOURCE = SampleSource()
MATCH = SOURCE.past_matches()[0]  # STG 2-1 DDR, 1세트를 내주고 역전
ANALYSIS = Analysis(angle="역전승", key_points=["1세트를 내주고 뒤집었다"])
GOOD = Draft(
    headline="STG, DDR 상대로 2-1 역전승",
    summary=["샘플 타이거즈, 데모 드래곤즈 상대로 2-1 승리.", "1세트를 내준 뒤 내리 두 세트를 가져왔다.", "풀세트 승부였다."],
)
BAD_NUMBER = Draft(headline="STG, DDR 상대로 2-1 승리", summary=["킬 스코어 17 대 9 로 압도했다.", "b", "c"])


def test_normalize_match_from_pandascore_payload():
    raw = {
        "id": 77,
        "status": "finished",
        "number_of_games": 3,
        "begin_at": "2026-11-01T08:00:00Z",
        "end_at": "2026-11-01T10:30:00Z",
        "winner_id": 10,
        "league": {"id": 293, "name": "LCK"},
        "serie": {"full_name": "Summer 2026"},
        "tournament": {"name": "Playoffs"},
        "opponents": [
            {"type": "Team", "opponent": {"id": 10, "name": "Alpha", "acronym": "ALP"}},
            {"type": "Team", "opponent": {"id": 20, "name": "Beta", "acronym": None}},
        ],
        "results": [{"team_id": 10, "score": 2}, {"team_id": 20, "score": 0}],
        "games": [
            {"position": 2, "finished": True, "length": 1790, "winner": {"id": 10}},
            {"position": 1, "finished": True, "length": 2040, "winner": {"id": 10}},
            {"position": 3, "finished": False, "status": "not_played", "winner": {"id": None}},
        ],
    }
    m = normalize_match(raw)
    assert m and (m.score_a, m.score_b) == (2, 0)
    assert m.stage == "Summer 2026 Playoffs"
    assert m.team_b.acronym == "Beta"
    assert [g.position for g in m.games] == [1, 2] and m.games[0].length_min == 34
    assert normalize_match({**raw, "opponents": raw["opponents"][:1]}) is None  # 상대 미정


def test_facts_and_tags():
    facts, tags = F.result_facts(MATCH, build_context(MATCH, SOURCE))
    assert "풀세트" in tags and "역전승" in tags
    assert any("승리 팀: 샘플 타이거즈" in f for f in facts)

    reverse_sweep = next(m for m in SOURCE.team_matches(1) if m.best_of == 5)
    _, tags = F.result_facts(reverse_sweep, build_context(reverse_sweep, SOURCE))
    assert "역스윕" in tags


def test_context_excludes_the_match_itself_and_later_games():
    ctx = build_context(MATCH, SOURCE)
    assert all((e.date or "") < MATCH.end_at for e in ctx.form_a.recent + ctx.form_b.recent)


def test_check_draft_catches_unsupported_numbers_and_wrong_winner():
    facts, _ = F.result_facts(MATCH, build_context(MATCH, SOURCE))
    assert F.check_draft(GOOD, facts, MATCH) == []
    assert any("숫자" in i for i in F.check_draft(BAD_NUMBER, facts, MATCH))
    wrong = Draft(headline="DDR 승리", summary=["a", "b", "c"])
    assert any("승리 팀" in i or "패배 팀" in i for i in F.check_draft(wrong, facts, MATCH))


def test_template_mode_runs_without_llm():
    out = build_brief_graph(None, SOURCE).invoke({"match": MATCH})
    assert out["generated_by"] == "template" and out["review"].ok
    assert [s.agent for s in out["trace"]] == ["수집", "분석", "작성", "검증"]


def test_rejected_draft_is_rewritten_then_published():
    llm = StubLLM(Analysis=[ANALYSIS], Draft=[BAD_NUMBER, GOOD], Review=[Review(ok=True)])
    out = build_brief_graph(llm, SOURCE).invoke({"match": MATCH})
    assert out["draft"] == GOOD and out["generated_by"] == "llm" and out["attempts"] == 2
    assert llm.calls.count("Draft") == 2
    assert any(s.agent == "검증" and s.note.startswith("반려") for s in out["trace"])


def test_llm_critic_can_reject():
    llm = StubLLM(
        Analysis=[ANALYSIS],
        Draft=[GOOD],
        Review=[Review(ok=False, issues=["팩트에 없는 주장"]), Review(ok=True)],
    )
    out = build_brief_graph(llm, SOURCE).invoke({"match": MATCH})
    assert out["attempts"] == 2 and out["review"].ok


def test_falls_back_to_template_after_rewrite_limit():
    llm = StubLLM(Analysis=[ANALYSIS], Draft=[BAD_NUMBER], Review=[Review(ok=True)])
    out = build_brief_graph(llm, SOURCE, max_rewrites=2).invoke({"match": MATCH})
    assert llm.calls.count("Draft") == 3
    assert out["generated_by"] == "template" and out["review"].ok
    facts, _ = F.result_facts(MATCH, build_context(MATCH, SOURCE))
    assert F.check_draft(out["draft"], facts, MATCH) == []


def test_llm_error_degrades_to_template():
    llm = StubLLM(Analysis=[RuntimeError("quota")], Draft=[RuntimeError("quota")], Review=[Review(ok=True)])
    out = build_brief_graph(llm, SOURCE).invoke({"match": MATCH})
    assert out["generated_by"] == "template" and out["review"].ok


def test_preview_debate_runs_both_panels():
    upcoming = SOURCE.upcoming_matches()[0]
    out = build_preview_graph(None, SOURCE).invoke({"match": upcoming})
    assert out["case_a"] and out["case_b"] and len(out["watch_points"]) >= 2
    assert out["generated_by"] == "template"

    llm = StubLLM(
        Case=[Case(points=["최근 흐름이 좋다."])],
        WatchPoints=[WatchPoints(points=["1세트 기선 제압 여부.", "연승 흐름이 이어질지."])],
    )
    out = build_preview_graph(llm, SOURCE).invoke({"match": upcoming})
    assert out["generated_by"] == "llm" and llm.calls.count("Case") == 2


def test_preview_rejects_panel_output_with_unsupported_numbers():
    upcoming = SOURCE.upcoming_matches()[0]
    llm = StubLLM(
        Case=[Case(points=["승률 87%로 압도적이다."])],
        WatchPoints=[WatchPoints(points=["a 포인트.", "b 포인트."])],
    )
    out = build_preview_graph(llm, SOURCE).invoke({"match": upcoming})
    assert all("87" not in p for p in out["case_a"] + out["case_b"])
