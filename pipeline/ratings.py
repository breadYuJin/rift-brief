"""세트별 선수 평점.

경기가 끝난 뒤 "그 판에 얼마나 잘했나"를 10점 만점 한 숫자로 보여 준다. 팬 투표로 매기는
후푸 평점과 달리, 이 점수는 세트 기록만으로 계산한다.

  1. 선수마다 여섯 가지를 잰다: KDA, 킬 관여율, 분당 데스, 팀 내 피해 비중,
     맞상대와의 분당 골드 차, 분당 시야 점수 (+ 라이너는 맞상대와의 분당 CS 차)
  2. 같은 포지션 선수들의 평균·표준편차로 표준화한다(포지션마다 기대치가 다르므로).
  3. 포지션별 가중치로 합쳐 6점을 기준으로 올리고 내린다. 이긴 쪽은 조금 더하고 진 쪽은 조금 뺀다.

표준화 기준(data/rating_scale.json)은 처음 한 번 만든 뒤 고정한다. 기준이 매일 바뀌면 지난 경기의
평점도 매일 달라지기 때문이다. 시즌이 바뀌어 다시 만들고 싶으면 그 파일을 지우면 된다.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .gamedata import ROLES, PlayerLine, SetRecord

BASE = 6.0
SPREAD = 1.6  # 표준화 점수 1 이 평점 몇 점인지
WIN_BONUS = 0.3
MIN_SCALE_SETS = 30  # 기준을 만들 때 필요한 최소 세트 수

METRICS = ("kda", "kp", "deaths", "dmg_share", "gold_diff", "cs_diff", "vision")
# 포지션별 가중치. 데스는 적을수록 좋으므로 음수다. 절댓값의 합은 1.
WEIGHTS: dict[str, dict[str, float]] = {
    "탑": {"kda": 0.25, "kp": 0.10, "deaths": -0.15, "dmg_share": 0.20, "gold_diff": 0.15, "cs_diff": 0.10, "vision": 0.05},
    "정글": {"kda": 0.25, "kp": 0.20, "deaths": -0.15, "dmg_share": 0.10, "gold_diff": 0.15, "cs_diff": 0.05, "vision": 0.10},
    "미드": {"kda": 0.25, "kp": 0.15, "deaths": -0.15, "dmg_share": 0.20, "gold_diff": 0.15, "cs_diff": 0.05, "vision": 0.05},
    "원딜": {"kda": 0.25, "kp": 0.15, "deaths": -0.15, "dmg_share": 0.25, "gold_diff": 0.10, "cs_diff": 0.05, "vision": 0.05},
    "서포터": {"kda": 0.25, "kp": 0.25, "deaths": -0.20, "dmg_share": 0.05, "gold_diff": 0.05, "cs_diff": 0.0, "vision": 0.20},
}

Scale = dict[str, dict[str, list[float]]]  # 포지션 → 지표 → [평균, 표준편차]


def measures(s: SetRecord) -> dict[tuple[int, str], dict[str, float]]:
    """세트의 선수별 지표. 키는 (팀 ID, 선수 이름). 기록이 불완전한 세트는 빈 결과."""
    minutes = s.length_min or 0
    if minutes <= 0 or len(s.players) != 10:
        return {}
    by_team: dict[int, list[PlayerLine]] = defaultdict(list)
    for p in s.players:
        by_team[p.team_id].append(p)
    lane = {(p.team_id, p.role): p for p in s.players}
    out: dict[tuple[int, str], dict[str, float]] = {}
    for p in s.players:
        mates = by_team[p.team_id]
        rival = lane.get((s.other(p.team_id).id, p.role))
        if rival is None:
            return {}
        team_kills = sum(m.kills for m in mates)
        team_damage = sum(m.damage for m in mates)
        out[(p.team_id, p.player)] = {
            "kda": math.log1p((p.kills + p.assists) / max(1, p.deaths)),
            "kp": (p.kills + p.assists) / team_kills if team_kills else 0.0,
            "deaths": p.deaths / minutes,
            "dmg_share": p.damage / team_damage if team_damage else 0.0,
            "gold_diff": (p.gold - rival.gold) / minutes,
            "cs_diff": (p.cs - rival.cs) / minutes,
            "vision": p.vision / minutes,
        }
    return out


def build_scale(sets: list[SetRecord]) -> Scale:
    """포지션별 평균과 표준편차."""
    values: dict[str, dict[str, list[float]]] = {r: {m: [] for m in METRICS} for r in ROLES}
    for s in sets:
        roles = {(p.team_id, p.player): p.role for p in s.players}
        for key, row in measures(s).items():
            if roles[key] in values:
                for m in METRICS:
                    values[roles[key]][m].append(row[m])
    scale: Scale = {}
    for role, by_metric in values.items():
        scale[role] = {}
        for m, xs in by_metric.items():
            if not xs:
                scale[role][m] = [0.0, 1.0]
                continue
            mean = sum(xs) / len(xs)
            sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
            scale[role][m] = [round(mean, 5), round(sd, 5) or 1.0]
    return scale


def load_scale(data_dir: Path, sets: list[SetRecord]) -> Scale | None:
    """고정해 둔 기준을 읽는다. 없으면 지금 있는 세트로 만들어 저장한다. 세트가 모자라면 None."""
    path = data_dir / "rating_scale.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["scale"]
    usable = [s for s in sets if measures(s)]
    if len(usable) < MIN_SCALE_SETS:
        return None
    scale = build_scale(usable)
    note = {"sets": len(usable), "from": usable[0].start[:10], "to": usable[-1].start[:10]}
    path.write_text(json.dumps({"basis": note, "scale": scale}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return scale


def rate_set(s: SetRecord, scale: Scale) -> dict[tuple[int, str], float]:
    """세트의 선수별 평점(1.0 ~ 10.0)."""
    roles = {(p.team_id, p.player): p.role for p in s.players}
    out: dict[tuple[int, str], float] = {}
    for key, row in measures(s).items():
        role = roles[key]
        if role not in WEIGHTS or role not in scale:
            continue
        total = 0.0
        for m, weight in WEIGHTS[role].items():
            mean, sd = scale[role][m]
            z = max(-2.5, min(2.5, (row[m] - mean) / sd))
            total += weight * z
        rating = BASE + SPREAD * total + (WIN_BONUS if s.winner_id == key[0] else -WIN_BONUS)
        out[key] = round(max(1.0, min(10.0, rating)), 1)
    return out


def best_of(ratings: dict[tuple[int, str], float], team_id: int | None) -> dict[str, Any] | None:
    """그 팀에서 평점이 가장 높은 선수. 이 사이트가 뽑는 세트 최고 선수다(공식 MVP 가 아니다)."""
    mine = [(r, name) for (tid, name), r in ratings.items() if tid == team_id]
    if not mine:
        return None
    rating, name = max(mine, key=lambda x: (x[0], x[1]))
    return {"player": name, "team_id": team_id, "rating": rating}
