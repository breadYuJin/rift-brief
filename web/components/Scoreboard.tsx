import { formatTime } from "@/lib/format";
import type { Match } from "@/lib/types";
import { TeamLogo } from "./Assets";
import { FormPips } from "./FormPips";

interface Props {
  match: Match;
  recentA?: boolean[];
  recentB?: boolean[];
  size?: "sm" | "md" | "lg";
}

/** 중계 화면의 스코어보드처럼 두 팀을 좌우로 마주 세우고 가운데에 스코어를 둔다. */
export function Scoreboard({ match, recentA, recentB, size = "md" }: Props) {
  const { team_a: a, team_b: b } = match;
  const finished = match.status === "finished" && match.winner_id !== null;
  const running = match.status === "running";
  const aLost = finished && match.winner_id !== a.id;
  const bLost = finished && match.winner_id !== b.id;
  const winner = finished ? (aLost ? b : a) : null;
  const logo = size === "lg" ? 56 : size === "sm" ? 18 : 30;
  return (
    <div className={`sb sb--${size}`}>
      <div className={`sb__team sb__team--a${aLost ? " is-loser" : ""}`}>
        <span className="sb__id">
          <TeamLogo id={a.id} size={logo} />
          <abbr className="sb__acr" title={a.name}>
            {a.acronym}
          </abbr>
        </span>
        {size !== "sm" && a.name !== a.acronym && <span className="sb__name">{a.name}</span>}
        {size !== "sm" && <FormPips recent={recentA} side="a" />}
      </div>
      <div className="sb__mid">
        {finished || running ? (
          <span className="sb__score" aria-hidden="true">
            <span className={aLost ? "is-loser" : ""}>{match.score_a}</span>
            <span className="sb__colon">:</span>
            <span className={bLost ? "is-loser" : ""}>{match.score_b}</span>
          </span>
        ) : (
          <span className="sb__time">{formatTime(match.begin_at) || "vs"}</span>
        )}
        {running && <span className="live">진행 중</span>}
        {!finished && !running && size !== "sm" && <span className="sb__bo">{match.best_of}전제</span>}
      </div>
      <div className={`sb__team sb__team--b${bLost ? " is-loser" : ""}`}>
        <span className="sb__id">
          <TeamLogo id={b.id} size={logo} />
          <abbr className="sb__acr" title={b.name}>
            {b.acronym}
          </abbr>
        </span>
        {size !== "sm" && b.name !== b.acronym && <span className="sb__name">{b.name}</span>}
        {size !== "sm" && <FormPips recent={recentB} side="b" />}
      </div>
      {winner && (
        <span className="sr-only">
          {winner.name} 승리, 세트 스코어 {Math.max(match.score_a, match.score_b)} 대{" "}
          {Math.min(match.score_a, match.score_b)}
        </span>
      )}
      {running && (
        <span className="sr-only">
          진행 중, 현재 세트 스코어 {a.name} {match.score_a} 대 {b.name} {match.score_b}
        </span>
      )}
    </div>
  );
}
