// pipeline/schemas.py 의 레코드와 같은 모양이다.
export interface Team {
  id: number;
  name: string;
  acronym: string;
}

export interface Game {
  position: number;
  winner_id: number | null;
  length_min: number | null;
}

export interface Match {
  id: number;
  league: string;
  stage: string;
  league_id: number | null;
  serie_id: number | null;
  tournament: string;
  round?: string;
  best_of: number;
  status: string;
  begin_at: string | null;
  end_at: string | null;
  team_a: Team;
  team_b: Team;
  score_a: number;
  score_b: number;
  winner_id: number | null;
  games: Game[];
}

export interface TraceStep {
  agent: string;
  note: string;
}

export interface Brief {
  match: Match;
  recent_a?: boolean[];
  recent_b?: boolean[];
  headline: string;
  summary: string[];
  tags: string[];
  facts: string[];
  importance?: number;
  reasons?: string[];
  generated_by: "llm" | "template";
  trace: TraceStep[];
}

export interface Preview {
  match: Match;
  recent_a?: boolean[];
  recent_b?: boolean[];
  form_a: string;
  form_b: string;
  h2h: string;
  case_a: string[];
  case_b: string[];
  watch_points: string[];
  importance?: number;
  reasons?: string[];
  generated_by: "llm" | "template";
  trace: TraceStep[];
}

export interface Standing {
  team: Team;
  wins: number;
  losses: number;
  set_wins: number;
  set_losses: number;
  recent: boolean[];
  streak: number;
}

export interface Stage {
  name: string;
  standings: Standing[];
}

export interface BracketSlot {
  match_id: number;
  note_a: string;
  note_b: string;
}

export interface Bracket {
  stage: string;
  tree: boolean;
  rounds: { name: string; slots: BracketSlot[] }[];
}

export interface League {
  id: number;
  name: string;
  serie: string;
  status: "진행 중" | "시작 전" | "종료";
  stages: Stage[];
  matches: Match[];
  brackets?: Bracket[];
}

export interface Meta {
  updated_at: string | null;
  sample: boolean;
  source?: "live" | "archive" | "sample";
  source_note?: string;
  llm: string;
}

// ---- 세트 상세·예측 (pipeline/analysis.py 가 만드는 파일) ----

export interface DraftStep {
  kind: "ban" | "pick";
  team_id: number;
  champion: string;
  role: string;
}

export interface TeamStats {
  kills: number;
  gold: number;
  dragons: number;
  barons: number;
  towers: number;
  heralds: number;
  grubs: number;
  atakhans: number;
  inhibitors: number;
}

export interface PlayerSetLine {
  player: string;
  champion: string;
  kda: [number, number, number];
  cs: number;
  gold: number;
  damage: number;
  vision: number;
  cs_min: number | null;
  dpm: number | null;
}

export interface Fight {
  t: number;
  blue: number;
  red: number;
  x: number | null;
  y: number | null;
  zone: string;
  winner: "blue" | "red" | "";
}

export interface SetSummary {
  has_timeline: boolean;
  fights?: Fight[];
  fight_count?: { total: number; blue: number; red: number };
  objectives?: { t: number; name: string; side: "blue" | "red" }[];
  gold_diff?: number[];
  jungle?: { blue: [number, number][]; red: [number, number][] };
  /** [초, 블루 쪽 득점인지, x, y] */
  kills?: [number, boolean, number, number][];
  participants_ok?: boolean;
  first_blood?: { t: number; side: string; zone: string } | null;
}

export interface ForecastRow {
  champion: string;
  p: number;
  hit?: boolean;
}

export interface TeamForecast {
  bans: ForecastRow[];
  picks: ForecastRow[];
  by_role: Record<string, string[]>;
  ban_hits?: number;
  pick_hits?: number;
}

export interface SetDetail {
  number: number;
  patch: string;
  length_min: number | null;
  blue: Team;
  red: Team;
  winner_id: number | null;
  first_pick_id: number | null;
  draft: DraftStep[];
  stats: { blue: TeamStats; red: TeamStats };
  matchups: { role: string; blue: PlayerSetLine; red: PlayerSetLine }[];
  summary: SetSummary;
  /** 블루 진영 기준 승률 */
  win: { before: number; after: number } | null;
  forecast: Record<string, TeamForecast>;
}

export interface MockMove {
  kind: "ban" | "pick";
  team_id: number;
  champion: string;
  role: string;
  reason: string;
}

export interface MockDraft {
  first_id: number;
  second_id: number;
  moves: MockMove[];
  commentary: string;
  by: "llm" | "policy";
}

export interface MatchSets {
  match_id: number;
  sets: SetDetail[];
  mock: MockDraft | null;
}

export interface DraftScores {
  sets: number;
  pick_recall_5: number;
  pick_recall_10: number;
  ban_recall_5: number;
  ban_recall_10: number;
}

export interface WinScores {
  sets: number;
  accuracy: number;
  brier: number;
  log_loss: number;
}

export interface Models {
  draft: {
    train_share: number;
    holdout: DraftScores;
    holdout_set1: DraftScores;
    holdout_later_sets: DraftScores;
    baseline_meta_only: DraftScores;
    rank_hit: { ban: number[]; pick: number[] };
  };
  win: {
    report: { coin: WinScores; blue_rate: WinScores; before_draft: WinScores; after_draft: WinScores };
    coef: number[];
    features: string[];
  };
  counts: { sets: number; drafted: number; timelines: number; timelines_verified: number; series: number };
  mock_by: "llm" | "policy";
}

export interface DraftSeries {
  match_id: number;
  league: string;
  date: string;
  team_a: Team;
  team_b: Team;
  score_a: number;
  score_b: number;
  sets: number;
  ban_recall: number;
  pick_recall: number;
  has_mock: boolean;
}

export interface UpcomingDraft {
  match_id: number;
  team_a: Team;
  team_b: Team;
  begin_at: string | null;
  forecast: Record<string, TeamForecast>;
  mock: MockDraft;
  win_before: number;
}

export interface DraftIndex {
  recent: DraftSeries[];
  upcoming: UpcomingDraft[];
}

export interface PlayerAverage {
  player: string;
  role: string;
  sets: number;
  win_rate: number;
  kda: number;
  cs_min: number;
  dpm: number;
  gpm: number;
  vision_min: number;
}

export interface ChampionTable {
  version: string;
  champions: Record<string, { id: string; en: string; ko: string }>;
}
