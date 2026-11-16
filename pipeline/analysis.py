"""세트 기록으로 예측·분석 결과를 만들어 사이트용 파일로 내보낸다.

  data/sets/<경기 ID>.json  세트별 밴픽, 세트 직전 예상과 적중, 승률, 교전·오브젝트·동선, 선수 맞대결
  data/models.json          밴픽 예측과 승률 모델의 검증 결과
  data/draft.json           밴픽 예측 페이지의 목록(최근 시리즈)과 다가오는 경기의 예상
  data/players.json         팀별 선수 시즌 평균

모든 예상은 "그 세트 이전 기록만으로" 낸 것이다.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import highlights, insights, youtube
from .agents.mock_draft import run_mock_draft
from .draft_model import TOP_N, DraftModel, SetForecast, appear_rate, evaluate, meta_only, rank_hit_rates, recall, replay, tune
from .gamedata import ROLES, SetRecord, load_sets, load_timelines
from .llm import LLM
from .schemas import Match, Team
from .win_model import report as win_report
from .win_model import walk_forward

VERSION = 2  # 산출물 형식이나 계산 방식이 바뀌면 올린다(다시 계산하게 됨)
TRAIN_SHARE = 0.6
MOCK_SERIES = 12  # 모의 밴픽을 만들어 둘 최근 시리즈 수
MOCK_LLM_SERIES = int(os.getenv("MOCK_LLM_SERIES", "3"))  # 그중 LLM 에이전트로 돌릴 수(한 시리즈에 21회 호출)
RECENT_SERIES = 40


def _write_if_changed(path: Path, payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _forecast_view(f: SetForecast, rank_p: dict[str, list[float]], drafted: set[str]) -> dict[str, Any]:
    def rows(items: list[tuple[str, float]], actual: list[str], kind: str) -> list[dict[str, Any]]:
        hit = set(actual)
        return [
            # hit: 이 팀이 실제로 그렇게 했다 / seen: 어느 쪽이든 이 세트 밴픽에 등장했다
            {"champion": c, "p": rank_p[kind][i] if i < len(rank_p[kind]) else 0.0, "hit": c in hit, "seen": c in drafted}
            for i, (c, _score) in enumerate(items[:TOP_N])
        ]

    return {
        "bans": rows(f.bans, f.actual_bans, "ban"),
        "picks": rows(f.picks, f.actual_picks, "pick"),
        "by_role": {role: [c for c, _ in items] for role, items in f.picks_by_role.items() if items},
        "ban_hits": f.hits("ban", TOP_N),
        "pick_hits": f.hits("pick", TOP_N),
    }


def _fingerprint(sets: list[SetRecord], timelines: dict[str, Any], llm: LLM | None, upcoming: list[Match], extra: str = "") -> str:
    """입력이 그대로면 다시 계산하지 않기 위한 지문."""
    h = hashlib.sha1()
    h.update(f"v{VERSION}|{llm.name if llm else 'policy'}|{extra}|".encode())
    for s in sets:
        h.update(f"{s.game_id}:{s.winner_id}:{len(s.draft)}:{len(s.players)}:{int(s.rpg in timelines)}|".encode())
    for m in upcoming:
        h.update(f"{m.id}:{m.begin_at}|".encode())
    return h.hexdigest()[:16]


def _old_mock(data_dir: Path, match_id: int) -> dict[str, Any] | None:
    path = data_dir / "sets" / f"{match_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("mock")
    except (OSError, ValueError):
        return None


def build(
    data_dir: Path,
    llm: LLM | None = None,
    upcoming: list[Match] | None = None,
    *,
    sets: list[SetRecord] | None = None,
    timelines: dict[str, Any] | None = None,
) -> bool:
    """분석 파일을 만든다. 바뀐 파일이 하나라도 있으면 True. 세트 기록이 없으면 아무것도 하지 않는다."""
    sets = load_sets(data_dir) if sets is None else sets
    drafted = [s for s in sets if s.draft]
    if not drafted:
        return False
    timelines = load_timelines(data_dir) if timelines is None else timelines
    upcoming = upcoming or []
    videos = youtube.load_videos(data_dir)
    clips_on = highlights.enabled() and bool(videos)
    fingerprint = _fingerprint(sets, timelines, llm, upcoming, f"{len(videos)}:{clips_on}:{highlights.offset_sec()}")
    try:
        if json.loads((data_dir / "models.json").read_text(encoding="utf-8")).get("input") == fingerprint:
            print("[분석] 입력이 그대로라 건너뜀")
            return False
    except (OSError, ValueError):
        pass
    print(f"[분석] 세트 {len(sets)}개 (밴픽 기록 {len(drafted)}, 타임라인 {sum(1 for s in sets if s.rpg in timelines)})")

    # ---- 밴픽 예측: 앞 구간에서 가중치를 고르고, 전체를 시간순으로 돌려 본다 ----
    weights = tune(sets, TRAIN_SHARE)
    by_series: dict[int, list[SetRecord]] = defaultdict(list)
    for s in sets:
        by_series[s.match_id].append(s)
    series_order = sorted(by_series, key=lambda m: by_series[m][0].start)
    mock_targets = set(series_order[-MOCK_SERIES:])
    mocks: dict[int, dict[str, Any]] = {}

    llm_targets = set(series_order[-MOCK_LLM_SERIES:])

    def before_set(model: DraftModel, s: SetRecord) -> None:
        # 시리즈 첫 세트 직전의 모델 상태로 '경기 전 모의 밴픽'을 만든다.
        if s.number != 1 or s.match_id not in mock_targets or not s.first_pick_id:
            return
        old = _old_mock(data_dir, s.match_id)
        if old and old.get("by") == "llm":  # LLM 이 이미 만든 것은 다시 부르지 않는다.
            mocks[s.match_id] = old
            return
        first, second = s.team(s.first_pick_id), s.other(s.first_pick_id)
        use = llm if s.match_id in llm_targets else None
        mocks[s.match_id] = run_mock_draft(model, use, first, second, s.start)

    forecasts, draft_model = replay(sets, weights, before_set=before_set)
    order = {s.game_id: i for i, s in enumerate(drafted)}
    cut = int(len(drafted) * TRAIN_SHARE)
    holdout = [f for f in forecasts if order[f.game_id] >= cut]
    rank_p = {"ban": rank_hit_rates(holdout, "ban"), "pick": rank_hit_rates(holdout, "pick")}

    drafted_by_game = {s.game_id: {step.champion for step in s.draft} for s in drafted}

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

    draft_report = {
        "weights": weights.__dict__,
        "train_share": TRAIN_SHARE,
        "holdout": metrics(holdout),
        "holdout_set1": metrics([f for f in holdout if f.number == 1]),
        "holdout_later_sets": metrics([f for f in holdout if f.number > 1]),
        "baseline_meta_only": evaluate(sets, meta_only(tau_meta=weights.tau_meta), start_at=TRAIN_SHARE),
        "rank_hit": rank_p,
    }
    print(f"[분석] 밴픽 예측 검증(뒤 {100 - int(TRAIN_SHARE * 100)}%): {draft_report['holdout']} / 기준선 {draft_report['baseline_meta_only']}")

    # ---- 승률 ----
    win_forecasts, win_model = walk_forward(sets)
    win_by_game = {f.game_id: f for f in win_forecasts}
    wins = win_report(win_forecasts)
    print(f"[분석] 승률 검증: {wins}")

    # ---- 경기별 파일 ----
    forecast_by_game: dict[str, dict[int, SetForecast]] = defaultdict(dict)
    for f in forecasts:
        forecast_by_game[f.game_id][f.team_id] = f
    averages = insights.player_averages(sets)
    changed = False
    timeline_ok = 0
    clip_sets = 0
    clip_samples: list[str] = []
    keep: set[str] = set()
    for match_id, series in by_series.items():
        out_sets = []
        for s in sorted(series, key=lambda s: s.number):
            timeline = timelines.get(s.rpg)
            summary = insights.set_summary(s, timeline)
            timeline_ok += bool(summary.get("participants_ok"))
            if timeline and videos:
                links = highlights.clip_links(timeline, summary["fights"], videos)
                clip_sets += any(links)
                if any(links) and len(clip_samples) < 5 and s.number == 1:
                    big = max(range(len(links)), key=lambda i: summary["fights"][i]["blue"] + summary["fights"][i]["red"])
                    f = summary["fights"][big]
                    clip_samples.append(f"{s.blue.acronym} vs {s.red.acronym} {s.number}세트 {f['t'] // 60}:{f['t'] % 60:02d} {f['zone']} → {links[big]}")
                if clips_on:
                    for f, link in zip(summary["fights"], links):
                        if link:
                            f["clip"] = link
            win = win_by_game.get(s.game_id)
            out_sets.append(
                {
                    "number": s.number,
                    "patch": s.patch,
                    "length_min": s.length_min,
                    "blue": s.blue.model_dump(),
                    "red": s.red.model_dump(),
                    "winner_id": s.winner_id,
                    "first_pick_id": s.first_pick_id,
                    "draft": [step.model_dump() for step in s.draft],
                    "stats": {"blue": s.blue_stats.model_dump(), "red": s.red_stats.model_dump()},
                    "matchups": insights.matchups(s),
                    "summary": summary,
                    "win": {"before": round(win.before_draft, 3), "after": round(win.after_draft, 3)} if win else None,
                    "forecast": {
                        str(t): _forecast_view(f, rank_p, drafted_by_game.get(s.game_id, set()))
                        for t, f in forecast_by_game.get(s.game_id, {}).items()
                    },
                }
            )
        name = f"{match_id}.json"
        keep.add(name)
        changed |= _write_if_changed(
            data_dir / "sets" / name,
            {"match_id": match_id, "sets": out_sets, "mock": mocks.get(match_id)},
        )
    for stale in (data_dir / "sets").glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
            changed = True

    if videos:
        print(f"[분석] 영상 위치를 계산할 수 있는 세트 {clip_sets}개 (사이트 노출: {'켜짐' if clips_on else '꺼짐'})")
        for line in clip_samples:
            print(f"[분석] 확인용 링크: {line}")

    # ---- 목록과 검증 결과 ----
    recent = []
    for match_id in reversed(series_order[-RECENT_SERIES:]):
        series = sorted(by_series[match_id], key=lambda s: s.number)
        fs = [f for s in series for f in forecast_by_game.get(s.game_id, {}).values()]
        a, b = series[0].blue, series[0].red
        recent.append(
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
                "has_mock": match_id in mocks,
            }
        )

    upcoming_out = []
    for m in upcoming:
        a, b = m.team_a, m.team_b
        if not (draft_model.knows(a.id) and draft_model.knows(b.id)):
            continue
        when = m.begin_at or ""
        before, _after = win_model.probability(a.id, b.id, [], [])
        upcoming_out.append(
            {
                "match_id": m.id,
                "team_a": a.model_dump(),
                "team_b": b.model_dump(),
                "begin_at": m.begin_at,
                "forecast": {
                    str(t.id): {
                        "bans": [{"champion": c, "p": rank_p["ban"][i]} for i, (c, _) in enumerate(p.bans)],
                        "picks": [{"champion": c, "p": rank_p["pick"][i]} for i, (c, _) in enumerate(p.picks)],
                        "by_role": {r: [c for c, _ in items] for r, items in p.picks_by_role.items() if items},
                    }
                    for t, o in ((a, b), (b, a))
                    for p in [draft_model.predict(t.id, o.id, when)]
                },
                "mock": run_mock_draft(draft_model, llm, a, b, when),
                "win_before": round(before, 3),
            }
        )

    players: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (team_id, name), stats in sorted(averages.items(), key=lambda kv: (ROLES.index(kv[1]["role"]) if kv[1]["role"] in ROLES else 9, -kv[1]["sets"])):
        if stats["sets"] >= 5:
            players[str(team_id)].append({"player": name, **stats})
    changed |= _write_if_changed(data_dir / "players.json", players)
    changed |= _write_if_changed(data_dir / "draft.json", {"recent": recent, "upcoming": upcoming_out})
    changed |= _write_if_changed(
        data_dir / "models.json",
        {
            "draft": draft_report,
            "win": {"report": wins, "coef": [round(c, 4) for c in win_model.coef_full], "features": ["전력 차", "조합 차", "숙련 차"]},
            "counts": {
                "sets": len(sets),
                "drafted": len(drafted),
                "timelines": sum(1 for s in sets if s.rpg in timelines),
                "timelines_verified": timeline_ok,
                "series": len(by_series),
                "clip_sets": clip_sets,
            },
            "clips": clips_on,
            "input": fingerprint,
            "mock_by": "llm" if any(m.get("by") == "llm" for m in mocks.values()) else "policy",
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
