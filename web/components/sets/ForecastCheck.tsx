import { pct, type SetView, type TeamSetView } from "@/lib/sets";
import type { ForecastRow } from "@/lib/types";

function Chips({ rows, side }: { rows: ForecastRow[]; side: "a" | "b" }) {
  return (
    <ol className="fc__chips">
      {rows.map((r) => (
        <li
          key={r.champion}
          className={`fc__chip fc__chip--${side}${r.hit ? " is-hit" : r.seen ? " is-seen" : ""}`}
          title={`이 순위 예상이 지난 검증에서 맞은 비율 ${pct(r.p)}`}
        >
          {r.champion}
          {r.hit && <span className="sr-only"> (적중)</span>}
          {!r.hit && r.seen && <span className="sr-only"> (다른 쪽에서 등장)</span>}
        </li>
      ))}
    </ol>
  );
}

function Team({ view, side }: { view: TeamSetView; side: "a" | "b" }) {
  const f = view.forecast;
  if (!f || f.picks.length === 0) {
    return (
      <div className="fc__team">
        <p className="fc__name">{view.team.acronym}</p>
        <p className="set__note">이 세트 전까지 쌓인 기록이 없어 예상하지 않았습니다.</p>
      </div>
    );
  }
  return (
    <div className="fc__team">
      <p className="fc__name">{view.team.acronym}</p>
      <p className="fc__kind">
        픽 예상 <strong>{view.picks.length}개 중 {f.pick_hits ?? 0}개 적중</strong>
      </p>
      <Chips rows={f.picks} side={side} />
      <p className="fc__kind">
        밴 예상 <strong>{view.bans.length}개 중 {f.ban_hits ?? 0}개 적중</strong>
      </p>
      <Chips rows={f.bans} side={side} />
    </div>
  );
}

/** 세트 직전에 낸 예상 10개와 실제 결과. 채워진 칸은 그 팀이 실제로 고르거나 금지한 챔피언, 테두리만 있는 칸은 다른 쪽에서 나온 챔피언이다. */
export function ForecastCheck({ set }: { set: SetView }) {
  return (
    <div className="fc">
      <Team view={set.a} side="a" />
      <Team view={set.b} side="b" />
    </div>
  );
}
