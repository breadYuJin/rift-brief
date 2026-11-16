import type { SetView } from "@/lib/sets";
import type { PlayerSetLine } from "@/lib/types";

function Stat({ label, value, more }: { label: string; value: string; more: boolean }) {
  return (
    <span className={`mu__stat${more ? " is-more" : ""}`}>
      <span className="mu__label">{label}</span> {value}
    </span>
  );
}

function Line({ p, other, side }: { p: PlayerSetLine; other: PlayerSetLine; side: "a" | "b" }) {
  const kda = (l: PlayerSetLine) => (l.kda[0] + l.kda[2]) / Math.max(1, l.kda[1]);
  return (
    <div className={`mu__side mu__side--${side}`}>
      <p className="mu__who">
        <strong>{p.player}</strong>
        <span>{p.champion}</span>
      </p>
      <p className="mu__stats">
        <Stat label="KDA" value={p.kda.join("/")} more={kda(p) > kda(other)} />
        <Stat label="분당 CS" value={p.cs_min?.toFixed(1) ?? "-"} more={(p.cs_min ?? 0) > (other.cs_min ?? 0)} />
        <Stat label="분당 피해" value={p.dpm?.toLocaleString("ko-KR") ?? "-"} more={(p.dpm ?? 0) > (other.dpm ?? 0)} />
      </p>
    </div>
  );
}

/** 같은 포지션 두 선수의 세트 기록을 마주 놓는다. 더 높은 쪽 숫자가 밝게 보인다. */
export function Matchups({ set }: { set: SetView }) {
  return (
    <ul className="mu">
      {set.matchups.map((m) => (
        <li key={m.role} className="mu__row">
          <Line p={m.a} other={m.b} side="a" />
          <span className="mu__role">{m.role}</span>
          <Line p={m.b} other={m.a} side="b" />
        </li>
      ))}
    </ul>
  );
}
