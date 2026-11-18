import { pct } from "@/lib/format";
import { type SetView } from "@/lib/sets";

function Row({ label, p }: { label: string; p: number }) {
  return (
    <div className="win__row">
      <span className="win__label">{label}</span>
      <span className="win__num win__num--a">{pct(p)}</span>
      <span className="win__bar" aria-hidden="true">
        <span style={{ width: `${p * 100}%` }} />
      </span>
      <span className="win__num win__num--b">{pct(1 - p)}</span>
    </div>
  );
}

/** 밴픽이 끝난 시점에 한 번 계산한 승률. 밴픽 전(전력만 본 값)과 나란히 둔다. */
export function WinBar({ set }: { set: SetView }) {
  if (!set.win) {
    return <p className="set__note">시즌 초반 세트라 쌓인 기록이 모자라 승률을 계산하지 않았습니다.</p>;
  }
  const { before, after } = set.win;
  const favored = after >= 0.5 ? set.a : set.b;
  return (
    <div className="win">
      <Row label="밴픽 전" p={before} />
      <Row label="밴픽 후" p={after} />
      <p className="set__note">
        모델은 {favored.team.acronym} 쪽을 높게 봤고, 실제로는 {(set.a.won ? set.a : set.b).team.acronym}
        {favored.won ? "가 이겼습니다." : "가 이겨 빗나갔습니다."}
      </p>
    </div>
  );
}
