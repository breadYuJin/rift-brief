"""세트별 선수 평점.

경기가 끝난 뒤 "그 판에 얼마나 잘했나"를 10점 만점 한 숫자로 보여 준다. 팬 투표로 매기는
후푸 평점과 달리, 이 점수는 세트 기록으로 계산한다.

  1. 선수마다 여섯 가지를 잰다: KDA, 킬 관여율, 분당 데스, 팀 내 피해 비중,
     맞상대와의 분당 골드 차, 분당 시야 점수 (+ 라이너는 맞상대와의 분당 CS 차)
  2. 같은 포지션 선수들의 평균·표준편차로 표준화한다(포지션마다 기대치가 다르므로).
  3. 포지션별 가중치로 합쳐 6점을 기준으로 올리고 내린다. 이긴 쪽은 조금 더하고 진 쪽은 조금 뺀다.
  4. 팬 의견이 모이면 일부만 섞는다(pipeline/feedback.py). 계산 평점이 기준이고, 의견은 정해진
     비율과 폭 안에서만 평점을 움직인다.

가중치와 의견 반영 비율은 저장소 맨 위의 ratings.config.json 에서 바꿀 수 있다.

표준화 기준(data/rating_scale.json)은 처음 한 번 만든 뒤 고정한다. 기준이 매일 바뀌면 지난 경기의
평점도 매일 달라지기 때문이다. 시즌이 바뀌어 다시 만들고 싶으면 그 파일을 지우면 된다.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .gamedata import ROLES, PlayerLine, SetRecord

BASE = 6.0
MIN_SCALE_SETS = 30  # 기준을 만들 때 필요한 최소 세트 수
CONFIG_PATH = Path(__file__).resolve().parents[1] / "ratings.config.json"

METRICS = ("kda", "kp", "deaths", "dmg_share", "gold_diff", "cs_diff", "vision")
# 포지션별 가중치. 데스는 적을수록 좋으므로 음수다. 절댓값의 합은 1.
WEIGHTS: dict[str, dict[str, float]] = {
    "탑": {
        "kda": 0.25,
        "kp": 0.10,
        "deaths": -0.15,
        "dmg_share": 0.20,
        "gold_diff": 0.15,
        "cs_diff": 0.10,
        "vision": 0.05,
    },
    "정글": {
        "kda": 0.25,
        "kp": 0.20,
        "deaths": -0.15,
        "dmg_share": 0.10,
        "gold_diff": 0.15,
        "cs_diff": 0.05,
        "vision": 0.10,
    },
    "미드": {
        "kda": 0.25,
        "kp": 0.15,
        "deaths": -0.15,
        "dmg_share": 0.20,
        "gold_diff": 0.15,
        "cs_diff": 0.05,
        "vision": 0.05,
    },
    "원딜": {
        "kda": 0.25,
        "kp": 0.15,
        "deaths": -0.15,
        "dmg_share": 0.25,
        "gold_diff": 0.10,
        "cs_diff": 0.05,
        "vision": 0.05,
    },
    "서포터": {
        "kda": 0.25,
        "kp": 0.25,
        "deaths": -0.20,
        "dmg_share": 0.05,
        "gold_diff": 0.05,
        "cs_diff": 0.0,
        "vision": 0.20,
    },
}


@dataclass(frozen=True)
class Feedback:
    """팬 의견을 평점에 섞는 정도."""

    min_votes: int = 3  # 한 선수·한 세트에 이만큼 모이기 전에는 반영하지 않는다
    max_share: float = 0.3  # 의견이 아무리 많아도 이 비율까지만 섞는다
    prior_votes: float = 5.0  # 클수록 의견이 많이 쌓여야 반영 비율이 오른다
    max_shift: float = 1.0  # 의견으로 평점이 움직일 수 있는 최대 폭(점)


@dataclass(frozen=True)
class Config:
    spread: float = 1.6  # 표준화 점수 1 이 평점 몇 점인지
    win_bonus: float = 0.3
    weights: dict[str, dict[str, float]] = field(default_factory=lambda: {r: dict(w) for r, w in WEIGHTS.items()})
    feedback: Feedback = field(default_factory=Feedback)

    def digest(self) -> str:
        """설정이 바뀌었는지 알아보기 위한 짧은 지문."""
        raw = json.dumps(
            [self.spread, self.win_bonus, self.weights, self.feedback.__dict__], sort_keys=True, ensure_ascii=False
        )
        return hashlib.sha1(raw.encode()).hexdigest()[:8]


def load_config(path: Path | None = None) -> Config:
    """ratings.config.json 을 읽는다. 파일이 없거나 항목이 빠져 있으면 기본값을 쓴다.

    잘못된 값(모르는 포지션·지표, 숫자가 아닌 값)은 무시하고 기본값을 남긴다.
    """
    path = path or CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Config()

    def number(value: Any, default: float, low: float, high: float) -> float:
        return (
            min(high, max(low, float(value)))
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else default
        )

    weights = {r: dict(w) for r, w in WEIGHTS.items()}
    for role, row in (raw.get("weights") or {}).items():
        if role in weights and isinstance(row, dict):
            for metric, value in row.items():
                if metric in METRICS:
                    weights[role][metric] = number(value, weights[role][metric], -1.0, 1.0)
    fb, base = raw.get("feedback") or {}, Feedback()
    return Config(
        spread=number(raw.get("spread"), 1.6, 0.1, 5.0),
        win_bonus=number(raw.get("win_bonus"), 0.3, 0.0, 2.0),
        weights=weights,
        feedback=Feedback(
            min_votes=int(number(fb.get("min_votes"), base.min_votes, 1, 1000)),
            max_share=number(fb.get("max_share"), base.max_share, 0.0, 1.0),
            prior_votes=number(fb.get("prior_votes"), base.prior_votes, 0.0, 1000.0),
            max_shift=number(fb.get("max_shift"), base.max_shift, 0.0, 9.0),
        ),
    )


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


def rate_set(s: SetRecord, scale: Scale, config: Config | None = None) -> dict[tuple[int, str], float]:
    """세트의 선수별 계산 평점(1.0 ~ 10.0). 팬 의견은 아직 섞지 않은 값이다."""
    config = config or Config()
    roles = {(p.team_id, p.player): p.role for p in s.players}
    out: dict[tuple[int, str], float] = {}
    for key, row in measures(s).items():
        role = roles[key]
        if role not in config.weights or role not in scale:
            continue
        total = 0.0
        for m, weight in config.weights[role].items():
            mean, sd = scale[role][m]
            z = max(-2.5, min(2.5, (row[m] - mean) / sd))
            total += weight * z
        rating = BASE + config.spread * total + (config.win_bonus if s.winner_id == key[0] else -config.win_bonus)
        out[key] = round(max(1.0, min(10.0, rating)), 1)
    return out


def blend(base: float, fan_mean: float, votes: int, fb: Feedback) -> float:
    """계산 평점에 팬 의견 평균을 일부 섞는다.

    반영 비율 = max_share × 의견 수 ÷ (의견 수 + prior_votes). 의견이 min_votes 보다 적으면 그대로 둔다.
    움직이는 폭은 max_shift 를 넘지 않는다.
    """
    if votes < fb.min_votes:
        return base
    share = fb.max_share * votes / (votes + fb.prior_votes)
    shift = max(-fb.max_shift, min(fb.max_shift, share * (fan_mean - base)))
    return round(max(1.0, min(10.0, base + shift)), 1)


def best_of(ratings: dict[tuple[int, str], float], team_id: int | None) -> dict[str, Any] | None:
    """그 팀에서 평점이 가장 높은 선수. 이 사이트가 뽑는 세트 최고 선수다(공식 MVP 가 아니다)."""
    mine = [(r, name) for (tid, name), r in ratings.items() if tid == team_id]
    if not mine:
        return None
    rating, name = max(mine, key=lambda x: (x[0], x[1]))
    return {"player": name, "team_id": team_id, "rating": rating}
