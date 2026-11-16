import type { Bracket, Brief, League, Match, Preview } from "./types";

const FEATURED_MIN = 2;

/** 주요 경기: 최근 결과와 예정 경기 중 주요 경기 점수가 높은 것. 없으면 가장 최근 결과 하나. */
export function pickFeatured(results: Brief[], previews: Preview[]) {
  const byScore = <T extends { importance?: number }>(a: T, b: T) => (b.importance ?? 0) - (a.importance ?? 0);
  const topResults = results
    .slice(0, 10)
    .filter((r) => (r.importance ?? 0) >= FEATURED_MIN)
    .sort(byScore)
    .slice(0, 2);
  const topPreviews = previews
    .filter((p) => (p.importance ?? 0) >= FEATURED_MIN)
    .sort(byScore)
    .slice(0, 2);
  return {
    results: topResults.length ? topResults : results.slice(0, 1),
    previews: topPreviews,
  };
}

export const liveMatches = (leagues: League[]): Match[] =>
  leagues.flatMap((l) => l.matches.filter((m) => m.status === "running"));

export const nextMatches = (leagues: League[], limit = 5): Match[] =>
  leagues
    .flatMap((l) => l.matches.filter((m) => m.status === "not_started" && m.begin_at))
    .sort((a, b) => (a.begin_at ?? "").localeCompare(b.begin_at ?? ""))
    .slice(0, limit);

export const stageLabel = (m: Match) => [m.league, m.tournament].filter(Boolean).join(" ");
export const winRate = (wins: number, losses: number) =>
  wins + losses === 0 ? "-" : (wins / (wins + losses)).toFixed(3).replace(/^0/, "");

/** 모든 리그의 대진표를 최근에 열린 순으로 늘어놓는다. 화면에는 대진표에 나오는 경기만 넘긴다. */
export function bracketEntries(leagues: League[], briefedIds: Set<number>) {
  const entries = leagues.flatMap((league) => {
    const byId = new Map(league.matches.map((m) => [m.id, m]));
    return (league.brackets ?? []).map((bracket: Bracket) => {
      const ids = bracket.rounds.flatMap((r) => r.slots.map((s) => s.match_id));
      const matches: Record<number, Match> = {};
      let latest = "";
      for (const id of ids) {
        const m = byId.get(id);
        if (!m) continue;
        matches[id] = m;
        if ((m.begin_at ?? "") > latest) latest = m.begin_at ?? "";
      }
      return {
        key: `${league.id}:${bracket.stage}`,
        label: bracket.stage.startsWith(league.name) ? bracket.stage : `${league.name} ${bracket.stage}`,
        bracket,
        matches,
        briefed: ids.filter((id) => briefedIds.has(id)),
        latest,
      };
    });
  });
  return entries.sort((a, b) => b.latest.localeCompare(a.latest)).map(({ latest: _latest, ...rest }) => rest);
}
