"use client";

import { useState } from "react";
import { clock, type SetView } from "@/lib/sets";
import { DraftBoard } from "./DraftBoard";
import { FightList } from "./FightList";
import { ForecastCheck } from "./ForecastCheck";
import { GoldChart } from "./GoldChart";
import { Matchups } from "./Matchups";
import { JungleMap, KillMap } from "./RiftMap";
import { StatCompare } from "./StatCompare";
import { WinBar } from "./WinBar";

/** 세트를 골라 가며 밴픽, 승률, 기록, 교전, 맞대결을 본다. */
export function SetExplorer({ sets }: { sets: SetView[] }) {
  const [index, setIndex] = useState(0);
  const set = sets[index];
  const t = set.timeline;
  return (
    <div className="set">
      <div className="set__tabs" role="tablist" aria-label="세트 선택">
        {sets.map((s, i) => {
          const winner = s.a.won ? "a" : "b";
          return (
            <button
              key={s.number}
              type="button"
              role="tab"
              id={`set-tab-${s.number}`}
              aria-selected={i === index}
              aria-controls="set-panel"
              className={`set__tab set__tab--${winner}`}
              onClick={() => setIndex(i)}
            >
              <span className="set__tab-n">{s.number}세트</span>
              <span className="set__tab-w">
                {s[winner].team.acronym} 승{s.lengthMin ? `, ${Math.round(s.lengthMin)}분` : ""}
              </span>
            </button>
          );
        })}
      </div>

      <div className="set__panel" role="tabpanel" id="set-panel" aria-labelledby={`set-tab-${set.number}`} key={set.number}>
        <section className="set__part set__part--wide">
          <h3>밴픽</h3>
          <DraftBoard set={set} />
        </section>

        <section className="set__part">
          <h3>밴픽 직후 승률</h3>
          <WinBar set={set} />
        </section>

        <section className="set__part">
          <h3>세트 기록</h3>
          <StatCompare set={set} />
        </section>

        {t ? (
          <>
            <section className="set__part set__part--wide">
              <h3>
                흐름
                <span className="set__sub">
                  교전 {t.fightCount.total}회 ({set.a.team.acronym} 우세 {t.fightCount.a}, {set.b.team.acronym} 우세{" "}
                  {t.fightCount.b})
                  {t.firstBlood && `, 첫 킬 ${clock(t.firstBlood.t)} ${set[t.firstBlood.side].team.acronym}`}
                </span>
              </h3>
              <GoldChart set={set} timeline={t} />
            </section>
            <section className="set__part">
              <h3>킬 위치와 정글 동선</h3>
              <div className="set__maps">
                <KillMap set={set} timeline={t} />
                <JungleMap set={set} timeline={t} />
              </div>
            </section>
            <section className="set__part">
              <h3>큰 교전</h3>
              <FightList set={set} timeline={t} />
            </section>
          </>
        ) : (
          <p className="set__note set__part--wide">이 세트의 분 단위 기록(교전, 동선, 골드 흐름)은 아직 받지 못했습니다.</p>
        )}

        <section className="set__part set__part--wide">
          <h3>선수 맞대결</h3>
          <Matchups set={set} />
        </section>

        <section className="set__part set__part--wide">
          <h3>
            밴픽 예상과 실제
            <span className="set__sub">이 세트 직전까지의 기록만으로 낸 예상입니다.</span>
          </h3>
          <ForecastCheck set={set} />
        </section>
      </div>
    </div>
  );
}
