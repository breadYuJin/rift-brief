"""밴픽 예측, 승률, 경기 후 분석, 모의 밴픽 그래프의 테스트. 네트워크를 쓰지 않는다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from pipeline import analysis, insights
from pipeline.agents.mock_draft import Choice, Commentary, run_mock_draft
from pipeline.draft_model import DraftModel, meta_only, rank_hit_rates, recall, replay, tune
from pipeline.gamedata import DRAFT_ORDER, ROLES, DraftStep, PlayerLine, SetRecord, TeamStats, build_sets
from pipeline.live import DraftEvent, GridFeed, ManualFeed, track
from pipeline.schemas import Team
from pipeline.win_model import report, walk_forward

T1 = Team(id=1, name="알파", acronym="ALP")
T2 = Team(id=2, name="브라보", acronym="BRV")
T3 = Team(id=3, name="찰리", acronym="CHA")

# 팀마다 즐겨 쓰는 챔피언(포지션 순)과 즐겨 금지하는 챔피언
POOL = {
    1: (["가렌", "리신", "아리", "징크스", "쓰레쉬"], ["제드", "야스오", "카직스", "루시안", "노틸러스"]),
    2: (["다리우스", "바이", "오리아나", "케이틀린", "룰루"], ["레넥톤", "그레이브즈", "르블랑", "이즈리얼", "라칸"]),
    3: (["잭스", "세주아니", "신드라", "애쉬", "브라움"], ["피오라", "엘리스", "빅토르", "자야", "알리스타"]),
}
START = datetime(2026, 1, 10, 8, 0, tzinfo=timezone.utc)


def make_set(i: int, blue: Team, red: Team, winner: Team, match_id: int = 0, number: int = 1, picks=None) -> SetRecord:
    picks = picks or {blue.id: POOL[blue.id][0], red.id: POOL[red.id][0]}
    count = {"F": {"ban": 0, "pick": 0}, "S": {"ban": 0, "pick": 0}}
    teams = {"F": blue, "S": red}
    draft = []
    for kind, who, _n in DRAFT_ORDER:
        team = teams[who]
        k = count[who][kind]
        count[who][kind] += 1
        if kind == "ban":
            draft.append(DraftStep(kind="ban", team_id=team.id, champion=POOL[team.id][1][k]))
        else:
            draft.append(DraftStep(kind="pick", team_id=team.id, champion=picks[team.id][k], role=ROLES[k]))
    players = [
        PlayerLine(team_id=t.id, player=f"{t.acronym}{r}", champion=picks[t.id][j], role=r, kills=j, deaths=1, assists=2, cs=200, gold=10000, damage=15000, vision=30)
        for t in (blue, red)
        for j, r in enumerate(ROLES)
    ]
    return SetRecord(
        game_id=f"g{i}",
        match_id=match_id or 1000 + i,
        league="LCK",
        number=number,
        start=(START + timedelta(days=i)).isoformat(),
        patch="26.1",
        blue=blue,
        red=red,
        winner_id=winner.id,
        length_min=30.0,
        first_pick_id=blue.id,
        draft=draft,
        blue_stats=TeamStats(kills=10, dragons=3, barons=1, towers=9),
        red_stats=TeamStats(kills=10, dragons=1, towers=3),
        players=players,
        rpg=f"KR_{i}",
    )


def season(n: int = 40) -> list[SetRecord]:
    pairs = [(T1, T2), (T2, T3), (T3, T1), (T2, T1), (T3, T2), (T1, T3)]
    out = []
    for i in range(n):
        blue, red = pairs[i % len(pairs)]
        # 알파가 가장 세고 찰리가 가장 약하다.
        winner = min((blue, red), key=lambda t: t.id)
        out.append(make_set(i, blue, red, winner))
    return out


# ---- 밴픽 예측 ----


def test_draft_model_predicts_from_team_history():
    model = DraftModel()
    for s in season(12):
        model.add(s)
    p = model.predict(T1.id, T2.id, (START + timedelta(days=13)).isoformat())
    assert {c for c, _ in p.picks[:5]} == set(POOL[1][0])
    # 금지 예상에는 자기 팀이 금지해 온 챔피언과 상대가 고르는 챔피언이 섞여 나온다.
    predicted = {c for c, _ in p.bans}
    assert set(POOL[1][1]) <= predicted
    assert set(POOL[2][0]) <= predicted
    assert p.picks_by_role["미드"][0][0] == "아리"
    assert model.likely_role("징크스") == "원딜"
    assert model.knows(T1.id) and not model.knows(99)


def test_draft_model_excludes_unavailable_and_boosts_repeat_bans():
    model = DraftModel()
    for s in season(12):
        model.add(s)
    when = (START + timedelta(days=13)).isoformat()
    p = model.predict(T1.id, T2.id, when, unavailable={"아리", "제드"}, series_bans={"티모"})
    assert "아리" not in {c for c, _ in p.picks}
    assert "제드" not in {c for c, _ in p.bans}
    assert p.bans[0][0] == "티모"  # 같은 시리즈에서 이미 금지했던 챔피언이 맨 위로 온다


def test_replay_uses_only_earlier_sets_and_applies_fearless():
    sets = season(18)
    # 같은 시리즈의 2세트: 1세트에서 쓴 챔피언은 예상에서 빠져야 한다.
    first = make_set(30, T1, T2, T1, match_id=77, number=1)
    alt = {1: ["오른", "녹턴", "아지르", "바루스", "카르마"], 2: ["크산테", "신짜오", "탈리야", "세나", "렐"]}
    second = make_set(30, T1, T2, T1, match_id=77, number=2, picks=alt)
    second = second.model_copy(update={"game_id": "g30b", "start": (START + timedelta(days=30, hours=1)).isoformat()})
    forecasts, model = replay(sets + [first, second])
    assert forecasts[0].picks == [] and forecasts[0].bans == []  # 첫 세트 앞에는 기록이 없다
    f2 = next(f for f in forecasts if f.game_id == "g30b" and f.team_id == T1.id)
    assert not set(first.picked) & {c for c, _ in f2.picks}
    assert model.sets_seen == 20
    assert 0.0 <= recall(forecasts, "pick", 10) <= 1.0
    rates = rank_hit_rates(forecasts, "pick")
    assert len(rates) == 10 and rates[0] > 0.5


def test_team_model_beats_meta_only_and_tune_runs():
    sets = season(48)
    team_based, _ = replay(sets)
    baseline, _ = replay(sets, meta_only())
    assert recall(team_based, "pick", 5) > recall(baseline, "pick", 5)
    assert tune(sets).tau_team in (45.0, 90.0, 180.0)


# ---- 승률 ----


def test_win_model_walk_forward():
    import pipeline.win_model as wm

    sets = season(90)
    old = wm.MIN_TRAIN
    wm.MIN_TRAIN = 30
    try:
        forecasts, model = walk_forward(sets)
    finally:
        wm.MIN_TRAIN = old
    assert len(forecasts) == 60
    assert all(0.0 < f.before_draft < 1.0 and 0.0 < f.after_draft < 1.0 for f in forecasts)
    r = report(forecasts)
    assert r["before_draft"]["accuracy"] > 0.9  # 항상 강팀이 이기는 가짜 시즌
    assert r["before_draft"]["brier"] < r["coin"]["brier"]
    before, after = model.probability(T1.id, T3.id, POOL[1][0], POOL[3][0])
    assert before > 0.7 and after > 0.7


# ---- 경기 후 분석 ----

TIMELINE = {
    # [초, 처치자, 죽은 선수, 도움, x, y]
    "kills": [
        [200, 2, 7, [3], 9800, 4400],
        [215, 8, 2, [], 9900, 4500],
        [220, 3, 8, [], 9700, 4300],
        [900, 6, 1, [], 1500, 12000],
        [1500, 0, 9, [], 5000, 10400],
    ],
    "monsters": [[400, "DRAGON", "FIRE_DRAGON", 100], [1300, "BARON_NASHOR", "", 200], [1800, "DRAGON", "ELDER_DRAGON", 100]],
    "buildings": [],
    "gold": [[2500, 2500], [3200, 3000], [4100, 4500]],
    "pos": [[[0, 0]] * 10] + [[[i * 100 + m, m] for i in range(10)] for m in range(1, 4)],
}


def test_fights_objectives_and_zones():
    fs = insights.fights(TIMELINE)
    assert [(f["blue"], f["red"]) for f in fs] == [(2, 1), (0, 1), (1, 0)]
    assert fs[0]["zone"] == "드래곤 둥지" and fs[0]["winner"] == "blue"
    assert fs[1]["zone"] == "탑" and fs[2]["zone"] == "바론 둥지"
    assert [o["name"] for o in insights.objectives(TIMELINE)] == ["드래곤", "바론", "장로 드래곤"]
    assert insights.gold_diff(TIMELINE) == [0, 200, -400]
    paths = insights.jungle_paths(TIMELINE)
    assert paths["blue"] == [[101, 1], [102, 2], [103, 3]] and paths["red"][0] == [601, 1]
    assert insights.zone(7500, 7500) == "미드" and insights.zone(None, 1) == ""


def test_participant_check_and_matchups():
    s = make_set(1, T1, T2, T1)
    kills = []
    for i, p in enumerate(insights._ordered_players(s)):
        kills += [[100 + i, i + 1, 10 - i if i < 5 else 1, [], 100, 100]] * p.kills
    assert insights.participants_match(s, {"kills": kills})
    assert not insights.participants_match(s, {"kills": kills[:-1]})
    rows = insights.matchups(s)
    assert [r["role"] for r in rows] == ROLES
    assert rows[2]["blue"]["champion"] == "아리" and rows[2]["blue"]["cs_min"] == 6.7
    summary = insights.set_summary(s, TIMELINE)
    assert summary["fight_count"] == {"total": 3, "blue": 2, "red": 1}
    assert summary["first_blood"] == {"t": 200, "side": "blue", "zone": "드래곤 둥지"}
    assert insights.set_summary(s, None) == {"has_timeline": False}
    avg = insights.player_averages(season(12))
    assert avg[(1, "ALP미드")]["sets"] == 8 and avg[(1, "ALP미드")]["cs_min"] == 6.67


# ---- 모의 밴픽 에이전트 ----


class PickSecond:
    """항상 후보 목록의 두 번째를 고르는 가짜 LLM."""

    name = "fake"

    def __init__(self):
        self.calls = 0

    def structured(self, system, user, schema):
        self.calls += 1
        if schema is Commentary:
            return Commentary(text="가짜 해설.")
        options = [line[2:].split(" (")[0] for line in user.split("후보:\n")[1].splitlines()]
        return Choice(champion=options[min(1, len(options) - 1)], reason="두 번째 후보")


def trained() -> DraftModel:
    model = DraftModel()
    for s in season(24):
        model.add(s)
    return model


def test_mock_draft_policy_fills_all_steps_without_duplicates():
    out = run_mock_draft(trained(), None, T1, T2, (START + timedelta(days=30)).isoformat())
    moves = out["moves"]
    assert len(moves) == 20 and out["by"] == "policy"
    assert [m["kind"] for m in moves] == [k for k, _, _ in DRAFT_ORDER]
    champions = [m["champion"] for m in moves]
    assert len(set(champions)) == 20
    for team in (T1, T2):
        roles = [m["role"] for m in moves if m["kind"] == "pick" and m["team_id"] == team.id]
        assert sorted(roles) == sorted(ROLES)
    assert "알파" in out["commentary"]


def test_mock_draft_with_llm_and_fearless():
    llm = PickSecond()
    gone = set(POOL[1][0][:2])
    out = run_mock_draft(trained(), llm, T1, T2, (START + timedelta(days=30)).isoformat(), unavailable=gone)
    assert out["by"] == "llm" and out["commentary"] == "가짜 해설." and llm.calls == 21
    assert not gone & {m["champion"] for m in out["moves"]}
    assert any(m["reason"] == "두 번째 후보" for m in out["moves"])


def test_mock_draft_shows_korean_names_to_agents():
    seen: list[str] = []

    class Reader(PickSecond):
        def structured(self, system, user, schema):
            seen.append(user)
            return super().structured(system, user, schema)

    out = run_mock_draft(trained(), Reader(), T1, T2, (START + timedelta(days=30)).isoformat(), name=lambda c: f"한글{c}")
    assert "한글" in seen[0].split("후보:")[1]
    # 에이전트가 보여 준 이름으로 답해도 기록에는 원래 이름으로 남는다.
    assert out["by"] == "llm" and not any(m["champion"].startswith("한글") for m in out["moves"])


def test_mock_draft_rejects_choice_outside_candidates():
    class Rogue:
        name = "rogue"

        def structured(self, system, user, schema):
            if schema is Commentary:
                raise RuntimeError("down")
            return Choice(champion="없는챔피언", reason="무시돼야 함")

    out = run_mock_draft(trained(), Rogue(), T1, T2, (START + timedelta(days=30)).isoformat())
    assert out["by"] == "policy"
    assert "없는챔피언" not in {m["champion"] for m in out["moves"]}
    assert out["commentary"]


# ---- 실시간 추적 뼈대 ----


def test_track_updates_after_each_event():
    s = make_set(40, T1, T2, T1)
    views = list(track(ManualFeed.from_set(s), trained(), T1, T2, s.start))
    assert len(views) == 20 and views[0]["step"] == 1 and views[0]["kind"] == "ban"
    assert views[1]["after"]["champion"] == s.draft[0].champion
    seen: set[str] = set()
    for view, step in zip(views[1:], s.draft):
        seen.add(step.champion)
        assert not seen & {c for c, _ in view["candidates"]}
    try:
        next(GridFeed("series").events())
        raise AssertionError("GridFeed 는 아직 구현 전이어야 한다")
    except NotImplementedError:
        pass
    assert DraftEvent(kind="ban", team_id=1, champion="제드").champion == "제드"


# ---- 원본 → 세트, 분석 파일 ----


def raw_fixture() -> dict:
    games, drafts, players = [], [], []
    names = {1: "Alpha", 2: "Bravo", 3: "Charlie"}
    for s in season(30):
        blue, red = names[s.blue.id], names[s.red.id]
        row = {
            "GameId": s.game_id, "MatchId": f"m{s.match_id}", "N": "1", "Team1": blue, "Team2": red,
            "WinTeam": names[s.winner_id], "Len": "30.5", "Start": s.start[:19].replace("T", " "), "Patch": "26.1",
            "Rpg": s.rpg, "VOD": "", "Team1Kills": "10", "Team2Kills": "7", "Team1Dragons": "3", "Team2Dragons": "1",
        }
        games.append(row)
        d = {"GameId": s.game_id, "MatchId": row["MatchId"], "N": "1", "Team1": blue, "Team2": red}
        for col, team in (("Team1", s.blue), ("Team2", s.red)):
            for i, c in enumerate(s.champions(team.id, "ban"), 1):
                d[f"{col}Ban{i}"] = c
            for i, c in enumerate(s.champions(team.id, "pick"), 1):
                d[f"{col}Pick{i}"] = c
                d[f"{col}Role{i}"] = ["Top", "Jungle", "Mid", "Bot", "Support"][i - 1]
        drafts.append(d)
        for p in s.players:
            players.append({
                "GameId": s.game_id, "Link": f"{p.player} (선수)", "Team": names[p.team_id], "Champion": p.champion,
                "Role": ["Top", "Jungle", "Mid", "Bot", "Support"][ROLES.index(p.role)], "RoleN": str(ROLES.index(p.role) + 1),
                "Side": "1" if p.team_id == s.blue.id else "2", "Kills": str(p.kills), "Deaths": "1", "Assists": "2",
                "CS": "200", "Gold": "10000", "Dmg": "15000", "Vision": "30",
            })
    teams = [{"Name": n, "Short": n[:3].upper()} for n in names.values()]
    return {"leagues": {"LCK": {"matches": [], "games": games, "teams": teams, "drafts": drafts, "players": players, "vods": []}}}


def test_build_sets_from_raw():
    sets = build_sets(raw_fixture())
    assert len(sets) == 30
    s = sets[0]
    assert len(s.draft) == 20 and s.first_pick_id == s.blue.id
    assert s.draft[6].kind == "pick" and s.draft[6].role == "탑"
    assert s.blue_stats.kills == 10 and s.red_stats.dragons == 1 and s.length_min == 30.5
    assert len(s.players) == 10 and s.players[0].player.endswith("탑") and s.players[0].role == "탑"
    assert s.winner_id in (s.blue.id, s.red.id)


def test_analysis_build_writes_files(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "leaguepedia-2026.json").write_text(json.dumps(raw_fixture()), encoding="utf-8")
    sets = build_sets(raw_fixture())
    (tmp_path / "raw" / "timelines-2026.json").write_text(json.dumps({sets[-1].rpg: TIMELINE, sets[0].rpg: None}), encoding="utf-8")

    assert analysis.build(tmp_path) is True
    assert analysis.build(tmp_path) is False  # 같은 입력이면 파일을 다시 쓰지 않는다

    models = json.loads((tmp_path / "models.json").read_text(encoding="utf-8"))
    assert models["counts"] == {"sets": 30, "drafted": 30, "timelines": 1, "timelines_verified": 0, "series": 30, "clip_sets": 0}
    assert models["draft"]["holdout"]["pick_recall_10"] > models["draft"]["baseline_meta_only"]["pick_recall_10"] - 1e-9
    assert len(models["draft"]["rank_hit"]["pick"]) == 10

    listing = json.loads((tmp_path / "draft.json").read_text(encoding="utf-8"))
    assert len(listing["recent"]) == 30 and listing["recent"][0]["has_mock"]

    last = json.loads((tmp_path / "sets" / f"{sets[-1].match_id}.json").read_text(encoding="utf-8"))
    one = last["sets"][0]
    assert len(one["draft"]) == 20 and one["summary"]["has_timeline"] and one["summary"]["fight_count"]["total"] == 3
    assert len(one["matchups"]) == 5 and len(one["forecast"]) == 2
    assert len(last["mock"]["moves"]) == 20
    forecast = next(iter(one["forecast"].values()))
    assert forecast["pick_hits"] == 5 and all("p" in row for row in forecast["picks"])

    facts = analysis.extra_facts(sets, {sets[-1].rpg: TIMELINE})
    assert "교전 3회" in facts[sets[-1].match_id][0]


# ---- 챔피언 이름표 ----


def test_champion_table():
    from pipeline import champions

    english = {"data": {"MonkeyKing": {"name": "Wukong"}, "KSante": {"name": "K'Sante"}, "Nunu": {"name": "Nunu & Willump"}}}
    korean = {"data": {"MonkeyKing": {"name": "오공"}, "KSante": {"name": "크산테"}, "Nunu": {"name": "누누와 윌럼프"}}}
    pages = {"versions.json": ["26.22.1", "26.21.1"], "en_US/champion.json": english, "ko_KR/champion.json": korean}
    table = champions.fetch(lambda url: next(v for k, v in pages.items() if url.endswith(k)))
    assert table["version"] == "26.22.1"
    c = table["champions"]
    assert c["wukong"]["ko"] == "오공" and c["monkeyking"]["id"] == "MonkeyKing"
    assert c[champions.key("K'Sante")]["ko"] == "크산테"
    assert c["nunu"]["ko"] == "누누와 윌럼프" and c["nunuwillump"]["en"] == "Nunu & Willump"


# ---- 자동 수집, 영상 목록, 영상 위치 ----


def fake_youtube(path, params):
    if path == "channels":
        assert params["forHandle"] == "@LCK"
        return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
    if path == "playlistItems":
        return {"items": [{"contentDetails": {"videoId": v}} for v in ("v1", "v2")]}
    assert path == "videos"
    items = []
    for v in params["id"].split(","):
        item = {"id": v, "snippet": {"title": f"영상 {v}", "publishedAt": "2026-01-10T12:00:00Z", "description": ""}, "contentDetails": {"duration": "PT5H"}}
        if v == "v1":
            item["liveStreamingDetails"] = {"actualStartTime": "2026-01-10T07:30:00Z", "actualEndTime": "2026-01-10T13:00:00Z"}
        items.append(item)
    return {"items": items}


def test_youtube_collect_and_clip_links(tmp_path, monkeypatch):
    from pipeline import highlights, youtube

    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert youtube.collect(tmp_path, 2026, fake_youtube).startswith("건너뜀")
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    assert youtube.collect(tmp_path, 2026, fake_youtube) == "영상 2개 (새로 2개, 생중계 다시보기 1개)"
    assert youtube.collect(tmp_path, 2026, fake_youtube) == "영상 2개 (새로 0개, 생중계 다시보기 1개)"
    videos = youtube.load_videos(tmp_path)

    # 경기는 방송 시작 45분 뒤(08:15 UTC)에 시작했고, 30분짜리였다.
    start = int(datetime(2026, 1, 10, 8, 15, tzinfo=timezone.utc).timestamp())
    timeline = {"anchors": [[0, start], [1800, start + 1800]]}
    fights = [{"t": 200}, {"t": 900}]
    links = highlights.clip_links(timeline, fights, videos, shift=0)
    assert links[0] == f"https://www.youtube.com/watch?v=v1&t={45 * 60 + 200 - highlights.LEAD_SEC}s"
    assert highlights.clip_links(timeline, fights, videos, shift=30)[1].endswith(f"t={45 * 60 + 900 + 30 - highlights.LEAD_SEC}s")
    # 일시정지로 실제 시각이 많이 밀렸으면 만들지 않는다. 기준점이 없어도 마찬가지다.
    paused = {"anchors": [[0, start], [1800, start + 2400]]}
    assert highlights.clip_links(paused, fights, videos, shift=0) == [None, None]
    assert highlights.clip_links({}, fights, videos, shift=0) == [None, None]
    assert not highlights.enabled()


def test_collect_registry_records_each_source(tmp_path, monkeypatch):
    from pipeline import collect

    monkeypatch.delenv("SOME_KEY", raising=False)

    def boom(data_dir, year):
        raise RuntimeError("서버 오류")

    def later(data_dir, year):
        raise NotImplementedError("나중에")

    sources = [
        collect.Source("ok", "잘 되는 것", (), lambda d, y: f"{y}년 3건"),
        collect.Source("keyed", "키가 필요한 것", ("SOME_KEY",), lambda d, y: "안 불려야 함"),
        collect.Source("bad", "실패하는 것", (), boom),
        collect.Source("todo", "준비 중인 것", (), later),
    ]
    status = collect.run(tmp_path, 2026, sources=sources)
    assert [status[k]["state"] for k in ("ok", "keyed", "bad", "todo")] == ["수집됨", "키 없음", "실패", "준비 중"]
    assert status["ok"]["note"] == "2026년 3건" and "SOME_KEY" in status["keyed"]["note"]
    saved = json.loads((tmp_path / "collect.json").read_text(encoding="utf-8"))
    assert saved["bad"]["note"] == "서버 오류"
    assert [s.name for s in collect.SOURCES] == ["leaguepedia", "champions", "youtube", "grid"]


def test_timeline_keeps_real_time_anchors():
    from pipeline.leaguepedia import compact_timeline, fetch_timelines

    doc = {"info": {"frames": [
        {"events": [{"type": "PAUSE_END", "timestamp": 0, "realTimestamp": 1767000000000}], "participantFrames": {}},
        {"events": [{"type": "GAME_END", "timestamp": 1800000, "realTimestamp": 1767001800000}]},
    ]}}
    assert compact_timeline(doc)["anchors"] == [[0, 1767000000], [1800, 1767001800]]

    class Pages:
        def __init__(self):
            self.asked = []

        def page_content(self, title):
            self.asked.append(title)
            return json.dumps(doc)

    raw = {"leagues": {"LCK": {"games": [{"Rpg": "A", "Start": "2026-01-02"}, {"Rpg": "B", "Start": "2026-01-01"}, {"Rpg": "C", "Start": "2026-01-03"}]}}}
    pages = Pages()
    # A 는 예전 형식(기준점 없음), B 는 없음, C 는 이미 새 형식 → 없는 B 를 먼저, 그다음 A 를 다시 받는다.
    out = fetch_timelines(raw, {"A": {"kills": []}, "C": {"kills": [], "anchors": []}}, pages, limit=5)
    assert pages.asked == ["V5 data:B/Timeline", "V5 data:A/Timeline"]
    assert out["A"]["anchors"] and out["B"]["anchors"]
