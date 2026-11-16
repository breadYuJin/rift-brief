/** 최근 전적 표시. 왼쪽이 오래된 경기, 오른쪽이 가장 최근 경기. 채운 칸이 승리. */
export function FormPips({ recent, side }: { recent?: boolean[]; side?: "a" | "b" }) {
  if (!recent || recent.length === 0) return null;
  const wins = recent.filter(Boolean).length;
  const label = `최근 ${recent.length}경기 ${wins}승 ${recent.length - wins}패`;
  return (
    <span className={`pips${side ? ` pips--${side}` : ""}`} role="img" aria-label={label} title={label}>
      {[...recent].reverse().map((won, i) => (
        <span key={i} className={`pips__pip${won ? " is-win" : ""}`} />
      ))}
    </span>
  );
}
