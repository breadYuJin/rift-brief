"""밴픽이 끝난 시점의 세트 승률 모델.

입력은 세 가지다.
  - 전력 차: 세트 결과로 갱신하는 Elo 점수의 차이
  - 조합 차: 양 팀이 고른 챔피언들의 최근 대회 승률(표본이 적으면 50%쪽으로 당김) 평균의 차이
  - 숙련 차: 각 팀이 그 챔피언을 이전에 얼마나 써 봤는지의 차이

로지스틱 회귀로 블루 진영의 승률을 낸다. 검증은 항상 "그 시점 이전 기록으로만 학습해 예측"하는
방식(전진 검증)으로 한다. 한 시즌이 수백 세트뿐이라 조합 효과는 거의 잡히지 않는다. 그래서 밴픽 후
승률은 밴픽 전 승률에서 조금만 움직인다.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .gamedata import SetRecord

MIN_TRAIN = 120  # 이만큼 쌓이기 전에는 예측하지 않는다
REFIT_EVERY = 25
# 조합·숙련 항은 한 시즌 표본으로는 잡음이 커서 강하게 눌러 둔다(값이 클수록 0 쪽으로 당긴다).
# 2026 시즌 전진 검증에서 1 이면 적중률이 오히려 떨어졌고(64.1% → 61.4%), 10 이면 밴픽 전과 같았다.
DRAFT_L2 = 10.0


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def fit_logistic(
    rows: list[list[float]], labels: list[int], l2: float = 1.0, steps: int = 400, lr: float = 0.3
) -> list[float]:
    """경사 하강으로 푸는 로지스틱 회귀. 첫 계수는 절편이다."""
    n, d = len(rows), len(rows[0]) if rows else 0
    coef = [0.0] * (d + 1)
    for _ in range(steps):
        grad = [0.0] * (d + 1)
        for x, y in zip(rows, labels, strict=True):
            err = sigmoid(coef[0] + sum(c * v for c, v in zip(coef[1:], x, strict=True))) - y
            grad[0] += err
            for j, v in enumerate(x):
                grad[j + 1] += err * v
        coef[0] -= lr * grad[0] / n
        for j in range(1, d + 1):
            coef[j] -= lr * (grad[j] + l2 * coef[j]) / n
    return coef


def fit_full(rows: list[list[float]], labels: list[int]) -> list[float]:
    """전력 차는 그대로, 조합·숙련 항은 DRAFT_L2 만큼 더 눌러서 맞춘다."""
    scale = [1.0] + [1.0 / math.sqrt(DRAFT_L2)] * (len(rows[0]) - 1)
    coef = fit_logistic([[v * k for v, k in zip(r, scale, strict=True)] for r in rows], labels)
    return [coef[0]] + [c * k for c, k in zip(coef[1:], scale, strict=True)]


def predict(coef: list[float], x: list[float]) -> float:
    return sigmoid(coef[0] + sum(c * v for c, v in zip(coef[1:], x, strict=True)))


class WinState:
    """세트를 하나씩 관찰하며 쌓는 상태: Elo, 챔피언 승률, 팀별 챔피언 사용 횟수."""

    def __init__(self, k: float = 24.0, prior: float = 10.0):
        self.k, self.prior = k, prior
        self.elo: dict[int, float] = defaultdict(lambda: 1500.0)
        self.champ_games: dict[str, int] = defaultdict(int)
        self.champ_wins: dict[str, int] = defaultdict(int)
        self.team_champ: dict[tuple[int, str], int] = defaultdict(int)

    def _strength(self, picks: list[str]) -> float:
        if not picks:
            return 0.5
        return sum((self.champ_wins[c] + self.prior / 2) / (self.champ_games[c] + self.prior) for c in picks) / len(
            picks
        )

    def _comfort(self, team_id: int, picks: list[str]) -> float:
        if not picks:
            return 0.0
        return sum(math.log1p(self.team_champ[(team_id, c)]) for c in picks) / len(picks)

    def features(self, blue_id: int, red_id: int, blue_picks: list[str], red_picks: list[str]) -> list[float]:
        return [
            (self.elo[blue_id] - self.elo[red_id]) / 400.0,
            (self._strength(blue_picks) - self._strength(red_picks)) * 10.0,
            self._comfort(blue_id, blue_picks) - self._comfort(red_id, red_picks),
        ]

    def observe(self, s: SetRecord) -> None:
        if s.winner_id is None:
            return
        blue_won = s.winner_id == s.blue.id
        expected = 1.0 / (1.0 + 10 ** ((self.elo[s.red.id] - self.elo[s.blue.id]) / 400.0))
        delta = self.k * ((1.0 if blue_won else 0.0) - expected)
        self.elo[s.blue.id] += delta
        self.elo[s.red.id] -= delta
        for team, won in ((s.blue, blue_won), (s.red, not blue_won)):
            for c in s.champions(team.id, "pick"):
                self.champ_games[c] += 1
                self.champ_wins[c] += won
                self.team_champ[(team.id, c)] += 1


@dataclass
class WinForecast:
    game_id: str
    before_draft: float  # 밴픽 전(전력 차만 본) 블루 승률
    after_draft: float  # 밴픽 후 블루 승률
    blue_won: bool


@dataclass
class WinModel:
    state: WinState
    coef_base: list[float]
    coef_full: list[float]

    def probability(
        self, blue_id: int, red_id: int, blue_picks: list[str], red_picks: list[str]
    ) -> tuple[float, float]:
        """(밴픽 전, 밴픽 후) 블루 진영 승률."""
        x = self.state.features(blue_id, red_id, blue_picks, red_picks)
        return predict(self.coef_base, x[:1]), predict(self.coef_full, x)


def walk_forward(sets: list[SetRecord]) -> tuple[list[WinForecast], WinModel]:
    """시간순으로 돌며 이전 세트만으로 학습한 모델로 각 세트를 예측한다."""
    state = WinState()
    rows: list[list[float]] = []
    labels: list[int] = []
    forecasts: list[WinForecast] = []
    coef_base, coef_full = [0.0, 0.0], [0.0, 0.0, 0.0, 0.0]
    fitted_at = 0
    for s in sets:
        if s.winner_id is None or not s.draft:
            continue
        x = state.features(s.blue.id, s.red.id, s.champions(s.blue.id, "pick"), s.champions(s.red.id, "pick"))
        y = int(s.winner_id == s.blue.id)
        if len(rows) >= MIN_TRAIN:
            if len(rows) - fitted_at >= REFIT_EVERY or fitted_at == 0:
                coef_base = fit_logistic([r[:1] for r in rows], labels)
                coef_full = fit_full(rows, labels)
                fitted_at = len(rows)
            forecasts.append(WinForecast(s.game_id, predict(coef_base, x[:1]), predict(coef_full, x), bool(y)))
        rows.append(x)
        labels.append(y)
        state.observe(s)
    if rows:
        coef_base = fit_logistic([r[:1] for r in rows], labels)
        coef_full = fit_full(rows, labels)
    return forecasts, WinModel(state, coef_base, coef_full)


def score(probabilities: list[float], outcomes: list[bool]) -> dict[str, float]:
    n = len(probabilities)
    if n == 0:
        return {"sets": 0, "accuracy": 0.0, "brier": 0.0, "log_loss": 0.0}
    eps = 1e-9
    return {
        "sets": n,
        "accuracy": round(sum((p >= 0.5) == o for p, o in zip(probabilities, outcomes, strict=True)) / n, 3),
        "brier": round(sum((p - o) ** 2 for p, o in zip(probabilities, outcomes, strict=True)) / n, 4),
        "log_loss": round(
            -sum(math.log(max(eps, p if o else 1 - p)) for p, o in zip(probabilities, outcomes, strict=True)) / n, 4
        ),
    }


def report(forecasts: list[WinForecast]) -> dict[str, dict[str, float]]:
    outcomes = [f.blue_won for f in forecasts]
    blue_rate = sum(outcomes) / len(outcomes) if outcomes else 0.5
    return {
        "coin": score([0.5] * len(outcomes), outcomes),
        "blue_rate": score([blue_rate] * len(outcomes), outcomes),
        "before_draft": score([f.before_draft for f in forecasts], outcomes),
        "after_draft": score([f.after_draft for f in forecasts], outcomes),
    }
