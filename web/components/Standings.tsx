import { winRate } from "@/lib/select";
import type { Stage } from "@/lib/types";
import { FormPips } from "./FormPips";

const streakText = (n: number) => (n > 0 ? `${n}연승` : n < 0 ? `${-n}연패` : "-");

/** 스테이지별 팀 전적표. limit 을 주면 상위 몇 팀만 간단히 보여 준다. */
export function Standings({ stage, limit }: { stage: Stage; limit?: number }) {
  const rows = limit ? stage.standings.slice(0, limit) : stage.standings;
  const compact = Boolean(limit);
  return (
    <div className="table-wrap">
      <table className={`table${compact ? " table--compact" : ""}`}>
        <caption className="sr-only">{stage.name} 팀 전적</caption>
        <thead>
          <tr>
            <th scope="col" className="num">
              순위
            </th>
            <th scope="col">팀</th>
            <th scope="col" className="num">
              승
            </th>
            <th scope="col" className="num">
              패
            </th>
            {!compact && (
              <>
                <th scope="col" className="num">
                  승률
                </th>
                <th scope="col" className="num">
                  세트
                </th>
                <th scope="col" className="num">
                  득실
                </th>
              </>
            )}
            <th scope="col">최근 5경기</th>
            {!compact && <th scope="col">연속</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const diff = r.set_wins - r.set_losses;
            return (
              <tr key={r.team.id}>
                <td className="num table__rank">{i + 1}</td>
                <th scope="row" className="table__team">
                  <span className="table__acr">{r.team.acronym}</span>
                  {!compact && r.team.name !== r.team.acronym && <span className="table__name">{r.team.name}</span>}
                </th>
                <td className="num">{r.wins}</td>
                <td className="num">{r.losses}</td>
                {!compact && (
                  <>
                    <td className="num">{winRate(r.wins, r.losses)}</td>
                    <td className="num">
                      {r.set_wins}-{r.set_losses}
                    </td>
                    <td className="num">{diff > 0 ? `+${diff}` : diff}</td>
                  </>
                )}
                <td>
                  <FormPips recent={r.recent} />
                </td>
                {!compact && <td>{streakText(r.streak)}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
