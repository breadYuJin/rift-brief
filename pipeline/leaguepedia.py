"""Leaguepedia(lol.fandom.com) 공개 Cargo API 에서 한 해의 경기 기록을 받아 저장한다.

    python -m pipeline.leaguepedia --year 2026            # 받아 와서 정리
    python -m pipeline.leaguepedia --year 2026 --offline  # 받아 둔 원본으로 다시 정리만

원본 행은 data/raw/leaguepedia-<year>.json 에, 정리한 결과는 data/archive/<year>.json 에 둔다.
PANDASCORE_TOKEN 이 없을 때 파이프라인이 archive 파일을 읽는다.
Leaguepedia 의 내용은 CC BY-SA 라이선스이므로 사이트에 출처를 표기한다.
요청은 한 번에 500행까지, 요청 사이에 몇 초씩 쉬어 서버에 부담을 주지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import zlib
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import requests

from .config import ROOT
from .schemas import CombinedTable, Game, LeagueFeed, Match, Team

API = "https://lol.fandom.com/api.php"
PAGE_SIZE = 500
PAUSE_SEC = 4

# (표시 이름, OverviewPage 접두어). {year} 는 연도로 바뀐다.
LEAGUES = [
    ("LCK", "LCK/{year}"),
    ("퍼스트 스탠드", "{year} First Stand"),
    ("MSI", "{year} Mid-Season Invitational"),
    ("월즈", "{year} Season World Championship"),
]

# 이벤트성 경기는 기록에서 뺀다.
SKIP_PAGE_WORDS = ("showmatch",)

# 시즌 중 이름이 바뀐 팀을 하나로 묶는다(옛 표기 → 약칭).
SHORT_OVERRIDES = {"BRION": "BRO", "DRX": "KRX"}

# LCK 팀의 한국어 표기(약칭 기준). 국제 대회에서도 같은 이름으로 보여 준다.
KOREAN_NAMES = {
    "HLE": "한화생명e스포츠",
    "GEN": "젠지",
    "T1": "T1",
    "KT": "KT 롤스터",
    "DK": "디플러스 기아",
    "NS": "농심 레드포스",
    "BFX": "BNK 피어엑스",
    "BRO": "한진 브리온",
    "KRX": "키움 DRX",
    "DNS": "DN 수퍼스",
}

_SIDES = ("Team1", "Team2")
GAME_FIELDS = (
    "GameId,MatchId,N_GameInMatch=N,WinTeam,Gamelength_Number=Len,RiotPlatformGameId=Rpg,DateTime_UTC=Start,Patch,"
    "Team1,Team2,VOD,"
    + ",".join(
        f"{t}{f}"
        for t in _SIDES
        for f in (
            "Picks",
            "Bans",
            "Kills",
            "Gold",
            "Dragons",
            "Barons",
            "Towers",
            "RiftHeralds",
            "VoidGrubs",
            "Atakhans",
            "Inhibitors",
        )
    )
)
# PicksAndBansS7 의 Team1 은 먼저 밴픽하는 팀이다(진영과는 별개).
DRAFT_FIELDS = "GameId,MatchId,N_GameInMatch=N,Team1,Team2,Winner," + ",".join(
    f"{t}{kind}{i}" for kind in ("Ban", "Pick", "Role") for t in _SIDES for i in range(1, 6)
)
PLAYER_FIELDS = (
    "GameId,Link,Team,Champion,Role,Role_Number=RoleN,Side,Kills,Deaths,Assists,CS,Gold,"
    "DamageToChampions=Dmg,VisionScore=Vision"
)
VOD_FIELDS = "GameId,MatchId,N_GameInMatch=N,Blue,Red,FirstPick,Selection,VodGameStart,VodPB,MVP"

REGULAR_1 = "정규 시즌 1~2라운드"
REGULAR_2 = "정규 시즌 3~4라운드"


def stable_id(text: str) -> int:
    """Leaguepedia 에는 숫자 ID 가 없어 이름으로 고정 ID 를 만든다."""
    return zlib.crc32(text.encode("utf-8"))


def stage_name(league: str, prefix: str, page: str, tab: str) -> str:
    """OverviewPage 뒷부분과 탭 이름으로 화면에 쓸 스테이지 이름을 정한다."""
    rest = page[len(prefix) :].strip("/ ").lower()
    tab_l = tab.lower()
    final_round = any(w in tab_l for w in ("quarter", "semi", "final"))

    if league == "LCK":
        if "cup" in rest:
            if tab_l.startswith("week"):
                return "LCK컵 그룹 대항전"
            return "LCK컵 플레이-인" if "play-in" in tab_l else "LCK컵 플레이오프"
        if "road to msi" in rest:
            return "MSI 대표 선발전"
        if "rounds 1-2" in rest:
            return REGULAR_1
        if "rounds 3" in rest:
            return REGULAR_2
        if "play-in" in rest:
            return "플레이-인"
        if "playoffs" in rest:
            return "플레이오프"
        return rest.split("/")[-1].title() or "정규 시즌"

    if "play-in" in rest or "play-in" in tab_l:
        return "플레이-인"
    if league == "MSI":
        return "브래킷 스테이지"
    if league == "월즈":
        return "토너먼트" if final_round else "스위스 스테이지"
    if "group" in tab_l:
        return "그룹 스테이지"
    return "토너먼트" if final_round else "본선"


def round_label(tab: str) -> str:
    """탭 이름을 화면에 쓸 라운드 이름으로 바꾼다."""
    t = tab.lower()
    if "quarter" in t:
        return "8강"
    if "semi" in t:
        return "4강"
    if "final" in t:
        return "결승"
    for word, unit in (("round", "라운드"), ("day", "일차"), ("week", "주차")):
        found = re.search(rf"{word}\s*(\d+)", t)
        if found:
            return f"{found.group(1)}{unit}"
    return tab


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).isoformat()
    except ValueError:
        return None


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def resolve_team(name: str, shorts: dict[str, str]) -> Team:
    """표기가 달라도 같은 팀이면 같은 ID 가 나오도록 약칭을 기준으로 삼는다."""
    clean = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip() or name
    short = SHORT_OVERRIDES.get(clean) or shorts.get(name) or shorts.get(clean)
    if not short:
        short = (
            clean.upper() if " " not in clean and len(clean) <= 5 else "".join(w[0] for w in clean.split()[:3]).upper()
        )
    return Team(id=stable_id(short), name=KOREAN_NAMES.get(short, clean), acronym=short)


def official_player(value: Any) -> str | None:
    """주최 측 선정 선수 칸을 선수 이름으로 정리한다. 'Zeka (Kim Geon-woo)' → 'Zeka', 'N/A'·빈칸 → None."""
    name = str(value or "").split(" (")[0].strip()
    return name if name and name.upper() not in ("N/A", "NA", "TBD", "-") else None


def to_match(
    row: dict[str, Any],
    league: str,
    league_id: int,
    prefix: str,
    year: int,
    shorts: dict[str, str],
    games: list[dict[str, Any]],
) -> Match | None:
    """MatchSchedule 한 행을 Match 로 바꾼다. 팀이 정해지지 않은 행과 이벤트 경기는 버린다."""
    page = row.get("OverviewPage") or ""
    if any(w in page.lower() for w in SKIP_PAGE_WORDS):
        return None
    name_a, name_b = (row.get("Team1") or "").strip(), (row.get("Team2") or "").strip()
    if not name_a or not name_b or "TBD" in (name_a.upper(), name_b.upper()):
        return None

    a, b = resolve_team(name_a, shorts), resolve_team(name_b, shorts)
    winner = {"1": a.id, "2": b.id}.get(str(row.get("Winner") or "").strip())
    begin = _iso(row.get("Date"))
    tab = (row.get("Tab") or "").strip()
    stage = stage_name(league, prefix, page, tab)
    by_name = {name_a: a.id, name_b: b.id}
    game_list = [
        Game(
            position=_int(g.get("N")) or i + 1,
            winner_id=by_name.get((g.get("WinTeam") or "").strip()),
            length_min=round(float(g["Len"])) if g.get("Len") else None,
        )
        for i, g in enumerate(sorted(games, key=lambda g: _int(g.get("N"))))
    ]
    score_a, score_b = _int(row.get("Team1Score")), _int(row.get("Team2Score"))
    return Match(
        id=stable_id(row.get("MatchId") or f"{page}|{tab}|{name_a}|{name_b}|{begin}"),
        league=league,
        league_id=league_id,
        serie_id=year,
        tournament=stage,
        round=round_label(tab),
        stage=" ".join(p for p in (str(year), stage, tab) if p),
        best_of=_int(row.get("BestOf")) or max(1, 2 * max(score_a, score_b) - 1),
        mvp=official_player(row.get("MVP")),
        status="finished" if winner else "not_started",
        begin_at=begin,
        end_at=begin if winner else None,
        team_a=a,
        team_b=b,
        score_a=score_a,
        score_b=score_b,
        winner_id=winner,
        # 세트 기록이 스코어와 맞지 않으면(일부 누락 등) 쓰지 않는다.
        games=game_list if len(game_list) == score_a + score_b and all(g.winner_id for g in game_list) else [],
    )


def split_lck_groups(matches: list[Match]) -> list[CombinedTable]:
    """3~4라운드를 레전드·라이즈 그룹으로 나누고, 정규 시즌 누적 순위표 정의를 돌려준다.

    3~4라운드는 같은 그룹끼리만 만나므로, 맞붙은 팀끼리 이으면 두 묶음이 나온다.
    1~2라운드 승수가 더 많은 묶음이 레전드 그룹이다.
    """
    second = [m for m in matches if m.tournament == REGULAR_2]
    if not second:
        return []
    group_of: dict[int, int] = {}
    for m in second:
        ga, gb = group_of.get(m.team_a.id), group_of.get(m.team_b.id)
        if ga is None and gb is None:
            group_of[m.team_a.id] = group_of[m.team_b.id] = len(set(group_of.values()))
        elif ga is None or gb is None:
            group_of[m.team_a.id] = group_of[m.team_b.id] = ga if ga is not None else gb  # type: ignore[assignment]
        elif ga != gb:
            for team, g in list(group_of.items()):
                if g == gb:
                    group_of[team] = ga
    groups = sorted(set(group_of.values()))
    if len(groups) != 2:
        return []

    first_wins = Counter(m.winner_id for m in matches if m.tournament == REGULAR_1 and m.winner_id)
    strength = {g: sum(first_wins[t] for t, tg in group_of.items() if tg == g) for g in groups}
    legend = max(groups, key=lambda g: strength[g])
    names = {g: f"{REGULAR_2} {'레전드' if g == legend else '라이즈'} 그룹" for g in groups}
    for m in second:
        g = group_of[m.team_a.id]
        m.tournament = names[g]
        m.stage = m.stage.replace(REGULAR_2, names[g], 1)
    return [
        CombinedTable(
            name=f"정규 시즌 최종 {'레전드' if g == legend else '라이즈'} 그룹 (1~4라운드 누적)",
            stages=[REGULAR_1, names[g]],
            teams_from=names[g],
        )
        for g in sorted(groups, key=lambda g: g != legend)
    ]


class Cargo:
    def __init__(self, session: requests.Session | None = None, pause: float = PAUSE_SEC):
        self._session = session or requests.Session()
        repo = os.getenv("GITHUB_REPOSITORY", "rift-brief")
        self._session.headers.update({"User-Agent": f"rift-brief-archive/1.0 (https://github.com/{repo})"})
        self._pause = pause
        self.requests_made = 0

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(5):
            self.requests_made += 1
            resp = self._session.get(API, params=params, timeout=60)
            try:
                data = resp.json()
            except ValueError:
                data = {}
            error = (data.get("error") or {}) if isinstance(data, dict) else {}
            code = error.get("code")
            if resp.status_code == 200 and not error:
                return data
            if resp.status_code in (429, 500, 502, 503, 504) or code == "ratelimited":
                wait = 20 * (attempt + 1)
                print(f"[leaguepedia] 잠시 대기 {wait}초 (HTTP {resp.status_code}, {code})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Leaguepedia 요청 실패: HTTP {resp.status_code} {error or resp.text[:200]}")
        raise RuntimeError("Leaguepedia 요청이 계속 제한되고 있습니다. 나중에 다시 실행하세요.")

    def _get(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        data = self._request(params)
        if "cargoquery" not in data:
            raise RuntimeError(f"Leaguepedia 응답에 결과가 없습니다: {str(data)[:200]}")
        return [r.get("title", {}) for r in data["cargoquery"]]

    def page_content(self, title: str) -> str | None:
        """위키 문서의 본문. 문서가 없으면 None."""
        data = self._request(
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "prop": "revisions",
                "titles": title,
                "rvprop": "content",
                "rvslots": "main",
            }
        )
        time.sleep(self._pause)
        pages = (data.get("query") or {}).get("pages") or []
        if not pages or pages[0].get("missing") or not pages[0].get("revisions"):
            return None
        return pages[0]["revisions"][0]["slots"]["main"]["content"]

    def image_urls(self, files: list[str], width: int = 160) -> dict[str, str]:
        """위키에 올라온 그림 파일 이름 → 주소(가로 width 로 줄인 것)."""
        out: dict[str, str] = {}
        for start in range(0, len(files), 40):
            batch = files[start : start + 40]
            data = self._request(
                {
                    "action": "query",
                    "format": "json",
                    "formatversion": 2,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": width,
                    "titles": "|".join(f"File:{f}" for f in batch),
                }
            )
            time.sleep(self._pause)
            query = data.get("query") or {}
            asked = {n["to"]: n["from"] for n in query.get("normalized") or []}
            for page in query.get("pages") or []:
                info = (page.get("imageinfo") or [{}])[0]
                url = info.get("thumburl") or info.get("url")
                if url:
                    title = asked.get(page["title"], page["title"])
                    out[title.removeprefix("File:")] = url
        return out

    def query(self, *, tables: str, fields: str, where: str, order_by: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while True:
            page = self._get(
                {
                    "action": "cargoquery",
                    "format": "json",
                    "tables": tables,
                    "fields": fields,
                    "where": where,
                    "order_by": order_by,
                    "limit": PAGE_SIZE,
                    "offset": len(rows),
                }
            )
            rows += page
            time.sleep(self._pause)
            if len(page) < PAGE_SIZE:
                return rows


def fetch_raw(year: int, cargo: Any) -> dict[str, Any]:
    """리그별 경기·세트·팀 행을 API 에서 받은 그대로 모은다."""
    leagues: dict[str, Any] = {}
    notes: list[str] = []
    for league, pattern in LEAGUES:
        prefix = pattern.format(year=year)
        like = f'OverviewPage LIKE "{prefix}%"'
        rows = cargo.query(
            tables="MatchSchedule",
            fields="MatchId,OverviewPage,Tab,Team1,Team2,Team1Score,Team2Score,Winner,BestOf,MVP,DateTime_UTC=Date",
            where=like,
            order_by="DateTime_UTC",
        )
        print(f"[leaguepedia] {league}: 경기 {len(rows)}행")
        games: list[dict[str, Any]] = []
        teams: list[dict[str, Any]] = []
        if rows:
            try:
                games = cargo.query(tables="ScoreboardGames", fields=GAME_FIELDS, where=like, order_by="DateTime_UTC")
                print(f"[leaguepedia] {league}: 세트 기록 {len(games)}행")
            except RuntimeError as exc:
                notes.append(f"{league}: 세트 기록을 받지 못함 ({exc})")
            names = sorted({(r.get(k) or "").strip() for r in rows for k in ("Team1", "Team2")} - {""})
            try:
                quoted = ",".join('"' + n.replace('"', '\\"') + '"' for n in names)
                teams = cargo.query(tables="Teams", fields="Name,Short", where=f"Name IN ({quoted})", order_by="Name")
            except RuntimeError as exc:
                notes.append(f"{league}: 팀 약칭을 받지 못함 ({exc})")
        extra: dict[str, list[dict[str, Any]]] = {"drafts": [], "players": [], "vods": []}
        if rows:
            for key, table, fields, order in (
                ("drafts", "PicksAndBansS7", DRAFT_FIELDS, "GameId"),
                ("players", "ScoreboardPlayers", PLAYER_FIELDS, "GameId"),
                ("vods", "MatchScheduleGame", VOD_FIELDS, "GameId"),
            ):
                try:
                    extra[key] = cargo.query(tables=table, fields=fields, where=like, order_by=order)
                    print(f"[leaguepedia] {league}: {table} {len(extra[key])}행")
                except RuntimeError as exc:
                    notes.append(f"{league}: {table} 을 받지 못함 ({exc})")
        leagues[league] = {"matches": rows, "games": games, "teams": teams, **extra}
    return {
        "year": year,
        "source": "Leaguepedia",
        "fetched_on": datetime.now(UTC).date().isoformat(),
        "leagues": leagues,
        "notes": notes,
        "requests": getattr(cargo, "requests_made", 0),
    }


def compact_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    """경기 타임라인(약 1MB)에서 분석에 쓰는 것만 남긴다: 킬, 오브젝트, 건물, 분당 골드와 위치.

    참가자 번호 1~5 는 블루 진영, 6~10 은 레드 진영이다.
    """
    frames = timeline.get("frames") or (timeline.get("info") or {}).get("frames") or []
    kills: list[list[Any]] = []
    monsters: list[list[Any]] = []
    buildings: list[list[Any]] = []
    gold: list[list[int]] = []
    positions: list[list[list[int]]] = []
    anchors: list[list[int]] = []
    for frame in frames:
        for e in frame.get("events") or []:
            t = int(e.get("timestamp") or 0) // 1000
            kind = e.get("type")
            if e.get("realTimestamp"):
                # 실제 시각이 찍힌 이벤트(경기 시작·종료 등). 경기 내 시각을 방송 영상 위치로 옮길 때 기준점으로 쓴다.
                anchors.append([t, int(e["realTimestamp"]) // 1000])
            if kind == "CHAMPION_KILL":
                pos = e.get("position") or {}
                kills.append(
                    [
                        t,
                        e.get("killerId") or 0,
                        e.get("victimId") or 0,
                        e.get("assistingParticipantIds") or [],
                        pos.get("x"),
                        pos.get("y"),
                    ]
                )
            elif kind == "ELITE_MONSTER_KILL":
                team = e.get("killerTeamId") or (100 if 1 <= (e.get("killerId") or 0) <= 5 else 200)
                monsters.append([t, e.get("monsterType") or "", e.get("monsterSubType") or "", team])
            elif kind == "BUILDING_KILL":
                # teamId 는 건물을 잃은 쪽이다.
                buildings.append(
                    [t, e.get("buildingType") or "", e.get("towerType") or "", e.get("laneType") or "", e.get("teamId")]
                )
        players = frame.get("participantFrames") or {}
        if players:
            each = [players.get(str(i)) or {} for i in range(1, 11)]
            gold.append(
                [
                    sum(int(p.get("totalGold") or 0) for p in each[:5]),
                    sum(int(p.get("totalGold") or 0) for p in each[5:]),
                ]
            )
            positions.append(
                [
                    [int((p.get("position") or {}).get("x") or 0), int((p.get("position") or {}).get("y") or 0)]
                    for p in each
                ]
            )
    return {
        "kills": kills,
        "monsters": monsters,
        "buildings": buildings,
        "gold": gold,
        "pos": positions,
        "anchors": anchors,
    }


def fetch_timelines(raw: dict[str, Any], existing: dict[str, Any], cargo: Any, limit: int) -> dict[str, Any]:
    """아직 없는 세트의 타임라인을 최근 세트부터 limit 개까지 받아 압축해 더한다."""
    games = [g for league in raw["leagues"].values() for g in league.get("games") or [] if g.get("Rpg")]
    games.sort(key=lambda g: g.get("Start") or "", reverse=True)
    # 없는 세트를 먼저 받고, 남는 몫으로 예전 형식(실제 시각 기준점이 없는 것)을 새로 받는다.
    missing = [g for g in games if g["Rpg"] not in existing]
    outdated = [g for g in games if isinstance(existing.get(g["Rpg"]), dict) and "anchors" not in existing[g["Rpg"]]]
    todo = (missing + outdated)[:limit]
    print(
        f"[leaguepedia] 타임라인: 전체 {len(games)}세트 중 보유 {len(existing)}, "
        f"없는 것 {len(missing)}, 다시 받을 것 {len(outdated)}, 이번에 받을 것 {len(todo)}"
    )
    added = 0
    for g in todo:
        try:
            body = cargo.page_content(f"V5 data:{g['Rpg']}/Timeline")
            if body is None:
                existing[g["Rpg"]] = None  # 문서가 없는 세트는 다시 찾지 않도록 표시한다.
                continue
            existing[g["Rpg"]] = compact_timeline(json.loads(body))
            added += 1
        except (RuntimeError, ValueError) as exc:
            print(f"[leaguepedia] 타임라인 중단: {exc}")
            break
    anchored = sum(1 for v in existing.values() if v and v.get("anchors"))
    print(f"[leaguepedia] 타임라인 {added}건 추가 (실제 시각 기준점이 있는 것 {anchored}건)")
    return existing


def build(raw: dict[str, Any]) -> dict[str, Any]:
    """받아 둔 원본 행을 사이트가 쓰는 형태로 정리한다. 네트워크를 쓰지 않는다."""
    year = raw["year"]
    feeds: list[LeagueFeed] = []
    notes: list[str] = list(raw.get("notes", []))
    stage_counts: Counter[str] = Counter()
    raw_pages: Counter[str] = Counter()

    for index, (league, pattern) in enumerate(LEAGUES, start=1):
        prefix = pattern.format(year=year)
        data = raw["leagues"].get(league) or {}
        rows = data.get("matches") or []
        if not rows:
            notes.append(f"{league}: '{prefix}' 로 시작하는 경기 없음")
            continue
        games: dict[str, list[dict[str, Any]]] = {}
        for g in data.get("games") or []:
            games.setdefault(g.get("MatchId") or "", []).append(g)
        shorts = {(t.get("Name") or "").strip(): t["Short"].strip() for t in data.get("teams") or [] if t.get("Short")}

        matches: list[Match] = []
        for r in rows:
            raw_pages[f"{r.get('OverviewPage')} | {r.get('Tab')}"] += 1
            m = to_match(r, league, index, prefix, year, shorts, games.get(r.get("MatchId") or "", []))
            if m:
                matches.append(m)
        tables = split_lck_groups(matches) if league == "LCK" else []
        for m in matches:
            stage_counts[f"{league} / {m.tournament}"] += 1
        feeds.append(LeagueFeed(id=index, name=league, serie=str(year), matches=matches, tables=tables))

    return {
        "year": year,
        "source": raw.get("source", "Leaguepedia"),
        "fetched_on": raw.get("fetched_on", ""),
        "leagues": [f.model_dump() for f in feeds],
        "diagnostics": {
            "stages": dict(sorted(stage_counts.items())),
            "pages": dict(sorted(raw_pages.items())),
            "notes": notes,
            "requests": raw.get("requests", 0),
        },
    }


def collect(year: int, cargo: Any) -> dict[str, Any]:
    return build(fetch_raw(year, cargo))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year)
    parser.add_argument("--offline", action="store_true", help="받아 둔 원본으로 다시 정리만 한다")
    parser.add_argument(
        "--timeline-limit",
        type=int,
        default=int(os.getenv("TIMELINE_LIMIT", "300")),
        help="한 번에 받을 타임라인 수 (0 이면 받지 않는다)",
    )
    args = parser.parse_args(argv)

    raw_path = ROOT / "data" / "raw" / f"leaguepedia-{args.year}.json"
    if args.offline:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        cargo = Cargo()
        raw = fetch_raw(args.year, cargo)
        if not any(league["matches"] for league in raw["leagues"].values()):
            print("[leaguepedia] 받은 경기가 없어 저장하지 않습니다.")
            return 1
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        if args.timeline_limit > 0:
            tl_path = raw_path.with_name(f"timelines-{args.year}.json")
            existing = json.loads(tl_path.read_text(encoding="utf-8")) if tl_path.exists() else {}
            timelines = fetch_timelines(raw, existing, cargo, args.timeline_limit)
            tl_path.write_text(
                json.dumps(timelines, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
            )

    archive = build(raw)
    total = sum(len(league["matches"]) for league in archive["leagues"])
    for key, count in archive["diagnostics"]["stages"].items():
        print(f"[스테이지] {count:4d}  {key}")
    for note in archive["diagnostics"]["notes"]:
        print(f"[참고] {note}")
    out = ROOT / "data" / "archive" / f"{args.year}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(archive, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[leaguepedia] {total}경기 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
