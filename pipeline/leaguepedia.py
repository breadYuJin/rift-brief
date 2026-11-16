"""Leaguepedia(lol.fandom.com) 공개 Cargo API 에서 한 해의 경기 기록을 받아 저장한다.

    python -m pipeline.leaguepedia --year 2026

결과는 data/archive/<year>.json 에 쌓이고, PANDASCORE_TOKEN 이 없을 때 파이프라인이 이 파일을 읽는다.
Leaguepedia 의 내용은 CC BY-SA 라이선스이므로 사이트에 출처를 표기한다.
요청은 한 번에 500행까지, 요청 사이에 몇 초씩 쉬어 서버에 부담을 주지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import requests

from .config import ROOT
from .schemas import Game, LeagueFeed, Match, Team

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

# OverviewPage 뒷부분이나 탭 이름에 들어 있는 말 → 화면에 쓸 스테이지 이름. 위에서부터 먼저 맞는 것을 쓴다.
STAGE_WORDS = [
    ("road to msi", "MSI 대표 선발전"),
    ("rounds 1-2", "정규 시즌 1~2라운드"),
    ("rounds 3-4", "정규 시즌 3~4라운드"),
    ("rounds 3-5", "정규 시즌 3~5라운드"),
    ("play-in", "플레이-인"),
    ("playoffs", "플레이오프"),
    ("cup", "LCK컵"),
    ("swiss", "스위스 스테이지"),
    ("knockout", "토너먼트"),
    ("bracket", "브래킷 스테이지"),
]
KNOCKOUT_TABS = ("quarter", "semi", "final")

# LCK 팀의 한국어 표기. 약칭이 일치할 때만 쓴다.
KOREAN_NAMES = {
    "HLE": "한화생명e스포츠",
    "GEN": "젠지",
    "T1": "T1",
    "KT": "KT 롤스터",
    "DK": "디플러스 기아",
    "NS": "농심 레드포스",
    "BFX": "BNK 피어엑스",
    "BRO": "한진 브리온",
    "DRX": "키움 DRX",
    "DNS": "DN 수퍼스",
}


def stable_id(text: str) -> int:
    """Leaguepedia 에는 숫자 ID 가 없어 이름으로 고정 ID 를 만든다."""
    return zlib.crc32(text.encode("utf-8"))


def stage_name(league: str, prefix: str, page: str, tab: str) -> str:
    rest = page[len(prefix) :].strip("/ ").lower()
    # "Season/Cup" 처럼 시즌 표기가 앞에 붙는 경우가 있어 뒷부분 전체에서 찾는다.
    for word, name in STAGE_WORDS:
        if word in rest:
            return name
    tab_l = tab.lower()
    if league == "월즈" or league == "MSI" or league == "퍼스트 스탠드":
        if any(w in tab_l for w in KNOCKOUT_TABS):
            return "토너먼트"
        for word, name in STAGE_WORDS:
            if word in tab_l:
                return name
        if league == "월즈" and ("round" in tab_l or "day" in tab_l):
            return "스위스 스테이지"
    return "본선" if league != "LCK" else (rest.split("/")[-1].title() or "정규 시즌")


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_match(
    row: dict[str, Any],
    league: str,
    league_id: int,
    prefix: str,
    year: int,
    shorts: dict[str, str],
    games: list[dict[str, Any]],
) -> Match | None:
    """MatchSchedule 한 행을 Match 로 바꾼다. 팀이 정해지지 않은 행은 버린다."""
    name_a, name_b = (row.get("Team1") or "").strip(), (row.get("Team2") or "").strip()
    if not name_a or not name_b or "TBD" in (name_a.upper(), name_b.upper()):
        return None

    def team(name: str) -> Team:
        short = shorts.get(name) or "".join(w[0] for w in name.split()[:3]).upper() or name[:3].upper()
        return Team(id=stable_id(name), name=KOREAN_NAMES.get(short, name) if league == "LCK" else name, acronym=short)

    a, b = team(name_a), team(name_b)
    winner = {"1": a.id, "2": b.id}.get(str(row.get("Winner") or "").strip())
    begin = _iso(row.get("Date"))
    tab = (row.get("Tab") or "").strip()
    stage = stage_name(league, prefix, row.get("OverviewPage") or "", tab)
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
        id=stable_id(row.get("MatchId") or f"{row.get('OverviewPage')}|{tab}|{name_a}|{name_b}|{begin}"),
        league=league,
        league_id=league_id,
        serie_id=year,
        tournament=stage,
        stage=" ".join(p for p in (str(year), stage, tab) if p),
        best_of=_int(row.get("BestOf")) or max(1, 2 * max(score_a, score_b) - 1),
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


class Cargo:
    def __init__(self, session: requests.Session | None = None, pause: float = PAUSE_SEC):
        self._session = session or requests.Session()
        repo = os.getenv("GITHUB_REPOSITORY", "rift-brief")
        self._session.headers.update({"User-Agent": f"rift-brief-archive/1.0 (https://github.com/{repo})"})
        self._pause = pause
        self.requests_made = 0

    def _get(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        for attempt in range(5):
            self.requests_made += 1
            resp = self._session.get(API, params=params, timeout=40)
            try:
                data = resp.json()
            except ValueError:
                data = {}
            if resp.status_code == 200 and "cargoquery" in data:
                return [r.get("title", {}) for r in data["cargoquery"]]
            error = (data.get("error") or {}) if isinstance(data, dict) else {}
            code = error.get("code")
            if resp.status_code in (429, 500, 502, 503, 504) or code == "ratelimited":
                wait = 20 * (attempt + 1)
                print(f"[leaguepedia] 잠시 대기 {wait}초 (HTTP {resp.status_code}, {code})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Leaguepedia 요청 실패: HTTP {resp.status_code} {error or resp.text[:200]}")
        raise RuntimeError("Leaguepedia 요청이 계속 제한되고 있습니다. 나중에 다시 실행하세요.")

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


def collect(year: int, cargo: Cargo) -> dict[str, Any]:
    feeds: list[LeagueFeed] = []
    notes: list[str] = []
    stage_counts: Counter[str] = Counter()
    raw_pages: Counter[str] = Counter()

    for index, (league, pattern) in enumerate(LEAGUES, start=1):
        prefix = pattern.format(year=year)
        like = f'OverviewPage LIKE "{prefix}%"'
        rows = cargo.query(
            tables="MatchSchedule",
            fields="MatchId,OverviewPage,Tab,Team1,Team2,Team1Score,Team2Score,Winner,BestOf,DateTime_UTC=Date",
            where=like,
            order_by="DateTime_UTC",
        )
        print(f"[leaguepedia] {league}: 경기 {len(rows)}행")
        if not rows:
            notes.append(f"{league}: '{prefix}' 로 시작하는 경기 없음")
            continue

        games: dict[str, list[dict[str, Any]]] = {}
        try:
            for g in cargo.query(
                tables="ScoreboardGames",
                fields="MatchId,N_GameInMatch=N,WinTeam,Gamelength_Number=Len",
                where=like,
                order_by="DateTime_UTC",
            ):
                games.setdefault(g.get("MatchId") or "", []).append(g)
            print(f"[leaguepedia] {league}: 세트 기록 {sum(map(len, games.values()))}행")
        except RuntimeError as exc:
            notes.append(f"{league}: 세트 기록을 받지 못함 ({exc})")

        names = sorted({(r.get(k) or "").strip() for r in rows for k in ("Team1", "Team2")} - {""})
        shorts: dict[str, str] = {}
        try:
            quoted = ",".join('"' + n.replace('"', '\\"') + '"' for n in names)
            for t in cargo.query(tables="Teams", fields="Name,Short", where=f"Name IN ({quoted})", order_by="Name"):
                if t.get("Short"):
                    shorts[(t.get("Name") or "").strip()] = t["Short"].strip()
        except RuntimeError as exc:
            notes.append(f"{league}: 팀 약칭을 받지 못함 ({exc})")
        missing = [n for n in names if n not in shorts]
        if missing:
            notes.append(f"{league}: 약칭 없는 팀 {missing}")

        matches = []
        for r in rows:
            raw_pages[f"{r.get('OverviewPage')} | {r.get('Tab')}"] += 1
            m = to_match(r, league, index, prefix, year, shorts, games.get(r.get("MatchId") or "", []))
            if m:
                matches.append(m)
                stage_counts[f"{league} / {m.tournament}"] += 1
        feeds.append(LeagueFeed(id=index, name=league, serie=str(year), matches=matches))

    return {
        "year": year,
        "source": "Leaguepedia",
        "fetched_on": datetime.now(timezone.utc).date().isoformat(),
        "leagues": [f.model_dump() for f in feeds],
        "diagnostics": {
            "stages": dict(sorted(stage_counts.items())),
            "pages": dict(sorted(raw_pages.items())),
            "notes": notes,
            "requests": cargo.requests_made,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    args = parser.parse_args()

    archive = collect(args.year, Cargo())
    total = sum(len(l["matches"]) for l in archive["leagues"])
    for key, count in archive["diagnostics"]["pages"].items():
        print(f"[페이지] {count:4d}  {key}")
    for key, count in archive["diagnostics"]["stages"].items():
        print(f"[스테이지] {count:4d}  {key}")
    for note in archive["diagnostics"]["notes"]:
        print(f"[참고] {note}")
    if total == 0:
        print("[leaguepedia] 받은 경기가 없어 저장하지 않습니다.")
        return 1

    out = ROOT / "data" / "archive" / f"{args.year}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(archive, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[leaguepedia] {total}경기 저장: {out.relative_to(ROOT)} (요청 {archive['diagnostics']['requests']}회)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
