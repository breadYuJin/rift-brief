import { samePlayer } from "./format";
import type { Award, Match } from "./types";

/**
 * 주최 측이 뽑은 선수를 어떻게 부를지 정한다. 서로 다른 상을 섞지 않는다.
 *
 * - 경기 기록에 적힌 선수(match.mvp): 이름이 확인된 단계에서만 그 이름으로 부른다.
 *   LCK 정규 시즌은 POM, 국제 대회의 결승이 아닌 경기는 경기 MVP, 그 밖에는 "주최 측 선정"이라고만 한다.
 * - 대회가 끝난 뒤 따로 발표되는 상(파이널 MVP 등)은 award 로만 받는다. 경기 기록에서 미루어 붙이지 않는다.
 */
export interface OfficialPicks {
  /** 경기 기록에 적힌 선수와, 그 선수를 소개하는 문구 */
  pick: { player: string; heading: string; tag: string } | null;
  award: Award | null;
  /** 선수 이름 옆에 붙일 이름표. 대회 종료 후 상이 우선이다. */
  tagFor: (player: string) => string;
}

export function officialPicks(match: Match, award: Award | null): OfficialPicks {
  const isFinal = match.round === "결승";
  const named =
    match.league === "LCK" && match.tournament?.startsWith("정규 시즌")
      ? "POM"
      : match.league !== "LCK" && !isFinal
        ? "경기 MVP"
        : null;
  const pick = match.mvp
    ? {
        player: match.mvp,
        heading: isFinal
          ? "이 경기 기록에 적힌 주최 측 선정 선수"
          : named
            ? `주최 측 선정 ${named}`
            : "주최 측 선정 선수",
        tag: named ?? "주최 측 선정",
      }
    : null;
  return {
    pick,
    award,
    tagFor: (player) =>
      award && samePlayer(award.player, player) ? award.award : pick && samePlayer(pick.player, player) ? pick.tag : "",
  };
}
