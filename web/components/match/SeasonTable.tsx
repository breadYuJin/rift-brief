import type { PlayerAverage, Team } from "@/lib/types";

export interface SeasonRow {
  role: string;
  a: PlayerAverage;
  b: PlayerAverage;
}

interface Column {
  label: string;
  value: (p: PlayerAverage) => number;
  text: (p: PlayerAverage) => string;
}

// 왼쪽 팀은 이 순서로, 오른쪽 팀은 거꾸로 놓아 가운데 포지션을 중심으로 마주 보게 한다.
const COLUMNS: Column[] = [
  { label: "평점", value: (p) => p.rating ?? 0, text: (p) => p.rating?.toFixed(1) ?? "-" },
  { label: "KDA", value: (p) => p.kda, text: (p) => p.kda.toFixed(1) },
  { label: "분당 CS", value: (p) => p.cs_min, text: (p) => p.cs_min.toFixed(1) },
  { label: "분당 피해", value: (p) => p.dpm, text: (p) => String(p.dpm) },
];

/** 이 경기에 나온 선수끼리 시즌 평균을 맞세운 표. 더 높은 쪽 숫자가 밝게 보인다. */
export function SeasonTable({ teams, rows }: { teams: [Team, Team]; rows: SeasonRow[] }) {
  const [a, b] = teams;
  const reversed = [...COLUMNS].reverse();
  const cell = (col: Column, mine: PlayerAverage, other: PlayerAverage) => (
    <td key={col.label} className={`num${col.value(mine) > col.value(other) ? " is-more" : ""}`}>
      {col.text(mine)}
    </td>
  );
  return (
    <div className="table-wrap">
      <table className="table season">
        <thead>
          <tr>
            <th scope="col">{a.acronym}</th>
            {COLUMNS.map((c) => (
              <th key={c.label} scope="col" className="num">
                {c.label}
              </th>
            ))}
            <th scope="col" className="season__role">
              포지션
            </th>
            {reversed.map((c) => (
              <th key={c.label} scope="col" className="num">
                {c.label}
              </th>
            ))}
            <th scope="col" className="season__b">
              {b.acronym}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.role}>
              <th scope="row" className="season__a">
                {r.a.player}
              </th>
              {COLUMNS.map((c) => cell(c, r.a, r.b))}
              <td className="season__role">{r.role}</td>
              {reversed.map((c) => cell(c, r.b, r.a))}
              <th scope="row" className="season__b">
                {r.b.player}
              </th>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
