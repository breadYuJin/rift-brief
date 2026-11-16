// pipeline/schemas.py 의 BriefRecord / PreviewRecord 와 같은 모양이다.
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
  headline: string;
  summary: string[];
  tags: string[];
  facts: string[];
  generated_by: "llm" | "template";
  trace: TraceStep[];
}

export interface Preview {
  match: Match;
  form_a: string;
  form_b: string;
  h2h: string;
  case_a: string[];
  case_b: string[];
  watch_points: string[];
  generated_by: "llm" | "template";
  trace: TraceStep[];
}

export interface Meta {
  updated_at: string | null;
  sample: boolean;
  llm: string;
}
