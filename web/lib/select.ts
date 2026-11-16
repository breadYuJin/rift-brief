import type { Brief, League, Match, Preview } from "./types";

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
