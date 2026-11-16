import type { Match } from "@/lib/types";

/**
 * 시리즈 흐름 띠. 세트 하나가 칸 하나이고, 칸 색은 그 세트를 이긴 팀,
 * 칸 너비는 세트 길이(분)에 비례한다. 역전·풀세트가 한눈에 보인다.
 */
export function SetStrip({ match, detailed = false }: { match: Match; detailed?: boolean }) {
  if (match.games.length === 0) return null;
  return (
    <ol className={`sets${detailed ? " sets--detailed" : ""}`} aria-label="세트별 결과">
      {match.games.map((g) => {
        const side = g.winner_id === match.team_a.id ? "a" : "b";
        const team = side === "a" ? match.team_a : match.team_b;
        const label = `${g.position}세트 ${team.acronym} 승${g.length_min ? `, ${g.length_min}분` : ""}`;
        return (
          <li key={g.position} className={`sets__set sets__set--${side}`} style={{ flexGrow: g.length_min ?? 30 }} title={label}>
            {detailed ? (
              <>
                <span className="sets__who">{team.acronym}</span>
                {g.length_min && <span className="sets__min">{g.length_min}분</span>}
              </>
            ) : (
              <span className="sr-only">{label}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
