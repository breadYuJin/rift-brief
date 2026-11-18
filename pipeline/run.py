"""파이프라인 진입점: `python -m pipeline.run`

데이터 소스 고르기 → 리그 집계 → 끝난 경기 브리핑 → 예정 경기 프리뷰 → 저장 → 상 잇기 → 분석
"""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import Any

from . import analysis, awards
from .archive import ArchiveSource
from .config import Settings
from .facts import form_text
from .gamedata import SetRecord, load_sets, load_timelines
from .graphs import build_brief_graph, build_preview_graph
from .leagues import build_league, make_ranker
from .llm import LLM, get_llm
from .pandascore import PandaScoreClient
from .sample import SampleSource
from .schemas import BriefRecord, Context, LeagueFeed, Match, PreviewRecord
from .store import Store

FULL_SEASON = 5000  # archive·sample 모드에서는 시즌 전체를 브리핑으로 만든다
LOGGED_BRIEFS = 20  # 로그에 헤드라인을 찍을 최대 수


class LiveSource:
    """PandaScore 클라이언트를 파이프라인이 쓰는 형태로 감싼다."""

    note = ""

    def __init__(self, settings: Settings):
        self._client = PandaScoreClient(settings.pandascore_token)
        if settings.league_ids:
            self._leagues = [(i, self._client.league_name(i)) for i in settings.league_ids]
        else:
            self._leagues = self._client.resolve_leagues(settings.league_names)
        if not self._leagues:
            raise RuntimeError(
                "조회할 리그를 하나도 찾지 못했습니다. LEAGUES 또는 PANDASCORE_LEAGUE_IDS 를 확인하세요."
            )

    def leagues(self) -> list[LeagueFeed]:
        return [
            LeagueFeed(id=league_id, name=name, matches=self._client.league_matches(league_id))
            for league_id, name in self._leagues
        ]

    def team_matches(self, team_id: int) -> list[Match]:
        return self._client.team_matches(team_id)


Source = LiveSource | ArchiveSource | SampleSource


def _open_source(settings: Settings) -> Source:
    if settings.mode == "live":
        return LiveSource(settings)
    if settings.mode == "archive":
        return ArchiveSource(settings.archive_dir)
    return SampleSource()


def _same_fixture(a: Match, b: Match) -> bool:
    return (a.id, a.begin_at, a.team_a.id, a.team_b.id) == (b.id, b.begin_at, b.team_a.id, b.team_b.id)


def _recent(ctx: Context) -> tuple[list[bool], list[bool]]:
    return [e.won for e in ctx.form_a.recent], [e.won for e in ctx.form_b.recent]


def _brief_record(match: Match, out: dict[str, Any]) -> BriefRecord:
    recent_a, recent_b = _recent(out["context"])
    return BriefRecord(
        match=match,
        recent_a=recent_a,
        recent_b=recent_b,
        headline=out["draft"].headline,
        summary=out["draft"].summary,
        tags=out["tags"],
        facts=out["facts"],
        importance=out["importance"],
        reasons=out["reasons"],
        generated_by=out["generated_by"],
        trace=out["trace"],
    )


def _preview_record(match: Match, out: dict[str, Any]) -> PreviewRecord:
    ctx: Context = out["context"]
    recent_a, recent_b = _recent(ctx)
    return PreviewRecord(
        match=match,
        recent_a=recent_a,
        recent_b=recent_b,
        form_a=form_text(ctx.form_a),
        form_b=form_text(ctx.form_b),
        h2h=f"{ctx.h2h_a_wins}승 {ctx.h2h_b_wins}패" if ctx.h2h_a_wins or ctx.h2h_b_wins else "기록 없음",
        case_a=out["case_a"],
        case_b=out["case_b"],
        watch_points=out["watch_points"],
        importance=out["importance"],
        reasons=out["reasons"],
        generated_by=out["generated_by"],
        trace=out["trace"],
    )


def _set_facts(matches: list[Match], sets: list[SetRecord], timelines: dict[str, Any]) -> dict[int, list[str]]:
    """브리핑 근거에 덧붙일 사실: 세트별 킬·오브젝트·교전 기록과 주최 측이 그 경기에서 뽑은 선수."""
    facts: dict[int, list[str]] = defaultdict(list, analysis.extra_facts(sets, timelines))
    for m in matches:
        if m.mvp:
            facts[m.id].append(f"주최 측 선정 선수: {m.mvp}")
    return facts


