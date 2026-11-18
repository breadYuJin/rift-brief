/** 다섯 칸 가운데 평균 몇 칸을 맞혔는지 보여 주는 띠. */
export function Slots({ value, kind }: { value: number; kind: "pick" | "ban" }) {
  return (
    <span className={`slots slots--${kind}`} aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <span key={i} className="slots__cell">
          <span style={{ width: `${Math.max(0, Math.min(1, value - i)) * 100}%` }} />
        </span>
      ))}
    </span>
  );
}

/** 예상 순위별 적중률 막대(1~10순위). */
export function RankBars({ rates, kind }: { rates: number[]; kind: "pick" | "ban" }) {
  const top = Math.max(...rates, 0.01);
  return (
    <ol className={`rank rank--${kind}`}>
      {rates.map((r, i) => (
        <li key={i}>
          <span className="rank__bar" style={{ height: `${(r / top) * 100}%` }} aria-hidden="true" />
          <span className="rank__pct">{Math.round(r * 100)}</span>
          <span className="rank__n">{i + 1}순위</span>
        </li>
      ))}
    </ol>
  );
}

/** 승률 모델 비교 막대. */
export function WinBars({ rows }: { rows: { key: string; label: string; value: number }[] }) {
  return (
    <ul className="winbars">
      {rows.map((b) => (
        <li key={b.key} className={`winbars__row winbars__row--${b.key}`}>
          <span className="winbars__label">{b.label}</span>
          <span className="winbars__track" aria-hidden="true">
            <span style={{ width: `${b.value * 100}%` }} />
          </span>
          <strong className="winbars__num">{(b.value * 100).toFixed(1)}%</strong>
        </li>
      ))}
    </ul>
  );
}
