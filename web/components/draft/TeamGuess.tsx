import { ChampIcon } from "@/components/Assets";
import { championName } from "@/lib/data";
import { pct } from "@/lib/format";
import type { ForecastRow, Team, TeamForecast } from "@/lib/types";

function Chips({ rows }: { rows: ForecastRow[] }) {
  return (
    <ol className="fc__chips">
      {rows.map((r) => (
        <li key={r.champion} className="fc__chip">
          <ChampIcon name={r.champion} size={18} />
          {championName(r.champion)} <span className="fc__p">{pct(r.p)}</span>
        </li>
      ))}
    </ol>
  );
}

/** 다가오는 경기 한 팀의 예상 밴·픽과, 그 순위의 예상이 지난 검증에서 맞은 비율. */
export function TeamGuess({ team, forecast }: { team: Team; forecast?: TeamForecast }) {
  if (!forecast) return null;
  return (
    <div className="fc__team">
      <p className="fc__name">{team.acronym}</p>
      <p className="fc__kind">금지할 것 같은 챔피언</p>
      <Chips rows={forecast.bans} />
      <p className="fc__kind">고를 것 같은 챔피언</p>
      <Chips rows={forecast.picks} />
    </div>
  );
}
