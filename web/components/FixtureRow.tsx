import Link from "next/link";
import { formatTime } from "@/lib/format";
import type { Match } from "@/lib/types";

/** 일정표 한 줄: 시각, 두 팀, 스코어 또는 상태. */
export function FixtureRow({ match, href, showStage = true }: { match: Match; href?: string; showStage?: boolean }) {
  const { team_a: a, team_b: b } = match;
  const finished = match.status === "finished" && match.winner_id !== null;
  const running = match.status === "running";
  const aLost = finished && match.winner_id !== a.id;
  const bLost = finished && match.winner_id !== b.id;
  const middle =
    finished || running ? (
      <span className="fx__score">
        <span className={aLost ? "is-loser" : ""}>{match.score_a}</span>
        <span className="fx__colon">:</span>
        <span className={bLost ? "is-loser" : ""}>{match.score_b}</span>
      </span>
    ) : (
      <span className="fx__vs">vs</span>
    );
  const teams = (
    <>
      <abbr className={`fx__team fx__team--a${aLost ? " is-loser" : ""}`} title={a.name}>
        {a.acronym}
      </abbr>
      {middle}
      <abbr className={`fx__team fx__team--b${bLost ? " is-loser" : ""}`} title={b.name}>
        {b.acronym}
      </abbr>
    </>
  );
  return (
    <li className="fx">
      <time className="fx__time" dateTime={match.begin_at ?? undefined}>
        {formatTime(match.begin_at)}
      </time>
      {href ? (
        <Link className="fx__teams" href={href}>
          {teams}
        </Link>
      ) : (
        <span className="fx__teams">{teams}</span>
      )}
      <span className="fx__info">
        {running && <span className="live">진행 중</span>}
        {showStage && <span className="fx__stage">{match.tournament}</span>}
        {!finished && !running && <span className="fx__bo">{match.best_of}전제</span>}
      </span>
    </li>
  );
}
