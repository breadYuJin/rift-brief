import type { SetView } from "./sets";

/**
 * 평점 의견은 GitHub 이슈로 받는다. 제목은 "[평점]" 으로 시작하고, 본문의 "경기:", "세트:", "선수: 점수" 줄을
 * 파이프라인(pipeline/feedback.py)이 읽는다. 이 형식을 바꾸면 그쪽도 함께 바꿔야 한다.
 */
export const FEEDBACK_TITLE_PREFIX = "[평점]";

/** 이 세트의 선수 이름이 미리 적힌 이슈 작성 화면 주소. 저장소 주소가 없으면 빈 문자열. */
export function ratingFeedbackUrl(repoUrl: string, matchId: number, set: SetView): string {
  const names = set.matchups.flatMap((m) => [m.a.player, m.b.player]);
  if (!repoUrl || names.length === 0) return "";
  const title = `${FEEDBACK_TITLE_PREFIX} ${set.a.team.acronym} 대 ${set.b.team.acronym} ${set.number}세트`;
  const body = [
    `경기: ${matchId}`,
    `세트: ${set.number}`,
    "",
    "의견이 있는 선수만 이름 옆에 1~10 사이 점수를 적어 주세요. 비워 둔 줄은 반영되지 않습니다.",
    "",
    ...names.map((n) => `${n}: `),
  ].join("\n");
  return `${repoUrl}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

/** 지금까지 온 평점 의견 목록(로그인 없이 볼 수 있다). */
export const ratingFeedbackListUrl = (repoUrl: string) =>
  `${repoUrl}/issues?q=${encodeURIComponent(`is:issue ${FEEDBACK_TITLE_PREFIX} in:title`)}`;
