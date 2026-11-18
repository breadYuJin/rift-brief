import type { OfficialPicks as Picks } from "@/lib/official";

/** 경기 카드 아래: 대회 종료 후 상(출처와 함께)과 경기 기록에 적힌 주최 측 선정 선수. */
export function OfficialPicks({ picks }: { picks: Picks }) {
  const { award, pick } = picks;
  if (!award && !pick) return null;
  return (
    <dl className="official">
      {award && (
        <div>
          <dt>대회 종료 후 선정된 {award.award}</dt>
          <dd>
            <strong>{award.player}</strong>
            <a href={award.source} target="_blank" rel="noopener noreferrer">
              출처
            </a>
          </dd>
        </div>
      )}
      {pick && (
        <div>
          <dt>{pick.heading}</dt>
          <dd>
            <strong>{pick.player}</strong>
          </dd>
        </div>
      )}
    </dl>
  );
}
