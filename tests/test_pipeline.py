"""네트워크·API 키 없이 도는 테스트. LLM 은 스텁으로 대체한다."""
from __future__ import annotations

from pipeline import facts as F
from pipeline.agents.brief import build_context
from pipeline.graphs import build_brief_graph, build_preview_graph
from pipeline.leagues import build_league, importance, make_ranker
from pipeline.pandascore import normalize_match, pick_current_serie
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
        "serie_id": 5001,
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
    assert (m.league_id, m.serie_id, m.tournament) == (293, 5001, "Playoffs")
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
    assert [s.agent for s in out["trace"]] == ["수집", "분석", "작성", "검증", "편집"]


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


def test_league_record_has_standings_schedule_and_status():
    league = build_league(SOURCE.leagues()[0])
    assert league.status == "진행 중" and league.serie == "시범 시즌"
    regular = next(s for s in league.stages if s.name == "정규 시즌")
    top = regular.standings[0]
    assert top.team.acronym == "STG" and (top.wins, top.losses) == (5, 0) and top.streak == 5
    assert sum(r.wins for r in regular.standings) == sum(r.losses for r in regular.standings) == 10
    assert [m.status for m in league.matches].count("running") == 1
    assert league.matches == sorted(league.matches, key=lambda m: m.begin_at)


def test_current_serie_prefers_pending_matches():
    old = MATCH.model_copy(update={"serie_id": 1})
    nxt = SOURCE.upcoming_matches()[0].model_copy(update={"serie_id": 2})
    assert pick_current_serie([old, nxt]) == 2
    assert pick_current_serie([old]) == 1


def test_importance_scores_finals_and_top_clashes():
    league = build_league(SOURCE.leagues()[0])
    ranker = make_ranker([league])
    final = next(m for m in SOURCE.upcoming_matches() if "결승" in m.tournament)
    score, reasons = importance(final, [], ranker(final))
    assert score >= 5 and reasons == ["결승"]
    assert ranker(MATCH) == (1, 3, 4)  # STG 1위, DDR 3위, 4팀
    plain = SOURCE.upcoming_matches()[1]
    assert importance(plain, [], (3, 4, 10))[0] < score
    assert "1·2위 맞대결" in importance(plain, [], (2, 1, 10))[1]


def test_brief_graph_records_importance():
    league = build_league(SOURCE.leagues()[0])
    out = build_brief_graph(None, SOURCE, ranker=make_ranker([league])).invoke({"match": MATCH})
    assert out["importance"] >= 1 and "풀세트" in out["reasons"]


# ---- 시즌 기록 수집(Leaguepedia)과 아카이브 모드 ----

import json

from pipeline import leaguepedia as LP
from pipeline.archive import ArchiveSource
from pipeline.config import Settings
from pipeline.store import Store


class FakeCargo:
    """Cargo API 응답 모양(별칭을 키로 쓰는 행 목록)을 흉내 낸다."""

    requests_made = 0

    def query(self, *, tables, fields, where, order_by):
        self.requests_made += 1
        if "LCK/2026" not in where and "Name IN" not in where:
            return []
        if tables == "MatchSchedule":
            base = {"OverviewPage": "LCK/2026 Season/Rounds 1-2", "Tab": "Week 1", "BestOf": "3"}
            return [
                {**base, "MatchId": "m1", "Team1": "T1", "Team2": "Gen.G", "Team1Score": "2", "Team2Score": "1",
                 "Winner": "1", "Date": "2026-04-01 08:00:00"},
                {**base, "MatchId": "m2", "Team1": "Gen.G", "Team2": "KT Rolster", "Team1Score": "2", "Team2Score": "0",
                 "Winner": "1", "Date": "2026-04-02 08:00:00"},
                {"OverviewPage": "LCK/2026 Season/Playoffs", "Tab": "Finals", "BestOf": "5", "MatchId": "m3",
                 "Team1": "T1", "Team2": "Gen.G", "Team1Score": "", "Team2Score": "", "Winner": "",
                 "Date": "2026-09-13 05:00:00"},
                {**base, "MatchId": "m4", "Team1": "TBD", "Team2": "T1", "Winner": "", "Date": "2026-09-14 05:00:00"},
            ]
        if tables == "ScoreboardGames":
            return [
                {"MatchId": "m1", "N": "2", "WinTeam": "T1", "Len": "31.4"},
                {"MatchId": "m1", "N": "1", "WinTeam": "Gen.G", "Len": "28.9"},
                {"MatchId": "m1", "N": "3", "WinTeam": "T1", "Len": "40.2"},
                {"MatchId": "m2", "N": "1", "WinTeam": "Gen.G", "Len": "25"},  # 한 세트만 있어 버려져야 한다
            ]
        if tables == "Teams":
            return [{"Name": "T1", "Short": "T1"}, {"Name": "Gen.G", "Short": "GEN"}, {"Name": "KT Rolster", "Short": "KT"}]
        return []


