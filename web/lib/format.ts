const KST = "Asia/Seoul";

const dayFmt = new Intl.DateTimeFormat("ko-KR", { timeZone: KST, month: "long", day: "numeric", weekday: "long" });
const shortDayFmt = new Intl.DateTimeFormat("ko-KR", { timeZone: KST, month: "long", day: "numeric" });
const timeFmt = new Intl.DateTimeFormat("ko-KR", { timeZone: KST, hour: "2-digit", minute: "2-digit", hour12: false });
const stampFmt = new Intl.DateTimeFormat("ko-KR", {
  timeZone: KST,
  month: "long",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** "11월 15일 일요일" (한국 시간 기준) */
export const formatDay = (iso: string | null) => (iso ? dayFmt.format(new Date(iso)) : "날짜 미정");
/** "11월 15일" (한국 시간 기준) */
export const formatShortDay = (iso: string | null) => (iso ? shortDayFmt.format(new Date(iso)) : "날짜 미정");
/** "18:00" (한국 시간 기준) */
export const formatTime = (iso: string | null) => (iso ? timeFmt.format(new Date(iso)) : "");
export const formatStamp = (iso: string | null) => (iso ? stampFmt.format(new Date(iso)) : "");

export function groupByDay<T>(items: T[], getIso: (item: T) => string | null): [string, T[]][] {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = formatDay(getIso(item));
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return [...groups.entries()];
}

/** 0.42 → "42%" */
export const pct = (p: number) => `${Math.round(p * 100)}%`;

/** 선수 이름 비교(대소문자 무시). 기록마다 표기가 조금씩 다르다. */
export const samePlayer = (a: string | null | undefined, b: string) => !!a && a.toLowerCase() === b.toLowerCase();