def _write_briefs(graph: Any, matches: list[Match], results: dict[int, BriefRecord]) -> int:
    """아직 브리핑이 없는 끝난 경기마다 브리핑 그래프를 돌린다. 새로 만든 수를 돌려준다."""
    made = 0
    for match in matches:
        if match.id in results:
            continue
        try:
            out = graph.invoke({"match": match})
        except Exception as exc:  # 한 경기가 실패해도 나머지는 계속한다.
            print(f"[브리핑] 경기 {match.id} 처리 실패: {exc}")
            continue
        results[match.id] = _brief_record(match, out)
        made += 1
        if made <= LOGGED_BRIEFS:
            print(f"[브리핑] {match.team_a.acronym} vs {match.team_b.acronym}: {out['draft'].headline}")
    return made


def _write_previews(graph: Any, matches: list[Match], old: dict[int, PreviewRecord]) -> tuple[list[PreviewRecord], int]:
    """예정 경기마다 프리뷰를 만든다. 대진·시각이 그대로인 경기는 지난 프리뷰를 그대로 쓴다."""
    previews: list[PreviewRecord] = []
    made = 0
    for match in matches:
        kept = old.get(match.id)
        if kept and _same_fixture(kept.match, match):
            previews.append(kept)
            continue
        try:
            out = graph.invoke({"match": match})
        except Exception as exc:
            print(f"[프리뷰] 경기 {match.id} 처리 실패: {exc}")
            continue
        previews.append(_preview_record(match, out))
        made += 1
        print(f"[프리뷰] {match.team_a.acronym} vs {match.team_b.acronym}")
    return previews, made


def main() -> int:
    settings = Settings()
    store = Store(settings.data_dir)
    mode = settings.mode
    source = _open_source(settings)
    llm: LLM | None = get_llm(settings.llm_model)
    label = {"live": "PandaScore", "archive": f"시즌 기록({source.note})", "sample": "샘플"}[mode]
    print(f"[run] 데이터: {label} / 작성: {llm.name if llm else '템플릿'}")

    # 샘플은 매번 새로 만든다. 데이터 소스가 바뀌면 경기 ID 체계가 달라지므로 기존 기록을 버린다.
    keep_existing = mode != "sample" and store.meta.get("source") == mode
    results = {r.match.id: r for r in store.load_results()} if keep_existing else {}
    old_previews = {p.match.id: p for p in store.load_previews()} if keep_existing else {}

    feeds = source.leagues()
    leagues = [build_league(feed) for feed in feeds]
    ranker = make_ranker(leagues)
    for league in leagues:
        print(f"[리그] {league.name} {league.serie}: {league.status}, 경기 {len(league.matches)}건")

    every = [m for feed in feeds for m in feed.matches]
    past_limit = settings.past_limit if mode == "live" else FULL_SEASON
    past = sorted(
        (m for m in every if m.status == "finished" and m.winner_id), key=lambda m: m.end_at or "", reverse=True
    )[:past_limit]
    upcoming = sorted((m for m in every if m.status == "not_started" and m.begin_at), key=lambda m: m.begin_at or "")
    upcoming = upcoming[: settings.upcoming_limit]

    # 세트 상세 기록(밴픽·오브젝트·타임라인)은 수집해 둔 원본이 있을 때만 쓴다.
    sets = load_sets(settings.data_dir) if mode != "sample" else []
    timelines = load_timelines(settings.data_dir) if sets else {}
    extra = _set_facts(every, sets, timelines) if mode == "archive" else {}
    if mode == "archive":
        # 시즌 기록을 다시 정리하면 팀 이름·스테이지가 바뀔 수 있다. 경기 내용이 그대로이고
        # 세트 기록도 이미 반영된 브리핑만 재사용한다.
        current = {m.id: m for m in every}
        results = {
            i: r
            for i, r in results.items()
            if current.get(i) == r.match and all(f in r.facts for f in extra.get(i, []))
        }

    new_briefs = _write_briefs(build_brief_graph(llm, source, settings.max_rewrites, ranker, extra), past, results)
    previews, new_previews = _write_previews(build_preview_graph(llm, source, ranker), upcoming, old_previews)

    changed = store.save(
        list(results.values()),
        previews,
        leagues,
        sample=mode == "sample",
        source=mode,
        source_note=source.note,
        llm_name=llm.name if llm else "template",
        archive_size=settings.archive_size if mode == "live" else FULL_SEASON,
    )
    print(f"[run] 새 브리핑 {new_briefs}건, 새 프리뷰 {new_previews}건, 데이터 변경: {'있음' if changed else '없음'}")

    if mode == "archive":
        awards.save(settings.data_dir, every)  # 대회 종료 후 따로 발표되는 상(파이널 MVP 등)을 결승 경기에 잇는다
    if sets:
        try:
            analysis.build(
                settings.data_dir,
                llm,
                upcoming if mode == "archive" else [],
                matches=every,
                sets=sets,
                timelines=timelines,
            )
        except Exception as exc:  # 분석이 실패해도 브리핑은 이미 저장됐다.
            print(f"[분석] 실패: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
