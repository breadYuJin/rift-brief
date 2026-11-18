import type { SetView, TimelineView } from "@/lib/sets";

const SIZE = 15000;
const px = (v: number) => ((v / SIZE) * 100).toFixed(1);
const py = (v: number) => (100 - (v / SIZE) * 100).toFixed(1);

function Ground() {
  return (
    <>
      <rect x="0" y="0" width="100" height="100" rx="3" className="rift__ground" />
      <path d="M20,16 L80,86" className="rift__river" />
      <path d="M8,92 L8,9 L91,8" className="rift__lane" />
      <path d="M8,92 L92,8" className="rift__lane" />
      <path d="M8,92 L91,92 L92,8" className="rift__lane" />
      <circle cx="8" cy="92" r="4" className="rift__base" />
      <circle cx="92" cy="8" r="4" className="rift__base" />
      <text x="33" y="27" className="rift__label">
        바론
      </text>
      <text x="66" y="78" className="rift__label">
        드래곤
      </text>
    </>
  );
}

/** 협곡을 단순하게 그린 지도 위에 킬 위치를 찍는다. 점 색은 킬을 올린 팀이다. */
export function KillMap({ set, timeline }: { set: SetView; timeline: TimelineView }) {
  return (
    <figure className="rift">
      <svg
        viewBox="0 0 100 100"
        role="img"
        aria-label={`킬 위치 지도. ${set.a.team.acronym} ${set.a.stats.kills}킬, ${set.b.team.acronym} ${set.b.stats.kills}킬.`}
      >
        <Ground />
        {timeline.kills.map((k, i) => (
          <circle key={i} cx={px(k.x)} cy={py(k.y)} r="1.9" className={`rift__kill rift__kill--${k.side}`} />
        ))}
      </svg>
      <figcaption>킬이 난 자리</figcaption>
    </figure>
  );
}

/** 두 정글러의 초반 10분 위치를 1분 간격으로 이은 선. 굵은 점이 출발점이다. */
export function JungleMap({ set, timeline }: { set: SetView; timeline: TimelineView }) {
  const jungler = (side: "a" | "b") => set[side].picks.find((p) => p.role === "정글");
  return (
    <figure className="rift">
      <svg viewBox="0 0 100 100" role="img" aria-label="두 정글러의 초반 10분 동선 지도">
        <Ground />
        {(["a", "b"] as const).map((side) => {
          const path = timeline.jungle[side];
          if (path.length < 2) return null;
          return (
            <g key={side} className={`rift__path rift__path--${side}`}>
              <polyline points={path.map(([x, y]) => `${px(x)},${py(y)}`).join(" ")} />
              {path.map(([x, y], i) => (
                <circle key={i} cx={px(x)} cy={py(y)} r={i === 0 ? 2.2 : 1}>
                  <title>{`${i + 1}분`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <figcaption>
        초반 10분 정글 동선 ({jungler("a")?.player} / {jungler("b")?.player})
      </figcaption>
    </figure>
  );
}
