import type { Match, MatchSets, MockDraft, PlayerSetLine, SetDetail, Team, TeamForecast, TeamStats } from "./types";

/** 화면에서는 진영(블루/레드)이 아니라 경기의 왼쪽 팀(a)·오른쪽 팀(b) 기준으로 그린다. */
export type Side = "a" | "b";

export interface TeamSetView {
  team: Team;
  color: "blue" | "red";
  firstPick: boolean;
  won: boolean;
  bans: string[];
  picks: { role: string; champion: string; player: string }[];
  stats: TeamStats;
  forecast: TeamForecast | null;
}

export interface FightView {
  t: number;
  a: number;
  b: number;
  zone: string;
  winner: Side | "";
  x: number | null;
  y: number | null;
  clip?: string;
}

export interface TimelineView {
  goldDiff: number[]; // 분 단위, 양수면 a 가 앞섬
  fights: FightView[];
  fightCount: { total: number; a: number; b: number };
  objectives: { t: number; name: string; side: Side }[];
  kills: { t: number; side: Side; x: number; y: number }[];
  jungle: { a: [number, number][]; b: [number, number][] };
  firstBlood: { t: number; side: Side; zone: string } | null;
}

export interface SetView {
  number: number;
  patch: string;
  lengthMin: number | null;
  a: TeamSetView;
  b: TeamSetView;
  /** a 팀 기준 승률. 시즌 초반처럼 계산하지 않은 세트는 null */
  win: { before: number; after: number } | null;
  matchups: { role: string; a: PlayerSetLine; b: PlayerSetLine }[];
  /** 주최 측이 뽑은 세트 MVP (세트마다 뽑는 대회에서만) */
  officialMvp: string | null;
  /** 이긴 팀에서 평점이 가장 높은 선수 */
  best: { player: string; side: Side; rating: number } | null;
  timeline: TimelineView | null;
}

export interface MockView {
  first: Team;
  second: Team;
  firstSide: Side;
  moves: { kind: "ban" | "pick"; side: Side; champion: string; role: string; reason: string }[];
  commentary: string;
  by: "llm" | "policy";
}

type Name = (english: string) => string;

function teamView(set: SetDetail, team: Team, name: Name): TeamSetView {
  const color = set.blue.id === team.id ? "blue" : "red";
  const players = new Map(set.matchups.map((m) => [m.role, m[color].player]));
  const forecast = set.forecast[String(team.id)] ?? null;
  const rows = (items: TeamForecast["picks"]) => items.map((r) => ({ ...r, champion: name(r.champion) }));
  return {
    team,
    color,
    firstPick: set.first_pick_id === team.id,
    won: set.winner_id === team.id,
    bans: set.draft.filter((d) => d.kind === "ban" && d.team_id === team.id).map((d) => name(d.champion)),
    picks: set.draft
      .filter((d) => d.kind === "pick" && d.team_id === team.id)
      .map((d) => ({ role: d.role, champion: name(d.champion), player: players.get(d.role) ?? "" })),
    stats: set.stats[color],
    forecast: forecast && {
      ...forecast,
      picks: rows(forecast.picks),
      bans: rows(forecast.bans),
      by_role: Object.fromEntries(Object.entries(forecast.by_role).map(([role, list]) => [role, list.map(name)])),
    },
  };
}

export function toSetViews(data: MatchSets, match: Match, name: Name): SetView[] {
  const { team_a: a, team_b: b } = match;
  return data.sets.map((set) => {
    const aColor = set.blue.id === a.id ? "blue" : "red";
    const side = (color: string): Side => (color === aColor ? "a" : "b");
    const s = set.summary;
    const timeline: TimelineView | null =
      s.has_timeline && s.fights && s.fight_count
        ? {
            goldDiff: (s.gold_diff ?? []).map((d) => (aColor === "blue" ? d : -d)),
            fights: s.fights.map((f) => ({
              t: f.t,
              a: aColor === "blue" ? f.blue : f.red,
              b: aColor === "blue" ? f.red : f.blue,
              zone: f.zone,
              winner: f.winner ? side(f.winner) : "",
              x: f.x,
              y: f.y,
              clip: (f as { clip?: string }).clip,
            })),
            fightCount: {
              total: s.fight_count.total,
              a: aColor === "blue" ? s.fight_count.blue : s.fight_count.red,
              b: aColor === "blue" ? s.fight_count.red : s.fight_count.blue,
            },
            objectives: (s.objectives ?? []).map((o) => ({ t: o.t, name: o.name, side: side(o.side) })),
            kills: (s.kills ?? []).map(([t, blueScored, x, y]) => ({ t, side: side(blueScored ? "blue" : "red"), x, y })),
            jungle: {
              a: (aColor === "blue" ? s.jungle?.blue : s.jungle?.red) ?? [],
              b: (aColor === "blue" ? s.jungle?.red : s.jungle?.blue) ?? [],
            },
            firstBlood: s.first_blood
              ? { t: s.first_blood.t, side: side(s.first_blood.side), zone: s.first_blood.zone }
              : null,
          }
        : null;
    const line = (p: PlayerSetLine) => ({ ...p, champion: name(p.champion) });
    return {
      number: set.number,
      patch: set.patch,
      lengthMin: set.length_min,
      a: teamView(set, a, name),
      b: teamView(set, b, name),
      win: set.win && {
        before: aColor === "blue" ? set.win.before : 1 - set.win.before,
        after: aColor === "blue" ? set.win.after : 1 - set.win.after,
      },
      matchups: set.matchups.map((m) => ({ role: m.role, a: line(m[aColor]), b: line(m[aColor === "blue" ? "red" : "blue"]) })),
      officialMvp: set.official_mvp ?? null,
      best: set.best ? { player: set.best.player, side: set.best.team_id === a.id ? "a" : "b", rating: set.best.rating } : null,
      timeline,
    };
  });
}

export function toMockView(mock: MockDraft, a: Team, b: Team, name: Name): MockView {
  const firstSide: Side = mock.first_id === a.id ? "a" : "b";
  return {
    first: firstSide === "a" ? a : b,
    second: firstSide === "a" ? b : a,
    firstSide,
    moves: mock.moves.map((m) => ({
      kind: m.kind,
      side: m.team_id === a.id ? "a" : "b",
      champion: name(m.champion),
      role: m.role,
      reason: m.reason,
    })),
    commentary: mock.commentary,
    by: mock.by,
  };
}

/** 초를 "12:34" 로 */
export const clock = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;
export const pct = (p: number) => `${Math.round(p * 100)}%`;
