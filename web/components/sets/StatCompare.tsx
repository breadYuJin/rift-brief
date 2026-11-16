import type { SetView } from "@/lib/sets";

const ROWS: { key: "kills" | "gold" | "towers" | "dragons" | "barons" | "grubs" | "heralds"; label: string }[] = [
  { key: "kills", label: "킬" },
  { key: "gold", label: "골드" },
  { key: "towers", label: "타워" },
  { key: "dragons", label: "드래곤" },
  { key: "barons", label: "바론" },
  { key: "grubs", label: "공허 유충" },
  { key: "heralds", label: "전령" },
];

const show = (key: string, v: number) => (key === "gold" ? `${(v / 1000).toFixed(1)}k` : String(v));

/** 두 팀의 세트 기록을 가운데 기준선에서 좌우로 뻗는 막대로 비교한다. */
export function StatCompare({ set }: { set: SetView }) {
  return (
    <dl className="cmp">
      {ROWS.map(({ key, label }) => {
        const a = set.a.stats[key];
        const b = set.b.stats[key];
        if (a + b === 0) return null;
        return (
          <div key={key} className="cmp__row">
            <dt>{label}</dt>
            <dd className={`cmp__a${a > b ? " is-more" : ""}`}>
              <span className="cmp__num">{show(key, a)}</span>
              <span className="cmp__bar" style={{ width: `${(a / (a + b)) * 100}%` }} aria-hidden="true" />
            </dd>
            <dd className={`cmp__b${b > a ? " is-more" : ""}`}>
              <span className="cmp__bar" style={{ width: `${(b / (a + b)) * 100}%` }} aria-hidden="true" />
              <span className="cmp__num">{show(key, b)}</span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
