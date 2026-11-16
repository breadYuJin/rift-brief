"""밴픽 예측 모델.

경기 전에 두 팀의 예상 밴과 픽을 내고, 한 세트가 끝날 때마다 그 세트의 밴픽을 반영해
다음 세트의 예상을 다시 낸다. 규칙은 단순하고 설명 가능하게 유지한다.

  픽 점수 = 그 팀이 최근에 얼마나 골랐나 + 요즘 대회에서 얼마나 나오나
  밴 점수 = 상대가 최근에 얼마나 골랐나 + 그 팀이 원래 얼마나 금지했나 + 요즘 얼마나 금지되나
            + 이번 시리즈 앞 세트에서 이미 금지했던 챔피언인가

최근 기록일수록 무겁게 본다(지수 감쇠). 피어리스 규칙에 따라 같은 시리즈에서 이미 나온 챔피언은 뺀다.
확률은 "이 순위로 예상한 챔피언이 지난 검증에서 실제로 나온 비율"로 보정해 보여 준다.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Iterable

from .gamedata import ROLES, SetRecord

TOP_N = 10


@dataclass(frozen=True)
class Weights:
    tau_team: float = 90.0  # 팀 기록의 감쇠 기간(일)
    tau_meta: float = 14.0  # 대회 전체 흐름의 감쇠 기간(일)
    pick_meta: float = 0.5
    ban_opponent: float = 1.0
    ban_own: float = 1.0
    ban_meta: float = 0.5
    ban_repeat: float = 2.0  # 같은 시리즈에서 이미 금지했던 챔피언에 주는 가산점
    pick_denied: float = 0.7  # 같은 시리즈에서 상대가 계속 금지한 챔피언의 픽 점수를 깎는 비율


class Decay:
    """지수 감쇠 누적값. 날짜가 지나면 값이 exp(-일수/tau) 만큼 줄어든다."""

    def __init__(self, tau: float):
        self.tau = tau
        self._value: dict[str, float] = defaultdict(float)
        self._day: dict[str, int] = {}

    def add(self, key: str, day: int, amount: float = 1.0) -> None:
        self._value[key] = self.get(key, day) + amount
        self._day[key] = day

    def get(self, key: str, day: int) -> float:
        if key not in self._day:
            return 0.0
        return self._value[key] * math.exp(-max(0, day - self._day[key]) / self.tau)

    def all(self, day: int) -> dict[str, float]:
        return {k: self.get(k, day) for k in self._day}


TOTAL = "__total__"


@dataclass
class TeamHistory:
    picks: Decay
    bans: Decay
    by_role: dict[str, Decay]
    sets: Decay


@dataclass
class Prediction:
    bans: list[tuple[str, float]]
    picks: list[tuple[str, float]]
    picks_by_role: dict[str, list[tuple[str, float]]] = field(default_factory=dict)


def to_day(iso: str) -> int:
    return date.fromisoformat(iso[:10]).toordinal() if iso else 0


class DraftModel:
    def __init__(self, weights: Weights | None = None):
        self.w = weights or Weights()
        self._teams: dict[int, TeamHistory] = {}
        self._meta_picks = Decay(self.w.tau_meta)
        self._meta_bans = Decay(self.w.tau_meta)
        self._meta_sets = Decay(self.w.tau_meta)
        self._meta_role = {r: Decay(self.w.tau_meta) for r in ROLES}
        self._roles: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.sets_seen = 0

    def _team(self, team_id: int) -> TeamHistory:
        if team_id not in self._teams:
            t = self.w.tau_team
            self._teams[team_id] = TeamHistory(Decay(t), Decay(t), {r: Decay(t) for r in ROLES}, Decay(t))
        return self._teams[team_id]

    def add(self, s: SetRecord) -> None:
        """끝난 세트 하나를 기록에 더한다."""
        if not s.draft:
            return
        day = to_day(s.start)
        self.sets_seen += 1
        self._meta_sets.add(TOTAL, day)
        for team in (s.blue, s.red):
            self._team(team.id).sets.add(TOTAL, day)
        for step in s.draft:
            hist = self._team(step.team_id)
            if step.kind == "pick":
                hist.picks.add(step.champion, day)
                self._meta_picks.add(step.champion, day)
                if step.role in hist.by_role:
                    hist.by_role[step.role].add(step.champion, day)
                    self._meta_role[step.role].add(step.champion, day)
                    self._roles[step.champion][step.role] += 1
            else:
                hist.bans.add(step.champion, day)
                self._meta_bans.add(step.champion, day)

    def knows(self, team_id: int) -> bool:
        """이 팀의 밴픽 기록이 있는지."""
        return team_id in self._teams

    def likely_role(self, champion: str) -> str:
        """그 챔피언이 지금까지 가장 자주 쓰인 포지션."""
        counts = self._roles.get(champion)
        return max(counts, key=lambda r: counts[r]) if counts else ""

    @staticmethod
    def _rates(counter: Decay, total: float, day: int) -> dict[str, float]:
        return {k: v / total for k, v in counter.all(day).items()} if total > 0 else {}

    def predict(
        self,
        team_id: int,
        opponent_id: int,
        when: str,
        *,
        unavailable: Iterable[str] = (),
        series_bans: Iterable[str] = (),
        series_denied: Iterable[str] = (),
        top: int = TOP_N,
    ) -> Prediction:
        """한 팀의 예상 밴·픽.

        unavailable: 고를 수 없는 챔피언(피어리스로 소진됐거나 이미 밴·픽된 것)
        series_bans: 이 팀이 같은 시리즈 앞 세트에서 금지했던 챔피언
        series_denied: 상대가 같은 시리즈 앞 세트에서 금지했던 챔피언
        """
        day = to_day(when)
        gone = set(unavailable)
        me, opp = self._team(team_id), self._team(opponent_id)
        w = self.w

        meta_total = self._meta_sets.get(TOTAL, day)
        meta_pick = self._rates(self._meta_picks, meta_total, day)
        meta_ban = self._rates(self._meta_bans, meta_total, day)
        my_pick = self._rates(me.picks, me.sets.get(TOTAL, day), day)
        my_ban = self._rates(me.bans, me.sets.get(TOTAL, day), day)
        opp_pick = self._rates(opp.picks, opp.sets.get(TOTAL, day), day)

        denied = set(series_denied)
        picks = {
            c: my_pick.get(c, 0.0) + w.pick_meta * meta_pick.get(c, 0.0)
            for c in set(my_pick) | set(meta_pick)
            if c not in gone
        }
        repeat = set(series_bans)
        bans = {
            c: w.ban_opponent * opp_pick.get(c, 0.0)
            + w.ban_own * my_ban.get(c, 0.0)
            + w.ban_meta * meta_ban.get(c, 0.0)
            + (w.ban_repeat if c in repeat else 0.0)
            for c in set(opp_pick) | set(my_ban) | set(meta_ban) | repeat
            if c not in gone
        }

        def ranked(scores: dict[str, float], n: int) -> list[tuple[str, float]]:
            return sorted(((c, round(v, 4)) for c, v in scores.items() if v > 0), key=lambda cv: (-cv[1], cv[0]))[:n]

        def adjust(c: str, v: float) -> float:
            return v * (1 - w.pick_denied) if c in denied else v

        # 포지션별 후보: 그 팀이 그 포지션에서 쓴 기록에, 대회 전체에서 그 포지션에 나온 비율을 더한다.
        by_role: dict[str, list[tuple[str, float]]] = {}
        my_sets = me.sets.get(TOTAL, day)
        for role, counter in me.by_role.items():
            mine = self._rates(counter, my_sets, day)
            meta = self._rates(self._meta_role[role], meta_total, day)
            scores = {
                c: adjust(c, mine.get(c, 0.0) + w.pick_meta * meta.get(c, 0.0))
                for c in set(mine) | set(meta)
                if c not in gone
            }
            by_role[role] = ranked(scores, 3)
        return Prediction(
            bans=ranked(bans, top),
            picks=ranked({c: adjust(c, v) for c, v in picks.items()}, top),
            picks_by_role=by_role,
        )


# ---- 지난 기록으로 되돌려 보는 검증 ----


@dataclass
class SetForecast:
    """한 세트 직전에 낸 예상과 실제 결과."""

    game_id: str
    match_id: int
    number: int
    team_id: int
    bans: list[tuple[str, float]]
    picks: list[tuple[str, float]]
    picks_by_role: dict[str, list[tuple[str, float]]]
    actual_bans: list[str]
    actual_picks: list[str]

    def hits(self, kind: str, k: int) -> int:
        predicted = [c for c, _ in (self.bans if kind == "ban" else self.picks)[:k]]
        actual = self.actual_bans if kind == "ban" else self.actual_picks
        return len(set(predicted) & set(actual))


def replay(
    sets: list[SetRecord],
    weights: Weights | None = None,
    before_set: Callable[["DraftModel", SetRecord], None] | None = None,
) -> tuple[list[SetForecast], DraftModel]:
    """세트를 시간순으로 돌며, 그 시점까지의 기록만으로 예상을 내고 실제와 맞춰 본다.

    before_set 은 각 세트를 기록에 더하기 전에 불린다(그 시점의 모델로 다른 것을 만들 때 쓴다).
    """
    model = DraftModel(weights)
    forecasts: list[SetForecast] = []
    used: dict[int, set[str]] = defaultdict(set)  # 시리즈별 소진 챔피언
    banned_by: dict[tuple[int, int], set[str]] = defaultdict(set)  # (시리즈, 팀) → 그 팀이 금지한 챔피언
    for s in sets:
        if not s.draft:
            continue
        if before_set:
            before_set(model, s)
        for team, opp in ((s.blue, s.red), (s.red, s.blue)):
            p = model.predict(
                team.id,
                opp.id,
                s.start,
                unavailable=used[s.match_id],
                series_bans=banned_by[(s.match_id, team.id)],
                series_denied=banned_by[(s.match_id, opp.id)],
            )
            forecasts.append(
                SetForecast(
                    game_id=s.game_id,
                    match_id=s.match_id,
                    number=s.number,
                    team_id=team.id,
                    bans=p.bans,
                    picks=p.picks,
                    picks_by_role=p.picks_by_role,
                    actual_bans=s.champions(team.id, "ban"),
                    actual_picks=s.champions(team.id, "pick"),
                )
            )
        model.add(s)
        used[s.match_id] |= set(s.picked)
        for team in (s.blue, s.red):
            banned_by[(s.match_id, team.id)] |= set(s.champions(team.id, "ban"))
    return forecasts, model


def recall(forecasts: list[SetForecast], kind: str, k: int) -> float:
    """실제 밴(픽) 가운데 예상 상위 k 개 안에 들어 있던 비율."""
    actual = sum(len(f.actual_bans if kind == "ban" else f.actual_picks) for f in forecasts)
    return sum(f.hits(kind, k) for f in forecasts) / actual if actual else 0.0


def rank_hit_rates(forecasts: list[SetForecast], kind: str, top: int = TOP_N) -> list[float]:
    """예상 순위별 적중률. 화면에서 확률로 보여 주는 값이다."""
    hit, seen = [0] * top, [0] * top
    for f in forecasts:
        actual = set(f.actual_bans if kind == "ban" else f.actual_picks)
        for i, (champion, _) in enumerate((f.bans if kind == "ban" else f.picks)[:top]):
            seen[i] += 1
            hit[i] += champion in actual
    return [round(h / n, 3) if n else 0.0 for h, n in zip(hit, seen)]


def appear_rate(forecasts: list[SetForecast], kind: str, k: int, drafted: dict[str, set[str]]) -> float:
    """예상 상위 k 개 가운데, 어느 팀이든 그 세트의 밴픽에 실제로 등장한 비율.

    drafted: 세트 ID → 그 세트에서 금지되거나 선택된 챔피언 전체
    """
    hit = total = 0
    for f in forecasts:
        predicted = [c for c, _ in (f.bans if kind == "ban" else f.picks)[:k]]
        hit += len(set(predicted) & drafted.get(f.game_id, set()))
        total += len(predicted)
    return hit / total if total else 0.0


def meta_only(tau_meta: float = 14.0) -> Weights:
    """비교 기준: 팀 정보 없이 대회 전체 흐름만 보는 예상."""
    return Weights(tau_meta=tau_meta, tau_team=1e-6, ban_opponent=0.0, ban_own=0.0, ban_repeat=0.0, pick_denied=0.0, pick_meta=1.0, ban_meta=1.0)


def evaluate(sets: list[SetRecord], weights: Weights, start_at: float = 0.0) -> dict[str, float]:
    """시간순 뒤쪽 구간(start_at 이후)의 적중률."""
    forecasts, _ = replay(sets, weights)
    order = {s.game_id: i for i, s in enumerate(s for s in sets if s.draft)}
    cut = int(len(order) * start_at)
    later = [f for f in forecasts if order[f.game_id] >= cut]
    return {
        "pick_recall_5": round(recall(later, "pick", 5), 3),
        "pick_recall_10": round(recall(later, "pick", 10), 3),
        "ban_recall_5": round(recall(later, "ban", 5), 3),
        "ban_recall_10": round(recall(later, "ban", 10), 3),
        "sets": len({f.game_id for f in later}),
    }


def tune(sets: list[SetRecord], train_share: float = 0.6) -> Weights:
    """앞쪽 구간에서만 가중치를 고른다. 뒤쪽 구간은 검증용으로 남긴다."""
    drafted = [s for s in sets if s.draft]
    train = drafted[: int(len(drafted) * train_share)]
    best, best_score = Weights(), -1.0
    for tau_team in (45.0, 90.0, 180.0):
        for tau_meta in (7.0, 14.0, 30.0):
            for pick_meta in (0.5, 1.0, 2.0):
                for ban_opponent in (0.5, 1.0, 2.0):
                    w = Weights(tau_team=tau_team, tau_meta=tau_meta, pick_meta=pick_meta, ban_opponent=ban_opponent)
                    # 초반은 기록이 없어 점수가 흔들리므로 학습 구간의 뒤 절반으로 고른다.
                    m = evaluate(train, w, start_at=0.5)
                    score = m["pick_recall_10"] + m["ban_recall_10"]
                    if score > best_score:
                        best, best_score = w, score
    return best
