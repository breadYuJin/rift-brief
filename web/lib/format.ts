const KST = "Asia/Seoul";

const dayFmt = new Intl.DateTimeFormat("ko-KR", { timeZone: KST, month: "long", day: "numeric", weekday: "long" });
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
