"""밴픽 예측 모델.

경기 전에 두 팀의 예상 밴과 픽을 내고, 한 세트가 끝날 때마다 그 세트의 밴픽을 반영해
다음 세트의 예상을 다시 낸다. 규칙은 단순하고 설명 가능하게 유지한다.

  픽 점수 = 그 팀이 얼마나 골랐나 + 이번 패치 공식 경기에서 얼마나 나오나
  밴 점수 = 상대가 얼마나 골랐나 + 그 팀이 원래 얼마나 금지했나 + 이번 패치에서 얼마나 금지되나
            + 이번 시리즈 앞 세트에서 이미 금지했던 챔피언인가

기준은 날짜가 아니라 패치다. LoL 은 패치마다 메타가 바뀌므로, 대회 흐름은 "이번 패치가 적용된 뒤의
공식 경기"만 센다. 패치 초반에는 세트가 적으니 직전 패치의 흐름을 조금 섞고(meta_carry),
이번 패치 세트가 쌓일수록 그 비중이 줄어든다. 팀 기록은 패치가 하나 지날 때마다 일정 비율로
가볍게 본다(team_keep). 지난 시즌 기록은 쓰지 않는다.

피어리스 규칙에 따라 같은 시리즈에서 이미 나온 챔피언은 뺀다.
확률은 "이 순위로 예상한 챔피언이 지난 검증에서 실제로 나온 비율"로 보정해 보여 준다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .gamedata import ROLES, SetRecord

TOP_N = 10


@dataclass(frozen=True)
class Weights:
    meta_carry: float = 5.0  # 새 패치에 직전 패치 흐름을 몇 세트 분량만큼 섞을지
    team_keep: float = 0.75  # 패치가 하나 지날 때마다 팀 기록에 곱하는 비율
    team_scale: float = 1.0  # 0 이면 팀 기록을 아예 쓰지 않는다(비교 기준용)
    pick_meta: float = 0.5
    ban_opponent: float = 1.0
    ban_own: float = 1.0
    ban_meta: float = 0.5
    ban_repeat: float = 2.0  # 같은 시리즈에서 이미 금지했던 챔피언에 주는 가산점
    pick_denied: float = 0.7  # 같은 시리즈에서 상대가 계속 금지한 챔피언의 픽 점수를 깎는 비율


@dataclass
class Tally:
    """한 패치 안에서 센 횟수."""

    sets: int = 0
    picks: Counter = field(default_factory=Counter)
    bans: Counter = field(default_factory=Counter)
    wins: Counter = field(default_factory=Counter)
    by_role: dict[str, Counter] = field(default_factory=lambda: {r: Counter() for r in ROLES})


Rates = dict[str, dict[str, float]]  # "pick" | "ban" | 포지션 이름 → 챔피언별 세트당 비율


@dataclass
class Prediction:
    bans: list[tuple[str, float]]
    picks: list[tuple[str, float]]
    picks_by_role: dict[str, list[tuple[str, float]]] = field(default_factory=dict)


class DraftModel:
    def __init__(self, weights: Weights | None = None):
        self.w = weights or Weights()
        self.patches: list[str] = []  # 등장한 순서
        self._meta: dict[str, Tally] = {}
        self._carry: dict[str, Rates] = {}  # 패치 → 그 패치가 시작될 때 넘겨받은 직전 패치의 흐름
        self._teams: dict[int, dict[str, Tally]] = defaultdict(dict)
        self._roles: dict[str, Counter] = defaultdict(Counter)
        self.sets_seen = 0

    # ---- 기록 쌓기 ----

    def add(self, s: SetRecord) -> None:
        """끝난 세트 하나를 기록에 더한다."""
        if not s.draft:
            return
        if s.patch not in self._meta:
            if self.patches:
                self._carry[s.patch] = self.meta_rates(self.patches[-1])
            self.patches.append(s.patch)
            self._meta[s.patch] = Tally()
        self.sets_seen += 1
        meta = self._meta[s.patch]
        meta.sets += 1
        for team in (s.blue, s.red):
            self._teams[team.id].setdefault(s.patch, Tally()).sets += 1
        for step in s.draft:
            mine = self._teams[step.team_id][s.patch]
            if step.kind == "pick":
                mine.picks[step.champion] += 1
                meta.picks[step.champion] += 1
                meta.wins[step.champion] += s.winner_id == step.team_id
                if step.role in mine.by_role:
                    mine.by_role[step.role][step.champion] += 1
                    meta.by_role[step.role][step.champion] += 1
                    self._roles[step.champion][step.role] += 1
            else:
                mine.bans[step.champion] += 1
                meta.bans[step.champion] += 1

    def knows(self, team_id: int) -> bool:
        """이 팀의 밴픽 기록이 있는지."""
        return team_id in self._teams

    def likely_role(self, champion: str) -> str:
        """그 챔피언이 지금까지 가장 자주 쓰인 포지션."""
        counts = self._roles.get(champion)
        return max(counts, key=lambda r: counts[r]) if counts else ""

    # ---- 비율 ----

    def meta_rates(self, patch: str | None) -> Rates:
        """그 패치의 공식 경기 흐름(세트당 등장 비율). 패치 초반에는 직전 패치 흐름이 섞인다."""
        if patch is None:
            patch = self.patches[-1] if self.patches else ""
        tally = self._meta.get(patch)
        if tally is None:  # 아직 한 세트도 없는 새 패치: 직전 패치 흐름을 그대로 쓴다.
            return self.meta_rates(self.patches[-1]) if self.patches else {}
        carry = self._carry.get(patch, {})
        k = self.w.meta_carry if carry else 0.0
        total = tally.sets + k
        if total <= 0:
            return {}
        out: Rates = {}
        for kind, counts in (("pick", tally.picks), ("ban", tally.bans), *tally.by_role.items()):
            prev = carry.get(kind, {})
            out[kind] = {c: (counts.get(c, 0) + k * prev.get(c, 0.0)) / total for c in set(counts) | set(prev)}
        return out

    def team_rates(self, team_id: int, patch: str | None) -> Rates:
        """그 팀의 세트당 비율. 지난 패치의 기록일수록 가볍게 센다."""
        history = self._teams.get(team_id)
        if not history or self.w.team_scale == 0:
            return {}
        index = {p: i for i, p in enumerate(self.patches)}
        now = index.get(patch, len(self.patches)) if patch is not None else len(self.patches) - 1
        total = 0.0
        sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for p, tally in history.items():
            weight = self.w.team_keep ** max(0, now - index[p])
            total += weight * tally.sets
            for kind, counts in (("pick", tally.picks), ("ban", tally.bans), *tally.by_role.items()):
                for c, n in counts.items():
                    sums[kind][c] += weight * n
        if total <= 0:
            return {}
        return {kind: {c: v / total for c, v in counts.items()} for kind, counts in sums.items()}

    # ---- 예상 ----

    def predict(
        self,
        team_id: int,
        opponent_id: int,
        patch: str | None = None,
        *,
        unavailable: Iterable[str] = (),
        series_bans: Iterable[str] = (),
        series_denied: Iterable[str] = (),
        top: int = TOP_N,
    ) -> Prediction:
        """한 팀의 예상 밴·픽.

        patch: 그 경기에 적용되는 패치. 모르면(None) 가장 최근 패치로 본다.
        unavailable: 고를 수 없는 챔피언(피어리스로 소진됐거나 이미 밴·픽된 것)
        series_bans: 이 팀이 같은 시리즈 앞 세트에서 금지했던 챔피언
        series_denied: 상대가 같은 시리즈 앞 세트에서 금지했던 챔피언
        """
        gone = set(unavailable)
        w = self.w
        meta = self.meta_rates(patch)
        me, opp = self.team_rates(team_id, patch), self.team_rates(opponent_id, patch)
        meta_pick, meta_ban = meta.get("pick", {}), meta.get("ban", {})
        my_pick, my_ban, opp_pick = me.get("pick", {}), me.get("ban", {}), opp.get("pick", {})

        denied = set(series_denied)
        repeat = set(series_bans)

        def adjust(c: str, v: float) -> float:
            return v * (1 - w.pick_denied) if c in denied else v

        def ranked(scores: dict[str, float], n: int) -> list[tuple[str, float]]:
            return sorted(((c, round(v, 4)) for c, v in scores.items() if v > 0), key=lambda cv: (-cv[1], cv[0]))[:n]

        picks = {
            c: adjust(c, w.team_scale * my_pick.get(c, 0.0) + w.pick_meta * meta_pick.get(c, 0.0))
            for c in set(my_pick) | set(meta_pick)
            if c not in gone
        }
        bans = {
            c: w.team_scale * (w.ban_opponent * opp_pick.get(c, 0.0) + w.ban_own * my_ban.get(c, 0.0))
            + w.ban_meta * meta_ban.get(c, 0.0)
            + (w.ban_repeat if c in repeat else 0.0)
            for c in set(opp_pick) | set(my_ban) | set(meta_ban) | repeat
            if c not in gone
        }
        # 포지션별 후보: 그 팀이 그 포지션에서 쓴 기록에, 이번 패치에서 그 포지션에 나온 비율을 더한다.
        by_role: dict[str, list[tuple[str, float]]] = {}
        for role in ROLES:
            mine, flow = me.get(role, {}), meta.get(role, {})
            scores = {
                c: adjust(c, w.team_scale * mine.get(c, 0.0) + w.pick_meta * flow.get(c, 0.0))
                for c in set(mine) | set(flow)
                if c not in gone
            }
            by_role[role] = ranked(scores, 3)
        return Prediction(bans=ranked(bans, top), picks=ranked(picks, top), picks_by_role=by_role)

    # ---- 패치별 메타 ----

    def patch_meta(self, patch: str, top: int = 15) -> dict[str, object]:
        """그 패치의 공식 경기에서 많이 나온 챔피언(직전 패치를 섞지 않은 실제 횟수)."""
        tally = self._meta[patch]
        i = self.patches.index(patch)
        before = self._meta[self.patches[i - 1]] if i > 0 else None

        def presence(t: Tally, c: str) -> float:
            return (t.picks.get(c, 0) + t.bans.get(c, 0)) / t.sets if t.sets else 0.0

        rows = []
        for c in set(tally.picks) | set(tally.bans):
            picks = tally.picks.get(c, 0)
            rows.append(
                {
                    "champion": c,
                    "picks": picks,
                    "bans": tally.bans.get(c, 0),
                    "presence": round(presence(tally, c), 3),
                    "win_rate": round(tally.wins.get(c, 0) / picks, 3) if picks else None,
                    "role": max(ROLES, key=lambda r: tally.by_role[r].get(c, 0)) if picks else "",
                    # 직전 패치와 견준 밴픽률 변화. 직전 패치가 없으면 None.
                    "change": round(presence(tally, c) - presence(before, c), 3) if before else None,
                }
            )
        rows.sort(key=lambda r: (-r["presence"], -r["picks"], r["champion"]))
        return {"patch": patch, "sets": tally.sets, "champions": rows[:top]}


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
                s.patch,
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


def meta_only(meta_carry: float = 5.0) -> Weights:
    """비교 기준: 팀 정보 없이 그 패치의 대회 흐름만 보는 예상."""
    return Weights(meta_carry=meta_carry, team_scale=0.0, ban_repeat=0.0, pick_denied=0.0, pick_meta=1.0, ban_meta=1.0)


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
    for meta_carry in (0.0, 5.0, 15.0):
        for team_keep in (0.5, 0.75, 1.0):
            for pick_meta in (0.5, 1.0, 2.0):
                for ban_opponent in (0.5, 1.0, 2.0):
                    w = Weights(meta_carry=meta_carry, team_keep=team_keep, pick_meta=pick_meta, ban_opponent=ban_opponent)
                    # 초반은 기록이 없어 점수가 흔들리므로 학습 구간의 뒤 절반으로 고른다.
                    m = evaluate(train, w, start_at=0.5)
                    score = m["pick_recall_10"] + m["ban_recall_10"]
                    if score > best_score:
                        best, best_score = w, score
    return best
