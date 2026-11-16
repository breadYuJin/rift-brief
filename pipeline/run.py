"""파이프라인 진입점: `python -m pipeline.run`"""
from __future__ import annotations

import sys

from .config import Settings
from .graphs import build_brief_graph, build_preview_graph
from .facts import form_text
from .llm import get_llm
from .pandascore import PandaScoreClient
from .sample import SampleSource
from .schemas import BriefRecord, Match, PreviewRecord
from .store import Store


class LiveSource:
    """PandaScore 클라이언트를 파이프라인이 쓰는 형태로 감싼다."""

    def __init__(self, settings: Settings):
        self._client = PandaScoreClient(settings.pandascore_token)
        self._settings = settings
        self._league_ids = settings.league_ids or self._client.resolve_league_ids(settings.league_names)
        if not self._league_ids:
            raise RuntimeError("조회할 리그를 하나도 찾지 못했습니다. LEAGUES 또는 PANDASCORE_LEAGUE_IDS 를 확인하세요.")

    def past_matches(self) -> list[Match]:
        return self._client.past_matches(self._league_ids, self._settings.past_limit)

    def upcoming_matches(self) -> list[Match]:
        return self._client.upcoming_matches(self._league_ids, self._settings.upcoming_limit)

    def team_matches(self, team_id: int) -> list[Match]:
        return self._client.team_matches(team_id)


def _same_fixture(a: Match, b: Match) -> bool:
    return (a.id, a.begin_at, a.team_a.id, a.team_b.id) == (b.id, b.begin_at, b.team_a.id, b.team_b.id)


def main() -> int:
    settings = Settings()
    store = Store(settings.data_dir)
    source = SampleSource() if settings.sample_mode else LiveSource(settings)
    llm = get_llm(settings.llm_model)
    print(f"[run] 데이터: {'샘플' if settings.sample_mode else 'PandaScore'} / 작성: {llm.name if llm else '템플릿'}")

    # 샘플 데이터는 매번 새로 만들고, 샘플 → 실데이터 전환 시에는 기존 기록을 버린다.
    keep_existing = not settings.sample_mode and store.meta.get("sample") is False
    results = {r.match.id: r for r in store.load_results()} if keep_existing else {}
    old_previews = {p.match.id: p for p in store.load_previews()} if keep_existing else {}

    past = source.past_matches()
    upcoming = source.upcoming_matches()

    brief_graph = build_brief_graph(llm, source, settings.max_rewrites)
    new_briefs = 0
    for match in past:
        if match.id in results:
            continue
        try:
            out = brief_graph.invoke({"match": match})
            results[match.id] = BriefRecord(
                match=match,
                headline=out["draft"].headline,
                summary=out["draft"].summary,
                tags=out["tags"],
                facts=out["facts"],
                generated_by=out["generated_by"],
                trace=out["trace"],
            )
            new_briefs += 1
            print(f"[브리핑] {match.team_a.acronym} vs {match.team_b.acronym}: {out['draft'].headline}")
        except Exception as exc:
            print(f"[브리핑] 경기 {match.id} 처리 실패: {exc}")

    preview_graph = build_preview_graph(llm, source)
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
                    form_a=form_text(ctx.form_a),
                    form_b=form_text(ctx.form_b),
                    h2h=f"{ctx.h2h_a_wins}승 {ctx.h2h_b_wins}패" if ctx.h2h_a_wins or ctx.h2h_b_wins else "기록 없음",
                    case_a=out["case_a"],
                    case_b=out["case_b"],
                    watch_points=out["watch_points"],
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
        sample=settings.sample_mode,
        llm_name=llm.name if llm else "template",
        archive_size=settings.archive_size,
    )
    print(f"[run] 새 브리핑 {new_briefs}건, 새 프리뷰 {new_previews}건, 데이터 변경: {'있음' if changed else '없음'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
