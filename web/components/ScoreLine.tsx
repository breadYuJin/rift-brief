import type { Match } from "@/lib/types";

/** 중계 화면의 스코어 표시처럼 팀 약칭과 세트 스코어를 한 줄로 보여 준다. */
export function ScoreLine({ match, size = "md" }: { match: Match; size?: "md" | "lg" }) {
  const { team_a: a, team_b: b } = match;
  const finished = match.winner_id !== null;
  const aWon = match.winner_id === a.id;
  const bWon = match.winner_id === b.id;
  const winner = aWon ? a : bWon ? b : null;
  return (
    <div className={`score score--${size}`}>
      <span className={`score__team score__team--a${finished && !aWon ? " is-loser" : ""}`}>
        <abbr title={a.name}>{a.acronym}</abbr>
      </span>
      {finished ? (
        <span className="score__nums" aria-hidden="true">
          <span className={aWon ? "" : "is-loser"}>{match.score_a}</span>
          <span className="score__colon">:</span>
          <span className={bWon ? "" : "is-loser"}>{match.score_b}</span>
        </span>
      ) : (
        <span className="score__vs">vs</span>
      )}
      <span className={`score__team score__team--b${finished && !bWon ? " is-loser" : ""}`}>
        <abbr title={b.name}>{b.acronym}</abbr>
      </span>
      {winner && (
        <span className="sr-only">
          {winner.name} 승리, 세트 스코어 {Math.max(match.score_a, match.score_b)} 대{" "}
          {Math.min(match.score_a, match.score_b)}
        </span>
      )}
    </div>
  );
}
