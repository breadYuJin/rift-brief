"use client";

import { useState } from "react";
import type { MockView } from "@/lib/sets";

/** AI 모의 밴픽을 한 수씩 넘겨 보는 판. 순서는 실제 밴픽 순서와 같다. */
export function MockPlayer({ mock }: { mock: MockView }) {
  const total = mock.moves.length;
  const [shown, setShown] = useState(total);
  const moves = mock.moves.slice(0, shown);
  const last = shown > 0 && shown < total ? mock.moves[shown - 1] : null;
  const column = (side: "a" | "b") => {
    const team = side === mock.firstSide ? mock.first : mock.second;
    const mine = moves.filter((m) => m.side === side);
    return (
      <div className={`pb__team pb__team--${side}`}>
        <p className="pb__head">
          <span className="pb__acr">{team.acronym}</span>
          <span className="pb__tags">{side === mock.firstSide ? "먼저 시작" : "나중 시작"}</span>
        </p>
        <ol className="pb__picks" aria-label={`${team.acronym} 예상 선택`}>
          {mine
            .filter((m) => m.kind === "pick")
            .map((m) => (
              <li key={m.champion} className="pb__pick">
                <span className="pb__role">{m.role}</span>
                <span className="pb__champ">{m.champion}</span>
              </li>
            ))}
        </ol>
        <ul className="pb__bans" aria-label={`${team.acronym} 예상 금지`}>
          {mine
            .filter((m) => m.kind === "ban")
            .map((m) => (
              <li key={m.champion}>{m.champion}</li>
            ))}
        </ul>
      </div>
    );
  };
  return (
    <div className="mock">
      <div className="mock__controls">
        <button type="button" onClick={() => setShown(0)} disabled={shown === 0}>
          처음부터
        </button>
        <button type="button" onClick={() => setShown((n) => Math.min(total, n + 1))} disabled={shown === total}>
          다음 수
        </button>
        <button type="button" onClick={() => setShown(total)} disabled={shown === total}>
          끝까지
        </button>
        <span className="mock__count" aria-live="polite">
          {shown} / {total}수
        </span>
      </div>
      {last && (
        <p className="mock__last" aria-live="polite">
          <strong>
            {(last.side === mock.firstSide ? mock.first : mock.second).acronym} {last.kind === "ban" ? "금지" : "선택"}: {last.champion}
          </strong>
          {last.reason && <span> ({last.reason})</span>}
        </p>
      )}
      <div className="pb pb--mock">
        {column("a")}
        {column("b")}
      </div>
      {mock.by === "llm" && shown === total && mock.commentary && <p className="mock__say">{mock.commentary}</p>}
    </div>
  );
}
