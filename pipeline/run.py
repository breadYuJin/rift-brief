"""파이프라인 진입점: `python -m pipeline.run`"""
from __future__ import annotations

import sys

from .archive import ArchiveSource
from .config import Settings
from .facts import form_text
from .graphs import build_brief_graph, build_preview_graph
from .leagues import build_league, make_ranker
from .llm import get_llm
from .pandascore import PandaScoreClient
from .sample import SampleSource
from .schemas import BriefRecord, LeagueFeed, Match, PreviewRecord
from .store import Store


class LiveSource:
    """PandaScore 클라이언트를 파이프라인이 쓰는 형태로 감싼다."""

    def __init__(self, settings: Settings):
        self._client = PandaScoreClient(settings.pandascore_token)
        if settings.league_ids:
            self._leagues = [(i, self._client.league_name(i)) for i in settings.league_ids]
        else:
            self._leagues = self._client.resolve_leagues(settings.league_names)
        if not self._leagues:
            raise RuntimeError("조회할 리그를 하나도 찾지 못했습니다. LEAGUES 또는 PANDASCORE_LEAGUE_IDS 를 확인하세요.")

    def leagues(self) -> list[LeagueFeed]:
        return [
            LeagueFeed(id=league_id, name=name, matches=self._client.league_matches(league_id))
            for league_id, name in self._leagues
        ]

    def team_matches(self, team_id: int) -> list[Match]:
        return self._client.team_matches(team_id)


def _same_fixture(a: Match, b: Match) -> bool:
    return (a.id, a.begin_at, a.team_a.id, a.team_b.id) == (b.id, b.begin_at, b.team_a.id, b.team_b.id)


def main() -> int:
    settings = Settings()
    store = Store(settings.data_dir)
    mode = settings.mode
    if mode == "live":
        source = LiveSource(settings)
    elif mode == "archive":
        source = ArchiveSource(settings.archive_dir)
    else:
        source = SampleSource()
    source_note = getattr(source, "note", "")
    llm = get_llm(settings.llm_model)
    label = {"live": "PandaScore", "archive": f"시즌 기록({source_note})", "sample": "샘플"}[mode]
    print(f"[run] 데이터: {label} / 작성: {llm.name if llm else '템플릿'}")

    # 샘플은 매번 새로 만든다. 데이터 소스가 바뀌면 경기 ID 체계가 달라지므로 기존 기록을 버린다.
    keep_existing = mode != "sample" and store.meta.get("source") == mode
    # 시즌 기록은 한 해 전체를 브리핑으로 만든다.
    past_limit = settings.past_limit if mode == "live" else 5000
    archive_size = settings.archive_size if mode == "live" else 5000
    results = {r.match.id: r for r in store.load_results()} if keep_existing else {}
    old_previews = {p.match.id: p for p in store.load_previews()} if keep_existing else {}

    feeds = source.leagues()
    leagues = [build_league(feed) for feed in feeds]
    ranker = make_ranker(leagues)
    for league in leagues:
        print(f"[리그] {league.name} {league.serie}: {league.status}, 경기 {len(league.matches)}건")

    every = [m for feed in feeds for m in feed.matches]
    past = sorted(
        (m for m in every if m.status == "finished" and m.winner_id), key=lambda m: m.end_at or "", reverse=True
    )[:past_limit]
    upcoming = sorted((m for m in every if m.status == "not_started" and m.begin_at), key=lambda m: m.begin_at or "")[
        : settings.upcoming_limit
    ]

    if mode == "archive":
        # 시즌 기록을 다시 정리하면 팀 이름·스테이지가 바뀔 수 있다. 경기 내용이 그대로인 브리핑만 재사용한다.
        current = {m.id: m for m in every}
        results = {i: r for i, r in results.items() if current.get(i) == r.match}

    brief_graph = build_brief_graph(llm, source, settings.max_rewrites, ranker)
    new_briefs = 0
    for match in past:
        if match.id in results:
            continue
        try:
            out = brief_graph.invoke({"match": match})
            ctx = out["context"]
            results[match.id] = BriefRecord(
                match=match,
                recent_a=[e.won for e in ctx.form_a.recent],
                recent_b=[e.won for e in ctx.form_b.recent],
                headline=out["draft"].headline,
                summary=out["draft"].summary,
                tags=out["tags"],
                facts=out["facts"],
                importance=out["importance"],
                reasons=out["reasons"],
                generated_by=out["generated_by"],
                trace=out["trace"],
            )
            new_briefs += 1
            if new_briefs <= 20:
                print(f"[브리핑] {match.team_a.acronym} vs {match.team_b.acronym}: {out['draft'].headline}")
        except Exception as exc:
            print(f"[브리핑] 경기 {match.id} 처리 실패: {exc}")

    preview_graph = build_preview_graph(llm, source, ranker)
    previews: list[PreviewRecord] = []
    new_previews = 0
    for match in upcoming:
        old = old_previews.get(match.id)
        if old and _same_fixture(old.match, match):
            previews.append(old)
            continue
        try:
            out = preview_graph.invoke({"match": match})
            ctx = out["context"]
            previews.append(
                PreviewRecord(
                    match=match,
                    recent_a=[e.won for e in ctx.form_a.recent],
                    recent_b=[e.won for e in ctx.form_b.recent],
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
            )
            new_previews += 1
            print(f"[프리뷰] {match.team_a.acronym} vs {match.team_b.acronym}")
        except Exception as exc:
            print(f"[프리뷰] 경기 {match.id} 처리 실패: {exc}")

    changed = store.save(
        list(results.values()),
        previews,
        leagues,
        sample=mode == "sample",
        source=mode,
        source_note=source_note,
        llm_name=llm.name if llm else "template",
        archive_size=archive_size,
    )
    print(f"[run] 새 브리핑 {new_briefs}건, 새 프리뷰 {new_previews}건, 데이터 변경: {'있음' if changed else '없음'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
