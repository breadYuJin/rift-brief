import type { SetView, TeamSetView } from "@/lib/sets";

function Column({ view, side }: { view: TeamSetView; side: "a" | "b" }) {
  return (
    <div className={`pb__team pb__team--${side}${view.won ? " is-winner" : ""}`}>
      <p className="pb__head">
        <span className="pb__acr">{view.team.acronym}</span>
        <span className="pb__tags">
          {view.color === "blue" ? "블루 진영" : "레드 진영"}
          {view.firstPick && ", 선픽"}
          {view.won && <strong className="pb__win">승리</strong>}
        </span>
      </p>
      <ol className="pb__picks" aria-label={`${view.team.acronym} 선택`}>
        {view.picks.map((p) => (
          <li key={p.champion} className="pb__pick">
            <span className="pb__role">{p.role}</span>
            <span className="pb__champ">{p.champion}</span>
            <span className="pb__player">{p.player}</span>
          </li>
        ))}
      </ol>
      <ul className="pb__bans" aria-label={`${view.team.acronym} 금지`}>
        {view.bans.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </div>
  );
}

/** 한 세트의 밴픽. 왼쪽 팀과 오른쪽 팀이 마주 보고, 위가 선택 아래가 금지다. */
export function DraftBoard({ set }: { set: SetView }) {
  return (
    <div className="pb">
      <Column view={set.a} side="a" />
      <Column view={set.b} side="b" />
    </div>
  );
}
