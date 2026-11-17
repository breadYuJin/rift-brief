import { ChampIcon } from "@/components/Assets";
import type { SetView } from "@/lib/sets";
import type { PlayerSetLine } from "@/lib/types";

function Stat({ label, value, more }: { label: string; value: string; more: boolean }) {
  return (
    <span className={`mu__stat${more ? " is-more" : ""}`}>
      <span className="mu__label">{label}</span> {value}
    </span>
  );
}

/** 평점 배지. 7.5 이상은 밝게, 5 미만은 흐리게 보인다. 팬 의견이 반영됐으면 몇 명인지 옆에 적는다. */
export function Rating({
  value,
  best = false,
  official = "",
  votes = 0,
  base,
}: {
  value?: number | null;
  best?: boolean;
  /** 주최 측 선정 선수면 그 이름표("POM", "결승 MVP" 등) */
  official?: string;
  votes?: number;
  base?: number | null;
}) {
  if (value == null) return official ? <span className="rate__official">{official}</span> : null;
  const tier = value >= 7.5 ? "high" : value < 5 ? "low" : "mid";
  return (
    <>
      <span
        className={`rate rate--${tier}${best ? " rate--best" : ""}`}
        title={votes > 0 && base != null ? `기록으로 계산한 점수 ${base.toFixed(1)}, 팬 의견 ${votes}명 반영` : undefined}
      >
        <span className="sr-only">평점 </span>
        {value.toFixed(1)}
        {best && <span className="rate__tag">최고</span>}
      </span>
      {votes > 0 && <span className="rate__votes">의견 {votes}명</span>}
      {official && <span className="rate__official">{official}</span>}
    </>
  );
}

function Line({
  p,
  other,
  side,
  best,
  official,
}: {
  p: PlayerSetLine;
  other: PlayerSetLine;
  side: "a" | "b";
  best: boolean;
  official: boolean;
}) {
  const kda = (l: PlayerSetLine) => (l.kda[0] + l.kda[2]) / Math.max(1, l.kda[1]);
  return (
    <div className={`mu__side mu__side--${side}`}>
      <p className="mu__who">
        <ChampIcon name={p.champion} size={26} />
        <strong>{p.player}</strong>
        <span>{p.champion}</span>
        <Rating value={p.rating} best={best} votes={p.votes} base={p.rating_base} official={official ? "주최 측 MVP" : ""} />
      </p>
      <p className="mu__stats">
        <Stat label="KDA" value={p.kda.join("/")} more={kda(p) > kda(other)} />
        <Stat label="분당 CS" value={p.cs_min?.toFixed(1) ?? "-"} more={(p.cs_min ?? 0) > (other.cs_min ?? 0)} />
        <Stat label="분당 피해" value={p.dpm?.toLocaleString("ko-KR") ?? "-"} more={(p.dpm ?? 0) > (other.dpm ?? 0)} />
      </p>
    </div>
  );
}

const same = (official: string | null, player: string) => !!official && official.toLowerCase() === player.toLowerCase();

/** 같은 포지션 두 선수의 세트 기록을 마주 놓는다. 더 높은 쪽 숫자가 밝게 보인다. */
export function Matchups({ set }: { set: SetView }) {
  return (
    <ul className="mu">
      {set.matchups.map((m) => (
        <li key={m.role} className="mu__row">
          <Line
            p={m.a}
            other={m.b}
            side="a"
            best={set.best?.side === "a" && set.best.player === m.a.player}
            official={same(set.officialMvp, m.a.player)}
          />
          <span className="mu__role">{m.role}</span>
          <Line
            p={m.b}
            other={m.a}
            side="b"
            best={set.best?.side === "b" && set.best.player === m.b.player}
            official={same(set.officialMvp, m.b.player)}
          />
        </li>
      ))}
    </ul>
  );
}
