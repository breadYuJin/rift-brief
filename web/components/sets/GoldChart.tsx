import { clock, type SetView, type TimelineView } from "@/lib/sets";

const W = 640;
const H = 214;
// 위 띠는 왼쪽 팀 오브젝트, 가운데가 골드 차, 아래 띠는 오른쪽 팀 오브젝트, 맨 아래가 시간 눈금이다.
const PAD = { l: 14, r: 14, t: 34, b: 50 };
const LABEL_GAP = 30;
const GLYPH: Record<string, string> = { 드래곤: "용", "장로 드래곤": "장로", 바론: "바론", 전령: "전령", "공허 유충": "유충", 아타칸: "아타칸" };

/** 같은 팀이 1분 안에 연달아 잡은 같은 오브젝트(유충 세 마리 등)는 하나로 묶는다. */
function grouped(objectives: TimelineView["objectives"]) {
  const out: (TimelineView["objectives"][number] & { count: number })[] = [];
  for (const o of objectives) {
    const last = out[out.length - 1];
    if (last && last.name === o.name && last.side === o.side && o.t - last.t < 60) last.count += 1;
    else out.push({ ...o, count: 1 });
  }
  return out;
}

/** 글자가 겹치지 않게 두 줄로 나눠 놓는다. 앞 글자와 가까우면 둘째 줄로 내린다. */
function staggered<T extends { x: number }>(items: T[]): (T & { row: 0 | 1 })[] {
  const lastX = [-Infinity, -Infinity];
  return items.map((item) => {
    const row = item.x - lastX[0] >= LABEL_GAP ? 0 : item.x - lastX[1] >= LABEL_GAP ? 1 : lastX[0] <= lastX[1] ? 0 : 1;
    lastX[row] = item.x;
    return { ...item, row: row as 0 | 1 };
  });
}

/** 분 단위 골드 차. 위로 솟으면 왼쪽 팀, 아래로 꺼지면 오른쪽 팀이 앞선 구간이다. 오브젝트와 교전을 같은 시간축에 얹는다. */
export function GoldChart({ set, timeline }: { set: SetView; timeline: TimelineView }) {
  const diff = timeline.goldDiff;
  if (diff.length < 2) return null;
  const minutes = diff.length - 1;
  const peak = Math.max(1000, ...diff.map(Math.abs));
  const mid = PAD.t + (H - PAD.t - PAD.b) / 2;
  const half = (H - PAD.t - PAD.b) / 2;
  const x = (min: number) => PAD.l + (min / minutes) * (W - PAD.l - PAD.r);
  const y = (d: number) => mid - (d / peak) * half;
  const area = (clamp: (d: number) => number) =>
    `M${x(0)},${mid} ` + diff.map((d, i) => `L${x(i).toFixed(1)},${y(clamp(d)).toFixed(1)}`).join(" ") + ` L${x(minutes)},${mid} Z`;
  const final = diff[diff.length - 1];
  const leader = final >= 0 ? set.a : set.b;
  const ticks = Array.from({ length: Math.floor(minutes / 10) }, (_, i) => (i + 1) * 10);
  const objects = grouped(timeline.objectives).map((o) => ({ ...o, x: x(o.t / 60) }));
  const labels = [
    ...staggered(objects.filter((o) => o.side === "a")).map((o) => ({ ...o, y: o.row === 0 ? 26 : 13 })),
    ...staggered(objects.filter((o) => o.side === "b")).map((o) => ({ ...o, y: H - PAD.b + (o.row === 0 ? 14 : 27) })),
  ];
  return (
    <figure className="gold">
      <div className="gold__scroll">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`골드 차 흐름. 마지막에는 ${leader.team.acronym} 가 ${(Math.abs(final) / 1000).toFixed(1)}k 앞섰습니다.`}>
        {ticks.map((m) => (
          <g key={m}>
            <line x1={x(m)} x2={x(m)} y1={PAD.t} y2={H - PAD.b} className="gold__grid" />
            <text x={x(m)} y={H - 4} className="gold__tick">
              {m}분
            </text>
          </g>
        ))}
        <path d={area((d) => Math.max(d, 0))} className="gold__area gold__area--a" />
        <path d={area((d) => Math.min(d, 0))} className="gold__area gold__area--b" />
        <line x1={PAD.l} x2={W - PAD.r} y1={mid} y2={mid} className="gold__zero" />
        {timeline.fights
          .filter((f) => f.a + f.b >= 2)
          .map((f) => (
            <circle key={f.t} cx={x(f.t / 60)} cy={mid} r={2 + Math.min(4, f.a + f.b)} className={`gold__fight gold__fight--${f.winner || "even"}`}>
              <title>{`${clock(f.t)} ${f.zone} 교전 ${set.a.team.acronym} ${f.a} : ${f.b} ${set.b.team.acronym}`}</title>
            </circle>
          ))}
        {labels.map((o) => (
          <text key={`${o.t}${o.name}`} x={o.x} y={o.y} className={`gold__obj gold__obj--${o.side}`}>
            {GLYPH[o.name] ?? o.name}
            <title>{`${clock(o.t)} ${(o.side === "a" ? set.a : set.b).team.acronym} ${o.name}${o.count > 1 ? ` ${o.count}마리` : ""}`}</title>
          </text>
        ))}
      </svg>
      </div>
      <figcaption>
        골드 차 흐름입니다. 위쪽은 {set.a.team.acronym}, 아래쪽은 {set.b.team.acronym} 가 앞선 구간이고, 글자는 그
        팀이 잡은 오브젝트, 가운데 점은 2킬 이상 나온 교전입니다.
      </figcaption>
    </figure>
  );
}
