"""밴픽 예측 기능을 만들 수 있는지 확인하는 일회성 조사 스크립트.

Leaguepedia 에 (1) 순서가 있는 밴픽 기록이 있는지, (2) 2026 시즌 분량이 얼마나 되는지,
(3) 세트가 끝난 뒤 얼마 만에 기록이 올라오는지를 본다. 결과는 로그로만 남긴다.
"""
from __future__ import annotations

import json
import os
import time

import requests

API = "https://lol.fandom.com/api.php"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = f"rift-brief-probe/1.0 (https://github.com/{os.getenv('GITHUB_REPOSITORY', 'rift-brief')})"


def get(params: dict) -> dict:
    for attempt in range(5):
        resp = SESSION.get(API, params={**params, "format": "json"}, timeout=40)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        code = (data.get("error") or {}).get("code") if isinstance(data, dict) else None
        if resp.status_code == 200 and not code:
            time.sleep(4)
            return data
        if resp.status_code in (429, 500, 502, 503, 504) or code == "ratelimited":
            time.sleep(20 * (attempt + 1))
            continue
        time.sleep(4)
        return {"error": data.get("error") or resp.text[:200]}
    return {"error": "rate limited"}


def cargo(tables: str, fields: str, where: str, order_by: str = "", limit: int = 5) -> list[dict] | dict:
    data = get({"action": "cargoquery", "tables": tables, "fields": fields, "where": where, "order_by": order_by, "limit": limit})
    return [r["title"] for r in data["cargoquery"]] if "cargoquery" in data else data


def main() -> None:
    for table in ("PicksAndBansS7", "ScoreboardGames", "MatchScheduleGame", "ScoreboardPlayers"):
        data = get({"action": "cargofields", "table": table})
        fields = sorted((data.get("cargofields") or {}).keys())
        print(f"[스키마] {table}: {len(fields)}개 필드")
        print("   " + ", ".join(fields) if fields else f"   {data}")

    for name, prefix in (("LCK", "LCK/2026"), ("FST", "2026 First Stand"), ("MSI", "2026 Mid-Season Invitational"), ("Worlds", "2026 Season World Championship")):
        like = f'OverviewPage LIKE "{prefix}%"'
        pb = cargo("PicksAndBansS7", "COUNT(*)=N", like)
        sg = cargo("ScoreboardGames", "COUNT(*)=N", like)
        sp = cargo("ScoreboardPlayers", "COUNT(*)=N", like)
        print(f"[분량] {name}: 밴픽 {pb} / 세트 {sg} / 선수 기록 {sp}")

    final = 'OverviewPage LIKE "LCK/2026 Season/Season Playoffs%"'
    rows = cargo(
        "PicksAndBansS7",
        "_pageName=Page,Team1,Team2,Winner,Team1Ban1,Team2Ban1,Team1Ban2,Team2Ban2,Team1Ban3,Team2Ban3,"
        "Team1Pick1,Team2Pick1,Team2Pick2,Team1Pick2,Team1Pick3,Team2Pick3,Team2Ban4,Team1Ban4,Team2Ban5,Team1Ban5,"
        "Team2Pick4,Team1Pick4,Team1Pick5,Team2Pick5,GameId,MatchId,N_GameInMatch=N",
        final,
        order_by="GameId DESC",
        limit=4,
    )
    print("[밴픽 예시] LCK 플레이오프 마지막 세트들")
    print(json.dumps(rows, ensure_ascii=False, indent=1)[:3500])

    games = cargo(
        "ScoreboardGames",
        "_pageName=Page,GameId,MatchId,DateTime_UTC=Start,Gamelength,Team1,Team2,WinTeam,Team1Picks,Team2Picks,Team1Bans,Team2Bans,VOD,Team1Dragons,Team1Barons,Team1Kills,Team2Kills",
        final,
        order_by="DateTime_UTC DESC",
        limit=4,
    )
    print("[세트 예시]")
    print(json.dumps(games, ensure_ascii=False, indent=1)[:3000])

    msg = cargo("MatchScheduleGame", "MatchId,N_GameInMatch=N,Vod,VodGameStart,VodHighlights,MVP", "MatchId LIKE \"LCK/2026 Season/Season Playoffs%\"", order_by="MatchId DESC", limit=4)
    print("[영상·MVP 예시]")
    print(json.dumps(msg, ensure_ascii=False, indent=1)[:2000])

    # 기록이 올라온 시점: 밴픽과 세트 기록이 저장된 문서의 편집 이력을 결승 당일로 좁혀 본다.
    pages = set()
    for group in (rows, games):
        if isinstance(group, list):
            pages |= {r.get("Page") for r in group if r.get("Page")}
    for page in sorted(pages):
        data = get({
            "action": "query", "prop": "revisions", "titles": page, "rvlimit": 50,
            "rvprop": "timestamp|size", "rvstart": "2026-09-13T15:00:00Z", "rvend": "2026-09-13T03:00:00Z",
        })
        revs = [rev for p in (data.get("query", {}).get("pages", {}) or {}).values() for rev in p.get("revisions", [])]
        print(f"[편집 이력] {page}: 결승 당일(UTC 03~15시) 편집 {len(revs)}회")
        for rev in reversed(revs):
            print(f"   {rev.get('timestamp')}  크기 {rev.get('size')}")


if __name__ == "__main__":
    main()
