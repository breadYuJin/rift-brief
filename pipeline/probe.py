"""명장면 링크를 만들 수 있는지 확인하는 일회성 조사 스크립트.

Leaguepedia 가 경기 후 보관하는 타임라인 기록에 킬 시각이 있는지, 언제 올라오는지,
다시보기 영상의 세트 시작 시각과 합쳐 링크를 만들 수 있는지 본다. 결과는 로그로만 남긴다.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter

import requests

API = "https://lol.fandom.com/api.php"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = f"rift-brief-probe/1.0 (https://github.com/{os.getenv('GITHUB_REPOSITORY', 'rift-brief')})"


def get(params: dict) -> dict:
    for attempt in range(5):
        resp = SESSION.get(API, params={**params, "format": "json", "formatversion": 2}, timeout=60)
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


def cargo(tables: str, fields: str, where: str, order_by: str = "", limit: int = 10) -> list[dict]:
    data = get({"action": "cargoquery", "tables": tables, "fields": fields, "where": where, "order_by": order_by, "limit": limit})
    rows = data.get("cargoquery")
    if rows is None:
        print("   조회 실패:", data)
        return []
    return [r["title"] for r in rows]


def page(title: str) -> tuple[str | None, str | None, str | None]:
    """(본문, 최신 편집 시각, 최초 편집 시각)"""
    latest = get({"action": "query", "prop": "revisions", "titles": title, "rvprop": "content|timestamp", "rvslots": "main"})
    pages = (latest.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing"):
        return None, None, None
    rev = pages[0]["revisions"][0]
    first = get({"action": "query", "prop": "revisions", "titles": title, "rvprop": "timestamp", "rvlimit": 1, "rvdir": "newer"})
    first_ts = ((first.get("query") or {}).get("pages") or [{}])[0].get("revisions", [{}])[0].get("timestamp")
    return rev["slots"]["main"]["content"], rev["timestamp"], first_ts


def clock(ms: int) -> str:
    return f"{ms // 60000}:{ms // 1000 % 60:02d}"


def inspect(label: str, where: str) -> None:
    print(f"\n===== {label} =====")
    games = cargo(
        "ScoreboardGames",
        "GameId,RiotPlatformGameId=Rpg,DateTime_UTC=Start,Gamelength,Team1,Team2,WinTeam,Team1Kills,Team2Kills,VOD",
        where,
        order_by="DateTime_UTC DESC",
        limit=1,
    )
    if not games:
        return
    g = games[0]
    print(json.dumps(g, ensure_ascii=False))
    rpg = g.get("Rpg")
    if not rpg:
        print("   RiotPlatformGameId 없음")
        return
    body, latest, first = page(f"V5 data:{rpg}/Timeline")
    if body is None:
        print(f"   타임라인 문서 없음: V5 data:{rpg}/Timeline")
        return
    print(f"   타임라인 문서 크기 {len(body) // 1024}KB, 최초 등록 {first}, 최근 수정 {latest}")
    timeline = json.loads(body)
    frames = timeline.get("frames") or timeline.get("info", {}).get("frames") or []
    events = [e for f in frames for e in f.get("events", [])]
    print("   프레임", len(frames), "/ 이벤트 종류:", dict(Counter(e.get("type") for e in events).most_common(12)))
    kills = sorted((e for e in events if e.get("type") == "CHAMPION_KILL"), key=lambda e: e["timestamp"])
    expected = int(g.get("Team1Kills") or 0) + int(g.get("Team2Kills") or 0)
    print(f"   킬 이벤트 {len(kills)}건 (스코어보드 합계 {expected})")
    if kills:
        print("   첫 킬 예시:", json.dumps({k: kills[0].get(k) for k in ("timestamp", "killerId", "victimId", "assistingParticipantIds", "position")}))
    if frames:
        pf = frames[min(10, len(frames) - 1)].get("participantFrames") or {}
        one = next(iter(pf.values()), {})
        print("   10분 시점 선수 프레임 항목:", sorted(one.keys())[:14], "/ 위치:", one.get("position"))

    # 가까운 킬(30초 이내)을 한 교전으로 묶고, 다시보기 영상의 세트 시작 시각에 더해 링크를 만든다.
    fights: list[list[dict]] = []
    for k in kills:
        if fights and k["timestamp"] - fights[-1][-1]["timestamp"] <= 30000:
            fights[-1].append(k)
        else:
            fights.append([k])
    vod = g.get("VOD") or ""
    base, start = (vod.split("?t=")[0], int(vod.split("?t=")[1])) if "?t=" in vod and vod.split("?t=")[1].isdigit() else (vod, None)
    print(f"   교전 {len(fights)}회, 영상 시작점 {vod or '없음'}")
    for f in fights[:12]:
        at = f[0]["timestamp"]
        link = f"{base}?t={start + max(0, at // 1000 - 10)}" if start is not None else "(영상 없음)"
        print(f"     {clock(at)}  {len(f)}킬  {link}")


def main() -> None:
    for name, prefix in (("LCK", "LCK/2026"), ("Worlds", "2026 Season World Championship")):
        like = f'OverviewPage LIKE "{prefix}%"'
        total = cargo("ScoreboardGames", "COUNT(*)=N", like)
        with_id = cargo("ScoreboardGames", "COUNT(*)=N", f'{like} AND RiotPlatformGameId IS NOT NULL AND RiotPlatformGameId != ""')
        with_vod = cargo("ScoreboardGames", "COUNT(*)=N", f'{like} AND VOD IS NOT NULL AND VOD != ""')
        print(f"[분량] {name}: 세트 {total} / 경기 ID 있음 {with_id} / 영상 링크 있음 {with_vod}")

    inspect("LCK 결승 마지막 세트", 'OverviewPage LIKE "LCK/2026 Season/Season Playoffs%"')
    inspect("LCK 정규 시즌 1~2라운드 한 세트", 'OverviewPage LIKE "LCK/2026 Season/Rounds 1-2%"')
    inspect("월즈 결승 마지막 세트", 'OverviewPage LIKE "2026 Season World Championship/Main Event%"')


if __name__ == "__main__":
    main()
