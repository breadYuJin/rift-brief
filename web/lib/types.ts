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
