"""세트 기록으로 예측·분석 결과를 만들어 사이트용 파일로 내보낸다.

  data/sets/<경기 ID>.json  세트별 밴픽, 세트 직전 예상과 적중, 승률, 교전·오브젝트·동선, 선수 맞대결
  data/models.json          밴픽 예측과 승률 모델의 검증 결과
  data/draft.json           밴픽 예측 페이지의 목록(최근 시리즈)과 다가오는 경기의 예상
  data/players.json         팀별 선수 시즌 평균
  data/patches.json         패치별로 공식 경기에서 많이 나온 챔피언

모든 예상은 "그 세트 이전 기록만으로" 낸 것이다.

흐름: 입력 읽기 → (입력이 그대로면 끝) → 밴픽 예측 → 승률 → 평점 → 경기별 파일 → 목록·검증 결과
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import champions, feedback, highlights, insights, ratings, youtube
from .agents.mock_draft import run_mock_draft
from .draft_model import (
    TOP_N,
    DraftModel,
    SetForecast,
    Weights,
    appear_rate,
    evaluate,
    meta_only,
    rank_hit_rates,
    recall,
    replay,
    tune,
)
from .gamedata import ROLES, SetRecord, load_sets, load_timelines
from .llm import LLM
from .schemas import Match
from .win_model import WinForecast, WinModel, walk_forward
from .win_model import report as win_report

VERSION = 4  # 산출물 형식이나 계산 방식이 바뀌면 올린다(다시 계산하게 됨)
TRAIN_SHARE = 0.6
MOCK_SERIES = 12  # 모의 밴픽을 만들어 둘 최근 시리즈 수
MOCK_LLM_SERIES = int(os.getenv("MOCK_LLM_SERIES", "3"))  # 그중 LLM 에이전트로 돌릴 수(한 시리즈에 21회 호출)
PATCHES_SHOWN = 6  # 패치별 메타를 보여 줄 최근 패치 수
RECENT_SERIES = 40  # 밴픽 예측 페이지에 보여 줄 최근 시리즈 수
CLIP_SAMPLES = 5  # 영상 위치 확인용으로 로그에 찍을 링크 수
MIN_PLAYER_SETS = 5  # 시즌 평균에 넣을 최소 세트 수

PlayerKey = tuple[int, str]  # (팀 ID, 선수 이름)
Ratings = dict[str, dict[PlayerKey, float]]  # 세트 ID → 선수별 평점


# ---- 입력 ----


@dataclass
class Inputs:
    """분석에 쓰는 입력을 한데 모은 것."""

    data_dir: Path
    llm: LLM | None
    sets: list[SetRecord]
    timelines: dict[str, Any]
    upcoming: list[Match]
    official: dict[int, str]  # 경기 ID → 주최 측이 그 경기에서 뽑은 선수
    videos: dict[str, Any]
    clips_on: bool
    name: Callable[[str], str]  # 챔피언 영어 이름 → 한국어 이름
    config: ratings.Config
    votes: list[dict[str, Any]]
    drafted: list[SetRecord] = field(init=False)
    series: dict[int, list[SetRecord]] = field(init=False)  # 경기 ID → 세트(순서대로)
    series_order: list[int] = field(init=False)  # 경기 ID, 오래된 것부터

    def __post_init__(self) -> None:
        self.drafted = [s for s in self.sets if s.draft]
        self.series = defaultdict(list)
        for s in self.sets:
            self.series[s.match_id].append(s)
        for group in self.series.values():
            group.sort(key=lambda s: s.number)
        self.series_order = sorted(self.series, key=lambda m: self.series[m][0].start)

    def fingerprint(self) -> str:
        """입력이 그대로면 다시 계산하지 않기 위한 지문."""
        h = hashlib.sha1()
        extra = (
            f"{len(self.videos)}:{self.clips_on}:{highlights.offset_sec()}:{self.name('Wukong')}"
            f":{self.config.digest()}:{feedback.digest(self.votes)}:{len(self.official)}"
            f":{sum(bool(s.official_mvp) for s in self.sets)}"
        )
        h.update(f"v{VERSION}|{self.llm.name if self.llm else 'policy'}|{extra}|".encode())
        for s in self.sets:
            h.update(
                f"{s.game_id}:{s.winner_id}:{len(s.draft)}:{len(s.players)}:{int(s.rpg in self.timelines)}|".encode()
            )
        for m in self.upcoming:
            h.update(f"{m.id}:{m.begin_at}|".encode())
        return h.hexdigest()[:16]


def _write_if_changed(path: Path, payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---- 밴픽 예측 ----


@dataclass
class DraftResult:
    weights: Weights
    model: DraftModel  # 모든 세트를 반영한 모델(다가오는 경기 예상용)
    by_game: dict[str, dict[int, SetForecast]]  # 세트 ID → 팀 ID → 세트 직전 예상
    rank_p: dict[str, list[float]]  # 예상 순위별 적중률(화면에 확률로 보여 주는 값)
    report: dict[str, Any]
    mocks: dict[int, dict[str, Any]]  # 경기 ID → 경기 전 모의 밴픽


def _draft_stage(inp: Inputs) -> DraftResult:
    """앞 구간에서 가중치를 고르고, 전체를 시간순으로 돌려 보며 세트마다 예상을 낸다."""
    weights = tune(inp.sets, TRAIN_SHARE)
    mock_targets = set(inp.series_order[-MOCK_SERIES:])
    llm_targets = set(inp.series_order[-MOCK_LLM_SERIES:]) if MOCK_LLM_SERIES > 0 else set()
    mocks: dict[int, dict[str, Any]] = {}

    def before_set(model: DraftModel, s: SetRecord) -> None:
        # 시리즈 첫 세트 직전의 모델 상태로 '경기 전 모의 밴픽'을 만든다.
        if s.number != 1 or s.match_id not in mock_targets or not s.first_pick_id:
            return
        old = (_read_json(inp.data_dir / "sets" / f"{s.match_id}.json") or {}).get("mock")
        if old and old.get("by") == "llm":  # LLM 이 이미 만든 것은 다시 부르지 않는다.
            mocks[s.match_id] = old
            return
        llm = inp.llm if s.match_id in llm_targets else None
        first, second = s.team(s.first_pick_id), s.other(s.first_pick_id)
        mocks[s.match_id] = run_mock_draft(model, llm, first, second, s.patch, name=inp.name)

    forecasts, model = replay(inp.sets, weights, before_set=before_set)
    by_game: dict[str, dict[int, SetForecast]] = defaultdict(dict)
    for f in forecasts:
        by_game[f.game_id][f.team_id] = f

    order = {s.game_id: i for i, s in enumerate(inp.drafted)}
    cut = int(len(inp.drafted) * TRAIN_SHARE)
    holdout = [f for f in forecasts if order[f.game_id] >= cut]
    rank_p = {"ban": rank_hit_rates(holdout, "ban"), "pick": rank_hit_rates(holdout, "pick")}
    drafted_by_game = {s.game_id: {step.champion for step in s.draft} for s in inp.drafted}

    def metrics(fs: list[SetForecast]) -> dict[str, Any]:
        return {
            "pick_appear_5": round(appear_rate(fs, "pick", 5, drafted_by_game), 3),
            "ban_appear_5": round(appear_rate(fs, "ban", 5, drafted_by_game), 3),
            "pick_hits_10": round(sum(f.hits("pick", 10) for f in fs) / len(fs), 2) if fs else 0.0,
            "ban_hits_10": round(sum(f.hits("ban", 10) for f in fs) / len(fs), 2) if fs else 0.0,
            "sets": len({f.game_id for f in fs}),
            "pick_recall_5": round(recall(fs, "pick", 5), 3),
            "pick_recall_10": round(recall(fs, "pick", 10), 3),
            "ban_recall_5": round(recall(fs, "ban", 5), 3),
            "ban_recall_10": round(recall(fs, "ban", 10), 3),
        }

    report = {
        "weights": weights.__dict__,
        "train_share": TRAIN_SHARE,
        "holdout": metrics(holdout),
        "holdout_set1": metrics([f for f in holdout if f.number == 1]),
        "holdout_later_sets": metrics([f for f in holdout if f.number > 1]),
        "baseline_meta_only": evaluate(inp.sets, meta_only(weights.meta_carry), start_at=TRAIN_SHARE),
        "rank_hit": rank_p,
    }
    print(
        f"[분석] 밴픽 예측 검증(뒤 {100 - int(TRAIN_SHARE * 100)}%): {report['holdout']}"
        f" / 기준선 {report['baseline_meta_only']}"
    )
    return DraftResult(weights, model, by_game, rank_p, report, mocks)


def _forecast_view(f: SetForecast, rank_p: dict[str, list[float]], drafted: set[str]) -> dict[str, Any]:
    """세트 직전 예상 하나를 화면용으로. hit: 이 팀이 실제로 그렇게 했다, seen: 어느 쪽이든 밴픽에 등장했다."""

    def rows(items: list[tuple[str, float]], actual: list[str], kind: str) -> list[dict[str, Any]]:
        hit = set(actual)
        p = rank_p[kind]
        return [
            {"champion": c, "p": p[i] if i < len(p) else 0.0, "hit": c in hit, "seen": c in drafted}
            for i, (c, _score) in enumerate(items[:TOP_N])
        ]

    return {
        "bans": rows(f.bans, f.actual_bans, "ban"),
        "picks": rows(f.picks, f.actual_picks, "pick"),
        "by_role": {role: [c for c, _ in items] for role, items in f.picks_by_role.items() if items},
        "ban_hits": f.hits("ban", TOP_N),
        "pick_hits": f.hits("pick", TOP_N),
    }


# ---- 평점 ----


@dataclass
class RatingResult:
    base: Ratings  # 세트 기록으로 계산한 평점
    fan: dict[str, dict[PlayerKey, tuple[float, int]]]  # 세트 ID → 선수 → (의견 평균, 의견 수)
    final: Ratings  # 계산 평점에 팬 의견을 일부 섞은 최종 평점

    @property
    def votes(self) -> int:
        return sum(count for players in self.fan.values() for _mean, count in players.values())

    @property
    def voted_lines(self) -> int:
        return sum(len(players) for players in self.fan.values())


def _rating_stage(inp: Inputs) -> RatingResult:
    scale = ratings.load_scale(inp.data_dir, inp.sets)
    base = {s.game_id: ratings.rate_set(s, scale, inp.config) for s in inp.sets} if scale else {}
    fan = feedback.aggregate(inp.votes, inp.sets)
    final = {
        game_id: {
            key: ratings.blend(value, *fan[game_id][key], inp.config.feedback) if key in fan.get(game_id, {}) else value
            for key, value in players.items()
        }
        for game_id, players in base.items()
    }
    return RatingResult(base, fan, final)


def _with_feedback(
    rows: list[dict[str, Any]],
    s: SetRecord,
    base: dict[PlayerKey, float],
    fan: dict[PlayerKey, tuple[float, int]],
) -> list[dict[str, Any]]:
    """팬 의견이 있는 선수 줄에 계산 평점과 의견 수를 덧붙인다."""
    for row in rows:
        for color, team in (("blue", s.blue), ("red", s.red)):
            key = (team.id, row[color]["player"])
            if key in fan:
                mean, count = fan[key]
                row[color] |= {"rating_base": base.get(key), "fan": round(mean, 1), "votes": count}
    return rows


def _series_ratings(series: list[SetRecord], rated: Ratings) -> list[dict[str, Any]]:
    """시리즈 평균 평점. 세트 절반 이상 뛴 선수만, 높은 순."""
    totals: dict[PlayerKey, list[float]] = defaultdict(list)
    role_of: dict[PlayerKey, str] = {}
    for s in series:
        for key, value in rated.get(s.game_id, {}).items():
            totals[key].append(value)
        role_of.update({(p.team_id, p.player): p.role for p in s.players})
    rows = [
        {
            "player": player,
            "team_id": team_id,
            "role": role_of.get((team_id, player), ""),
            "rating": round(sum(values) / len(values), 2),
            "sets": len(values),
        }
        for (team_id, player), values in totals.items()
        if len(values) * 2 >= len(series)
    ]
    return sorted(rows, key=lambda r: (-r["rating"], r["player"]))


def _official_agreement(official: dict[int, str], series: dict[int, list[SetRecord]], rated: Ratings) -> dict[str, Any]:
    """주최 측이 뽑은 선수와 이 사이트 평점이 얼마나 겹치는지.

    경기마다 이긴 팀 선수 다섯을 평균 평점 순으로 세워, 주최 측 선정 선수가 몇 번째인지 본다.
    아무렇게나 골라도 1위로 맞을 확률은 20% 다.
    """
    ranks: list[int] = []
    for match_id, chosen in official.items():
        sets = series.get(match_id)
        if not sets:
            continue
        wins: dict[int | None, int] = defaultdict(int)
        for s in sets:
            wins[s.winner_id] += 1
        winner = max(wins, key=lambda t: wins[t])
        totals: dict[str, list[float]] = defaultdict(list)
        for s in sets:
            for (team_id, player), value in rated.get(s.game_id, {}).items():
                if team_id == winner:
                    totals[player].append(value)
        order = [p.lower() for p in sorted(totals, key=lambda p: -sum(totals[p]) / len(totals[p]))]
        if chosen.lower() in order:
            ranks.append(order.index(chosen.lower()) + 1)
    n = len(ranks)
    return {
        "matches": n,
        "top1": round(sum(r == 1 for r in ranks) / n, 3) if n else None,
        "top2": round(sum(r <= 2 for r in ranks) / n, 3) if n else None,
        "mean_rank": round(sum(ranks) / n, 2) if n else None,
    }


# ---- 경기별 파일 ----


@dataclass
class MatchFileStats:
    timelines_verified: int = 0  # 참가자 순서가 스코어보드와 맞는 타임라인 수
    clip_sets: int = 0  # 영상 위치를 계산할 수 있는 세트 수
    clip_samples: list[str] = field(default_factory=list)  # 확인용 링크(로그용)


def _attach_clips(
    inp: Inputs, s: SetRecord, timeline: dict[str, Any], summary: dict[str, Any], stats: MatchFileStats
) -> None:
    """교전마다 영상 위치를 계산한다. 사이트에는 HIGHLIGHT_LINKS=1 일 때만 붙인다."""
    fights = summary["fights"]
    links = highlights.clip_links(timeline, fights, inp.videos)
    if not any(links):
        return
    stats.clip_sets += 1
    if len(stats.clip_samples) < CLIP_SAMPLES and s.number == 1:
        big = max(range(len(links)), key=lambda i: fights[i]["blue"] + fights[i]["red"])
        f = fights[big]
        when = f"{f['t'] // 60}:{f['t'] % 60:02d}"
        stats.clip_samples.append(
            f"{s.blue.acronym} vs {s.red.acronym} {s.number}세트 {when} {f['zone']} → {links[big]}"
        )
    if inp.clips_on:
        for f, link in zip(fights, links, strict=True):
            if link:
                f["clip"] = link


def _set_view(
    inp: Inputs,
    s: SetRecord,
    draft: DraftResult,
    win: WinForecast | None,
    rating: RatingResult,
    stats: MatchFileStats,
) -> dict[str, Any]:
    timeline = inp.timelines.get(s.rpg)
    summary = insights.set_summary(s, timeline)
    stats.timelines_verified += bool(summary.get("participants_ok"))
    if timeline and inp.videos:
        _attach_clips(inp, s, timeline, summary, stats)
    rated = rating.final.get(s.game_id, {})
    drafted = {step.champion for step in s.draft}
    return {
        "number": s.number,
        "patch": s.patch,
        "length_min": s.length_min,
        "blue": s.blue.model_dump(),
        "red": s.red.model_dump(),
        "winner_id": s.winner_id,
        "first_pick_id": s.first_pick_id,
        "draft": [step.model_dump() for step in s.draft],
        "stats": {"blue": s.blue_stats.model_dump(), "red": s.red_stats.model_dump()},
        "matchups": _with_feedback(
            insights.matchups(s, rated), s, rating.base.get(s.game_id, {}), rating.fan.get(s.game_id, {})
        ),
        # 주최 측이 세트마다 MVP 를 뽑는 대회에서의 세트 MVP
        "official_mvp": s.official_mvp,
        # 이긴 팀에서 평점이 가장 높은 선수(이 사이트가 뽑는 세트 최고 선수)
        "best": ratings.best_of(rated, s.winner_id),
        "summary": summary,
        "win": {"before": round(win.before_draft, 3), "after": round(win.after_draft, 3)} if win else None,
        "forecast": {
            str(team_id): _forecast_view(f, draft.rank_p, drafted)
            for team_id, f in draft.by_game.get(s.game_id, {}).items()
        },
    }


def _write_match_files(
    inp: Inputs, draft: DraftResult, wins: dict[str, WinForecast], rating: RatingResult
) -> tuple[bool, MatchFileStats]:
    """경기마다 data/sets/<경기 ID>.json 을 쓰고, 이제 없는 경기의 파일은 지운다."""
    stats = MatchFileStats()
    changed = False
    keep: set[str] = set()
    for match_id, series in inp.series.items():
        file_name = f"{match_id}.json"
        keep.add(file_name)
        payload = {
            "match_id": match_id,
            "sets": [_set_view(inp, s, draft, wins.get(s.game_id), rating, stats) for s in series],
            "mock": draft.mocks.get(match_id),
            "ratings": _series_ratings(series, rating.final),
        }
        changed |= _write_if_changed(inp.data_dir / "sets" / file_name, payload)
    for stale in (inp.data_dir / "sets").glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
            changed = True
    if inp.videos:
        shown = "켜짐" if inp.clips_on else "꺼짐"
        print(f"[분석] 영상 위치를 계산할 수 있는 세트 {stats.clip_sets}개 (사이트 노출: {shown})")
        for line in stats.clip_samples:
            print(f"[분석] 확인용 링크: {line}")
    return changed, stats


# ---- 목록과 검증 결과 ----


def _recent_series(inp: Inputs, draft: DraftResult) -> list[dict[str, Any]]:
    """밴픽 예측 페이지의 지난 시리즈 목록. 최근 것부터."""
    out = []
    for match_id in reversed(inp.series_order[-RECENT_SERIES:]):
        series = inp.series[match_id]
        fs = [f for s in series for f in draft.by_game.get(s.game_id, {}).values()]
        a, b = series[0].blue, series[0].red
        out.append(
            {
                "match_id": match_id,
                "league": series[0].league,
                "date": series[0].start,
                "team_a": a.model_dump(),
                "team_b": b.model_dump(),
                "score_a": sum(s.winner_id == a.id for s in series),
                "score_b": sum(s.winner_id == b.id for s in series),
                "sets": len(series),
                "ban_recall": round(recall(fs, "ban", TOP_N), 3),
                "pick_recall": round(recall(fs, "pick", TOP_N), 3),
                "has_mock": match_id in draft.mocks,
            }
        )
    return out


def _upcoming_forecasts(inp: Inputs, draft: DraftResult, win_model: WinModel) -> list[dict[str, Any]]:
    """다가오는 경기의 예상 밴픽과 모의 밴픽. 두 팀 모두 기록이 있는 경기만. 패치를 모르므로 가장 최근 패치 기준."""
    rank_p = draft.rank_p
    out = []
    for m in inp.upcoming:
        a, b = m.team_a, m.team_b
        if not (draft.model.knows(a.id) and draft.model.knows(b.id)):
            continue
        forecast = {}
        for team, opponent in ((a, b), (b, a)):
            p = draft.model.predict(team.id, opponent.id)
            forecast[str(team.id)] = {
                "bans": [{"champion": c, "p": rank_p["ban"][i]} for i, (c, _) in enumerate(p.bans)],
                "picks": [{"champion": c, "p": rank_p["pick"][i]} for i, (c, _) in enumerate(p.picks)],
                "by_role": {r: [c for c, _ in items] for r, items in p.picks_by_role.items() if items},
            }
        before, _after = win_model.probability(a.id, b.id, [], [])
        out.append(
            {
                "match_id": m.id,
                "team_a": a.model_dump(),
                "team_b": b.model_dump(),
                "begin_at": m.begin_at,
                "forecast": forecast,
                "mock": run_mock_draft(draft.model, inp.llm, a, b, None, name=inp.name),
                "win_before": round(before, 3),
            }
        )
    return out


def _player_table(inp: Inputs, rated: Ratings) -> dict[str, list[dict[str, Any]]]:
    """팀별 선수 시즌 평균. 포지션 순, 같은 포지션은 많이 뛴 선수부터."""
    averages = insights.player_averages(inp.sets, rated)

    def order(item: tuple[PlayerKey, dict[str, Any]]) -> tuple[int, int]:
        stats = item[1]
        return (ROLES.index(stats["role"]) if stats["role"] in ROLES else len(ROLES), -stats["sets"])

    table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (team_id, player), stats in sorted(averages.items(), key=order):
        if stats["sets"] >= MIN_PLAYER_SETS:
            table[str(team_id)].append({"player": player, **stats})
    return table


def _patch_table(inp: Inputs, model: DraftModel) -> list[dict[str, Any]]:
    """패치별 메타: 그 패치가 적용된 공식 경기에서 많이 나온 챔피언. 최근 패치부터."""
    out = []
    for patch in reversed(model.patches[-PATCHES_SHOWN:]):
        sets = [s for s in inp.drafted if s.patch == patch]
        out.append(
            {
                **model.patch_meta(patch),
                "from": min(s.start[:10] for s in sets),
                "to": max(s.start[:10] for s in sets),
                "leagues": sorted({s.league for s in sets}),
            }
        )
    return out


# ---- 진입점 ----


def build(
    data_dir: Path,
    llm: LLM | None = None,
    upcoming: list[Match] | None = None,
    *,
    matches: list[Match] | None = None,
    sets: list[SetRecord] | None = None,
    timelines: dict[str, Any] | None = None,
) -> bool:
    """분석 파일을 만든다. 바뀐 파일이 하나라도 있으면 True. 세트 기록이 없으면 아무것도 하지 않는다."""
    sets = load_sets(data_dir) if sets is None else sets
    if not any(s.draft for s in sets):
        return False
    videos = youtube.load_videos(data_dir)
    inp = Inputs(
        data_dir=data_dir,
        llm=llm,
        sets=sets,
        timelines=load_timelines(data_dir) if timelines is None else timelines,
        upcoming=upcoming or [],
        official={m.id: m.mvp for m in matches or [] if m.mvp},
        videos=videos,
        clips_on=highlights.enabled() and bool(videos),
        name=champions.namer(data_dir),
        config=ratings.load_config(),
        votes=feedback.load_votes(data_dir),
    )
    fingerprint = inp.fingerprint()
    if (_read_json(data_dir / "models.json") or {}).get("input") == fingerprint:
        print("[분석] 입력이 그대로라 건너뜀")
        return False
    timeline_count = sum(1 for s in sets if s.rpg in inp.timelines)
    print(f"[분석] 세트 {len(sets)}개 (밴픽 기록 {len(inp.drafted)}, 타임라인 {timeline_count})")

    draft = _draft_stage(inp)
    win_forecasts, win_model = walk_forward(sets)
    win_scores = win_report(win_forecasts)
    print(f"[분석] 승률 검증: {win_scores}")
    rating = _rating_stage(inp)

    changed, stats = _write_match_files(inp, draft, {f.game_id: f for f in win_forecasts}, rating)
    changed |= _write_if_changed(data_dir / "players.json", _player_table(inp, rating.final))
    changed |= _write_if_changed(data_dir / "patches.json", _patch_table(inp, draft.model))
    changed |= _write_if_changed(
        data_dir / "draft.json",
        {"recent": _recent_series(inp, draft), "upcoming": _upcoming_forecasts(inp, draft, win_model)},
    )
    changed |= _write_if_changed(
        data_dir / "models.json",
        {
            "draft": draft.report,
            "win": {
                "report": win_scores,
                "coef": [round(c, 4) for c in win_model.coef_full],
                "features": ["전력 차", "조합 차", "숙련 차"],
            },
            "counts": {
                "sets": len(sets),
                "drafted": len(inp.drafted),
                "timelines": timeline_count,
                "timelines_verified": stats.timelines_verified,
                "series": len(inp.series),
                "clip_sets": stats.clip_sets,
            },
            "clips": inp.clips_on,
            "ratings": {
                "official": _official_agreement(inp.official, inp.series, rating.final),
                "votes": rating.votes,
                "voted_lines": rating.voted_lines,
                "feedback": inp.config.feedback.__dict__,
            },
            "input": fingerprint,
            "mock_by": "llm" if any(m.get("by") == "llm" for m in draft.mocks.values()) else "policy",
        },
    )
    return changed


def extra_facts(sets: list[SetRecord], timelines: dict[str, Any]) -> dict[int, list[str]]:
    """경기 브리핑의 근거로 덧붙일 세트별 사실. 키는 경기 ID."""
    out: dict[int, list[str]] = defaultdict(list)
    for s in sets:
        b, r = s.blue_stats, s.red_stats
        if not (b.kills or r.kills):
            continue
        line = (
            f"{s.number}세트 {s.blue.acronym}(블루) 대 {s.red.acronym}(레드): 킬 {b.kills}-{r.kills}, "
            f"드래곤 {b.dragons}-{r.dragons}, 바론 {b.barons}-{r.barons}, 타워 {b.towers}-{r.towers}"
        )
        timeline = timelines.get(s.rpg)
        if timeline:
            fs = insights.fights(timeline)
            blue_won = sum(f["winner"] == "blue" for f in fs)
            red_won = sum(f["winner"] == "red" for f in fs)
            line += f", 교전 {len(fs)}회({s.blue.acronym} 우세 {blue_won}, {s.red.acronym} 우세 {red_won})"
        out[s.match_id].append(line)
    return out