def test_leaguepedia_rows_become_matches():
    archive = LP.collect(2026, FakeCargo())
    assert archive["diagnostics"]["stages"] == {"LCK / 정규 시즌 1~2라운드": 2, "LCK / 플레이오프": 1}
    lck = archive["leagues"][0]
    m1, m2, final = lck["matches"]
    assert (m1["team_a"]["acronym"], m1["team_b"]["name"], m1["score_a"], m1["score_b"]) == ("T1", "젠지", 2, 1)
    assert m1["winner_id"] == m1["team_a"]["id"] and m1["begin_at"] == "2026-04-01T08:00:00+00:00"
    assert [(g["position"], g["length_min"]) for g in m1["games"]] == [(1, 29), (2, 31), (3, 40)]
    assert m1["games"][0]["winner_id"] == m1["team_b"]["id"]
    assert m2["games"] == [] and m2["status"] == "finished"
    assert final["status"] == "not_started" and final["best_of"] == 5 and final["tournament"] == "플레이오프"
    assert m1["team_b"]["id"] == m2["team_a"]["id"]  # 같은 팀은 같은 ID


def test_stage_names_from_pages_and_tabs():
    assert LP.stage_name("LCK", "LCK/2026", "LCK/2026 Season/Cup", "Week 1") == "LCK컵 그룹 대항전"
    assert LP.stage_name("LCK", "LCK/2026", "LCK/2026 Season/Cup", "Play-In Round 1") == "LCK컵 플레이-인"
    assert LP.stage_name("LCK", "LCK/2026", "LCK/2026 Season/Cup", "Finals") == "LCK컵 플레이오프"
    assert LP.stage_name("LCK", "LCK/2026", "LCK/2026 Season/Season Playoffs", "Round 1") == "플레이오프"
    msi = "2026 Mid-Season Invitational"
    assert LP.stage_name("MSI", msi, msi, "Play-In Day 1") == "플레이-인"
    assert LP.stage_name("MSI", msi, msi, "Finals") == "브래킷 스테이지"
    assert LP.stage_name("퍼스트 스탠드", "2026 First Stand", "2026 First Stand", "Groups Day 2") == "그룹 스테이지"
    assert LP.stage_name("퍼스트 스탠드", "2026 First Stand", "2026 First Stand", "Semifinals") == "토너먼트"
    assert LP.stage_name("LCK", "LCK/2026", "LCK/2026 Season/Road to MSI", "Round 1") == "MSI 대표 선발전"
    worlds = "2026 Season World Championship"
    assert LP.stage_name("월즈", worlds, f"{worlds}/Play-In", "Round 1") == "플레이-인"
    assert LP.stage_name("월즈", worlds, f"{worlds}/Main Event", "Quarterfinals") == "토너먼트"
    assert LP.stage_name("월즈", worlds, f"{worlds}/Main Event", "Round 3") == "스위스 스테이지"


def test_semifinal_is_not_scored_as_final():
    semi = MATCH.model_copy(update={"stage": "2026 토너먼트 Semifinals", "tournament": "토너먼트", "best_of": 5})
    final = semi.model_copy(update={"stage": "2026 토너먼트 Finals"})
    assert importance(semi, [], (None, None, 0))[1] == ["4강"]
    assert importance(final, [], (None, None, 0))[1] == ["결승"]
    assert importance(final, [], (None, None, 0))[0] > importance(semi, [], (None, None, 0))[0]


