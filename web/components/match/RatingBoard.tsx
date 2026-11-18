import { TeamLogo } from "@/components/Assets";
import { Rating } from "@/components/sets/Matchups";
import type { OfficialPicks } from "@/lib/official";
import { ROLES } from "@/lib/sets";
import type { SeriesRating, Team } from "@/lib/types";

/** 경기 평균 평점. 두 팀을 나란히, 포지션 순으로. 경기 최고 평점은 이긴 팀에서 뽑는다. */
export function RatingBoard({
  teams,
  ratings,
  winnerId,
  picks,
}: {
  teams: [Team, Team];
  ratings: SeriesRating[];
  winnerId: number | null;
  picks: OfficialPicks;
}) {
  // ratings 는 평점 높은 순이라, 이긴 팀의 첫 선수가 경기 최고 평점이다.
  const top = ratings.find((r) => r.team_id === winnerId) ?? null;
  const rows = (teamId: number) =>
    ratings.filter((r) => r.team_id === teamId).sort((x, y) => ROLES.indexOf(x.role) - ROLES.indexOf(y.role));
  return (
    <div className="rates">
      {teams.map((team, i) => (
        <div key={team.id} className={`rates__team rates__team--${i === 0 ? "a" : "b"}`}>
          <p className="rates__head">
            <TeamLogo id={team.id} size={24} />
            {team.acronym}
          </p>
          <ul>
            {rows(team.id).map((r) => {
              const tag = picks.tagFor(r.player);
              return (
                <li key={r.player} className="rates__row">
                  <span className="rates__role">{r.role}</span>
                  <span className="rates__name">
                    {r.player}
                    {tag && <span className="rate__official">{tag}</span>}
                  </span>
                  <span className="rates__bar" aria-hidden="true">
                    <span style={{ width: `${r.rating * 10}%` }} />
                  </span>
                  <span className="rates__score">
                    <Rating value={r.rating} best={top?.player === r.player && top.team_id === r.team_id} />
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
