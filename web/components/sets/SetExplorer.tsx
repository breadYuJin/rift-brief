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
export function SetExplorer({
  sets,
  matchId,
  repoUrl,
  minVotes = 3,
}: {
  sets: SetView[];
  matchId: number;
  /** 평점 의견을 받는 GitHub 저장소 주소. 비어 있으면 의견 보내기를 감춘다. */
  repoUrl: string;
  minVotes?: number;
}) {
  const [index, setIndex] = useState(0);
  const set = sets[index];
  const t = set.timeline;
  // 의견 보내기: 이 세트의 선수 이름이 미리 적힌 GitHub 이슈 작성 화면을 연다. 점수만 채워 제출하면 된다.
  const names = set.matchups.flatMap((m) => [m.a.player, m.b.player]);
  const body = [
    `경기: ${matchId}`,
    `세트: ${set.number}`,
    "",
    "의견이 있는 선수만 이름 옆에 1~10 사이 점수를 적어 주세요. 비워 둔 줄은 반영되지 않습니다.",
    "",
    ...names.map((n) => `${n}: `),
  ].join("\n");
  const feedbackUrl =
    repoUrl && names.length > 0
      ? `${repoUrl}/issues/new?title=${encodeURIComponent(
          `[평점] ${set.a.team.acronym} 대 ${set.b.team.acronym} ${set.number}세트`,
        )}&body=${encodeURIComponent(body)}`
      : "";
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
          <h3>
            선수 맞대결과 평점
            {(set.best || set.officialMvp) && (
              <span className="set__sub">
                {set.best && `세트 최고 평점 ${set.best.player} ${set.best.rating.toFixed(1)}`}
                {set.best && set.officialMvp && ", "}
                {set.officialMvp && `주최 측 세트 MVP ${set.officialMvp}`}
              </span>
            )}
          </h3>
          <Matchups set={set} />
          {feedbackUrl && (
            <p className="set__note set__feedback">
              평점이 다르다고 생각하면{" "}
              <a href={feedbackUrl} target="_blank" rel="noopener noreferrer">
                의견 보내기
              </a>
              . GitHub 계정이 필요합니다. 한 선수에 {minVotes}명 이상 모이면 평점에 일부 반영됩니다.
            </p>
          )}
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
