"""경기 후 분석에 쓰는 지표: 교전, 오브젝트 순서, 골드 흐름, 정글 동선, 선수 맞대결.

타임라인의 참가자 번호는 1~5 가 블루(탑·정글·미드·원딜·서포터 순), 6~10 이 레드다.
이 순서 가정은 선수별 킬 수를 스코어보드와 대조해 세트마다 확인한다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .gamedata import ROLES, PlayerLine, SetRecord

FIGHT_GAP_SEC = 30
MAP_SIZE = 15000

MONSTERS = {
    "DRAGON": "드래곤",
    "ELDER_DRAGON": "장로 드래곤",
    "BARON_NASHOR": "바론",
    "RIFTHERALD": "전령",
    "HORDE": "공허 유충",
    "ATAKHAN": "아타칸",
}
_BARON = (5000, 10400)
_DRAGON = (9850, 4400)


def side_of(participant: int) -> str:
    return "blue" if 1 <= participant <= 5 else "red"


def zone(x: int | None, y: int | None) -> str:
    """맵 좌표를 대략적인 구역 이름으로 바꾼다."""
    if x is None or y is None:
        return ""
    near = lambda p, r: (x - p[0]) ** 2 + (y - p[1]) ** 2 <= r * r  # noqa: E731
    if near(_BARON, 1800):
        return "바론 둥지"
    if near(_DRAGON, 1800):
        return "드래곤 둥지"
    if x < 3500 and y < 3500:
        return "블루 본진"
    if x > MAP_SIZE - 3500 and y > MAP_SIZE - 3500:
        return "레드 본진"
    if abs(x - y) < 1600:
        return "미드"
    if x < 2600 or y > MAP_SIZE - 2600:
        return "탑"
    if y < 2600 or x > MAP_SIZE - 2600:
        return "바텀"
    return "위쪽 정글" if y > x else "아래쪽 정글"


def fights(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    """30초 안에 이어진 킬을 한 교전으로 묶는다."""
    out: list[dict[str, Any]] = []
    last = -10_000
    for t, killer, victim, _assists, x, y in sorted(timeline.get("kills") or [], key=lambda k: k[0]):
        if t - last > FIGHT_GAP_SEC or not out:
            out.append({"t": t, "blue": 0, "red": 0, "xs": [], "ys": []})
        f = out[-1]
        # 처치자가 없는 죽음(포탑·미니언)도 있어, 죽은 쪽의 반대편 득점으로 센다.
        f["red" if side_of(victim) == "blue" else "blue"] += 1
        if x is not None and y is not None:
            f["xs"].append(x)
            f["ys"].append(y)
        last = t
    for f in out:
        xs, ys = f.pop("xs"), f.pop("ys")
        f["x"] = round(sum(xs) / len(xs)) if xs else None
        f["y"] = round(sum(ys) / len(ys)) if ys else None
        f["zone"] = zone(f["x"], f["y"])
        f["winner"] = "blue" if f["blue"] > f["red"] else "red" if f["red"] > f["blue"] else ""
    return out


def objectives(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for t, kind, sub, team in timeline.get("monsters") or []:
        name = MONSTERS.get("ELDER_DRAGON" if sub == "ELDER_DRAGON" else kind, kind)
        out.append({"t": t, "name": name, "side": "blue" if team == 100 else "red"})
    return out


def gold_diff(timeline: dict[str, Any]) -> list[int]:
    """분 단위 골드 차(블루 − 레드)."""
    return [b - r for b, r in timeline.get("gold") or []]


def jungle_paths(timeline: dict[str, Any], minutes: int = 10) -> dict[str, list[list[int]]]:
    """초반 정글러의 분 단위 위치. 참가자 2번이 블루 정글, 7번이 레드 정글이다."""
    frames = (timeline.get("pos") or [])[1 : minutes + 1]
    return {"blue": [f[1] for f in frames if len(f) >= 10], "red": [f[6] for f in frames if len(f) >= 10]}


def participants_match(s: SetRecord, timeline: dict[str, Any]) -> bool:
    """타임라인의 참가자 순서가 스코어보드의 진영·포지션 순서와 같은지 킬 수로 확인한다."""
    kills: dict[int, int] = defaultdict(int)
    for _t, killer, _victim, _assists, _x, _y in timeline.get("kills") or []:
        if killer:
            kills[killer] += 1
    ordered = _ordered_players(s)
    if len(ordered) != 10:
        return False
    return all(kills[i + 1] == p.kills for i, p in enumerate(ordered))


def _ordered_players(s: SetRecord) -> list[PlayerLine]:
    by_key = {(p.team_id, p.role): p for p in s.players}
    out = []
    for team in (s.blue, s.red):
        for role in ROLES:
            p = by_key.get((team.id, role))
            if p:
                out.append(p)
    return out


def set_summary(s: SetRecord, timeline: dict[str, Any] | None) -> dict[str, Any]:
    """세트 하나의 분석 묶음. 타임라인이 없으면 스코어보드 기록만 담는다."""
    out: dict[str, Any] = {"has_timeline": bool(timeline)}
    if not timeline:
        return out
    fs = fights(timeline)
    out["fights"] = fs
    out["fight_count"] = {"total": len(fs), "blue": sum(f["winner"] == "blue" for f in fs), "red": sum(f["winner"] == "red" for f in fs)}
    out["objectives"] = objectives(timeline)
    out["gold_diff"] = gold_diff(timeline)
    out["jungle"] = jungle_paths(timeline)
    out["kills"] = [[t, side_of(victim) == "red", x, y] for t, _k, victim, _a, x, y in timeline.get("kills") or [] if x is not None]
    out["participants_ok"] = participants_match(s, timeline)
    first = min(timeline.get("kills") or [], key=lambda k: k[0], default=None)
    out["first_blood"] = (
        {"t": first[0], "side": "red" if side_of(first[2]) == "blue" else "blue", "zone": zone(first[4], first[5])}
        if first
        else None
    )
    return out


def matchups(s: SetRecord) -> list[dict[str, Any]]:
    """포지션별로 두 선수의 세트 기록을 나란히 놓는다."""
    minutes = s.length_min or 0
    by_key = {(p.team_id, p.role): p for p in s.players}
    rows = []
    for role in ROLES:
        a, b = by_key.get((s.blue.id, role)), by_key.get((s.red.id, role))
        if not a or not b:
            continue

        def line(p: PlayerLine) -> dict[str, Any]:
            return {
                "player": p.player,
                "champion": p.champion,
                "kda": [p.kills, p.deaths, p.assists],
                "cs": p.cs,
                "gold": p.gold,
                "damage": p.damage,
                "vision": p.vision,
                "cs_min": round(p.cs / minutes, 1) if minutes else None,
                "dpm": round(p.damage / minutes) if minutes else None,
            }

        rows.append({"role": role, "blue": line(a), "red": line(b)})
    return rows


def player_averages(sets: list[SetRecord]) -> dict[tuple[int, str], dict[str, Any]]:
    """선수별 시즌 평균. 키는 (팀 ID, 선수 이름)."""
    acc: dict[tuple[int, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    roles: dict[tuple[int, str], str] = {}
    for s in sets:
        minutes = s.length_min or 0
        if not minutes:
            continue
        for p in s.players:
            a = acc[(p.team_id, p.player)]
            roles[(p.team_id, p.player)] = p.role
            a["sets"] += 1
            a["wins"] += s.winner_id == p.team_id
            a["minutes"] += minutes
            for key in ("kills", "deaths", "assists", "cs", "gold", "damage", "vision"):
                a[key] += getattr(p, key)
    out = {}
    for key, a in acc.items():
        m = a["minutes"]
        out[key] = {
            "role": roles[key],
            "sets": int(a["sets"]),
            "win_rate": round(a["wins"] / a["sets"], 3),
            "kda": round((a["kills"] + a["assists"]) / max(1.0, a["deaths"]), 2),
            "cs_min": round(a["cs"] / m, 2),
            "dpm": round(a["damage"] / m),
            "gpm": round(a["gold"] / m),
            "vision_min": round(a["vision"] / m, 2),
        }
    return out