def test_archive_mode_builds_site_data(tmp_path, monkeypatch):
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "2026.json").write_text(json.dumps(LP.collect(2026, FakeCargo())), encoding="utf-8")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PANDASCORE_TOKEN", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert Settings().mode == "archive"

    from pipeline.run import main

    assert main() == 0
    store = Store(tmp_path)
    assert store.meta["source"] == "archive" and store.meta["sample"] is False
    assert "Leaguepedia 2026" in store.meta["source_note"]
    results = store.load_results()
    assert len(results) == 2 and results[0].match.team_a.acronym == "GEN"  # 최신순
    assert "역전승" in next(r for r in results if r.match.team_a.acronym == "T1").tags
    assert len(store.load_previews()) == 1
    league = json.loads((tmp_path / "leagues.json").read_text(encoding="utf-8"))[0]
    assert league["name"] == "LCK" and league["serie"] == "2026" and league["status"] == "진행 중"
    assert ArchiveSource(tmp_path / "archive").team_matches(results[0].match.team_a.id)

    # 같은 모드로 다시 돌리면 기존 브리핑을 재사용하고 바뀌는 것이 없다.
    before = (tmp_path / "results.json").read_text(encoding="utf-8")
    assert main() == 0 and (tmp_path / "results.json").read_text(encoding="utf-8") == before


def test_renamed_teams_and_showmatches():
    shorts = {"Gen.G": "GEN", "Kiwoom DRX": "KRX"}
    assert LP.resolve_team("DRX", shorts).id == LP.resolve_team("Kiwoom DRX", shorts).id
    assert LP.resolve_team("Kiwoom DRX", shorts).name == "키움 DRX"
    assert LP.resolve_team("BRION", {}).acronym == "BRO"
    lyon = LP.resolve_team("LYON (2024 American Team)", {})
    assert (lyon.name, lyon.acronym) == ("LYON", "LYON")
    row = {"OverviewPage": "LCK/2026 Season/Rounds 3-4/Classic Showmatch", "Tab": "Day 1", "Team1": "A", "Team2": "B",
           "Winner": "1", "Team1Score": "3", "Team2Score": "0", "Date": "2026-08-01 08:00:00", "MatchId": "x"}
    assert LP.to_match(row, "LCK", 1, "LCK/2026", 2026, {}, []) is None


def test_lck_groups_are_split_and_combined_tables_are_cumulative():
    def row(i, page, t1, t2, w):
        return {"OverviewPage": f"LCK/2026 Season/{page}", "Tab": "Week 1", "BestOf": "3", "MatchId": f"g{i}",
                "Team1": t1, "Team2": t2, "Team1Score": "2" if w == "1" else "0", "Team2Score": "0" if w == "1" else "2",
                "Winner": w, "Date": f"2026-0{4 if page == 'Rounds 1-2' else 7}-{10 + i:02d} 08:00:00"}

    rows = [
        row(1, "Rounds 1-2", "AAA", "CCC", "1"), row(2, "Rounds 1-2", "BBB", "DDD", "1"),
        row(3, "Rounds 1-2", "AAA", "DDD", "1"), row(4, "Rounds 1-2", "BBB", "CCC", "2"),
        row(5, "Rounds 3-4", "AAA", "BBB", "2"), row(6, "Rounds 3-4", "CCC", "DDD", "1"),
    ]
    raw = {"year": 2026, "leagues": {"LCK": {"matches": rows, "games": [], "teams": []}}}
    archive = LP.build(raw)
    assert archive["diagnostics"]["stages"]["LCK / 정규 시즌 3~4라운드 레전드 그룹"] == 1
    assert archive["diagnostics"]["stages"]["LCK / 정규 시즌 3~4라운드 라이즈 그룹"] == 1
    from pipeline.schemas import LeagueFeed

    league = build_league(LeagueFeed.model_validate(archive["leagues"][0]))
    legend = next(s for s in league.stages if s.name.startswith("정규 시즌 최종 레전드"))
    assert [(r.team.acronym, r.wins, r.losses) for r in legend.standings] == [("AAA", 2, 1), ("BBB", 2, 1)]
    rise = next(s for s in league.stages if s.name.startswith("정규 시즌 최종 라이즈"))
    assert [(r.team.acronym, r.wins, r.losses) for r in rise.standings] == [("CCC", 2, 1), ("DDD", 0, 3)]
    names = [s.name for s in league.stages]
    assert names.index(legend.name) < names.index("정규 시즌 3~4라운드 레전드 그룹")
