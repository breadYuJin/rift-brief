"use client";

import { useState } from "react";
import { pct } from "@/lib/format";
import { ChampIcon } from "./Assets";

export interface PatchView {
  patch: string;
  sets: number;
  period: string;
  leagues: string;
  champions: {
    name: string;
    role: string;
    picks: number;
    bans: number;
    presence: number;
    winRate: number | null;
    change: number | null;
  }[];
}

/** 패치를 골라, 그 패치가 적용된 공식 경기에서 많이 나온 챔피언을 본다. 막대의 진한 부분이 픽, 연한 부분이 밴이다. */
export function PatchMeta({ patches }: { patches: PatchView[] }) {
  const [index, setIndex] = useState(0);
  const patch = patches[index];
  if (!patch) return null;
  return (
    <div className="meta">
      <div className="meta__tabs" role="tablist" aria-label="패치 선택">
        {patches.map((p, i) => (
          <button
            key={p.patch}
            type="button"
            role="tab"
            aria-selected={i === index}
            aria-controls="meta-panel"
            id={`meta-tab-${i}`}
            className="meta__tab"
            onClick={() => setIndex(i)}
          >
            <span className="meta__patch">{p.patch}</span>
            <span className="meta__where">{p.leagues}</span>
          </button>
        ))}
      </div>
      <div
        className="meta__panel"
        role="tabpanel"
        id="meta-panel"
        aria-labelledby={`meta-tab-${index}`}
        key={patch.patch}
      >
        <p className="meta__basis">
          {patch.period}, 공식 경기 {patch.sets}세트 기준. 밴픽률은 그 챔피언이 선택되거나 금지된 세트의 비율입니다.
        </p>
        <ol className="meta__list">
          {patch.champions.map((c, i) => {
            const pickShare = c.picks / patch.sets;
            const banShare = c.bans / patch.sets;
            return (
              <li key={c.name} className="meta__row">
                <span className="meta__rank">{i + 1}</span>
                <ChampIcon name={c.name} size={32} />
                <span className="meta__who">
                  <strong>{c.name}</strong>
                  <span>{c.role || "금지만 됨"}</span>
                </span>
                <span className="meta__bar" aria-hidden="true">
                  <span className="meta__bar-pick" style={{ width: `${pickShare * 100}%` }} />
                  <span className="meta__bar-ban" style={{ width: `${banShare * 100}%` }} />
                </span>
                <span className="meta__num">
                  <strong>{pct(c.presence)}</strong>
                  <span>
                    픽 {c.picks}, 밴 {c.bans}
                  </span>
                </span>
                <span className="meta__win">
                  {c.winRate !== null && c.picks >= 5 ? (
                    <>
                      <strong>{pct(c.winRate)}</strong>
                      <span>승률</span>
                    </>
                  ) : (
                    <span>표본 적음</span>
                  )}
                </span>
                <span
                  className={`meta__change${c.change === null ? "" : c.change >= 0.1 ? " is-up" : c.change <= -0.1 ? " is-down" : ""}`}
                >
                  {c.change === null ? "" : `${c.change > 0 ? "+" : ""}${Math.round(c.change * 100)}%p`}
                </span>
              </li>
            );
          })}
        </ol>
        <p className="meta__basis meta__basis--wide">맨 오른쪽 숫자는 직전 패치와 견준 밴픽률 변화입니다.</p>
      </div>
    </div>
  );
}
