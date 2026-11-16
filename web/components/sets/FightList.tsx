import { clock, type SetView, type TimelineView } from "@/lib/sets";

/** 킬이 많이 난 교전 순으로 몇 개만 보여 준다. 영상 위치가 확인된 뒤에는 각 줄이 영상 바로가기가 된다. */
export function FightList({ set, timeline }: { set: SetView; timeline: TimelineView }) {
  const top = [...timeline.fights]
    .filter((f) => f.a + f.b >= 2)
    .sort((p, q) => q.a + q.b - (p.a + p.b) || p.t - q.t)
    .slice(0, 5)
    .sort((p, q) => p.t - q.t);
  if (top.length === 0) return null;
  return (
    <ol className="fights">
      {top.map((f) => {
        const body = (
          <>
            <span className="fights__time">{clock(f.t)}</span>
            <span className="fights__zone">{f.zone}</span>
            <span className="fights__score">
              <span className={f.winner === "a" ? "is-more" : ""}>
                {set.a.team.acronym} {f.a}
              </span>
              <span aria-hidden="true">:</span>
              <span className={f.winner === "b" ? "is-more" : ""}>
                {f.b} {set.b.team.acronym}
              </span>
            </span>
          </>
        );
        return (
          <li key={f.t} className={`fights__item fights__item--${f.winner || "even"}`}>
            {f.clip ? (
              <a href={f.clip} rel="noopener noreferrer" target="_blank">
                {body}
                <span className="fights__go">영상으로 보기</span>
              </a>
            ) : (
              body
            )}
          </li>
        );
      })}
    </ol>
  );
}
