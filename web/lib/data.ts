import fs from "node:fs";
import path from "node:path";
import type {
  Assets,
  Award,
  Brief,
  ChampionTable,
  CollectEntry,
  DraftIndex,
  League,
  MatchSets,
  Meta,
  Models,
  PatchMeta,
  PlayerAverage,
  Preview,
} from "./types";

// 파이프라인이 레포 루트의 data/ 에 커밋한 JSON 을 빌드 시점에 읽는다.
const DATA_DIR = path.join(process.cwd(), "..", "data");

// 빌드 중에는 파일이 바뀌지 않으므로 한 번 읽은 것을 다시 쓴다(경기 페이지마다 같은 파일을 읽는다).
// 개발 서버에서는 데이터를 고치면 바로 보이도록 매번 읽는다.
const cache = new Map<string, unknown>();
const useCache = process.env.NODE_ENV === "production";

/** data/ 의 JSON 파일을 읽는다. 없거나 읽을 수 없으면 fallback. */
function read<T>(file: string, fallback: T): T {
  if (useCache && cache.has(file)) return cache.get(file) as T;
  let value: T;
  try {
    value = JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf-8")) as T;
  } catch {
    value = fallback;
  }
  if (useCache) cache.set(file, value);
  return value;
}

// ---- 브리핑·프리뷰·리그 ----

export const getResults = () => read<Brief[]>("results.json", []);
export const getPreviews = () => read<Preview[]>("previews.json", []);
export const getLeagues = () => read<League[]>("leagues.json", []);
export const getMeta = () => read<Meta>("meta.json", { updated_at: null, sample: false, llm: "template" });
export const getCollectStatus = () => read<Record<string, CollectEntry>>("collect.json", {});

// ---- 세트 상세·예측·평점 ----

export const getMatchSets = (matchId: number | string) => read<MatchSets | null>(`sets/${matchId}.json`, null);
export const getModels = () => read<Models | null>("models.json", null);
export const getDraftIndex = () => read<DraftIndex>("draft.json", { recent: [], upcoming: [] });
export const getPlayers = () => read<Record<string, PlayerAverage[]>>("players.json", {});
export const getPatches = () => read<PatchMeta[]>("patches.json", []);
/** 경기 ID → 대회 종료 후 상 */
export const getAwards = () => read<Record<string, Award>>("awards.json", {});

// ---- 챔피언 이름과 그림 ----

const getChampionTable = () => read<ChampionTable | null>("champions.json", null);

/** 기록에 적힌 영어 챔피언 이름을 한국어 이름으로 바꾼다. 이름표가 없거나 모르는 이름이면 그대로 돌려준다. */
export function championName(english: string): string {
  const key = english.toLowerCase().replace(/[^a-z0-9]/g, "");
  return getChampionTable()?.champions[key]?.ko ?? english;
}

/** 팀 로고와 챔피언 아이콘 주소 묶음(레이아웃이 화면 전체에 내려 준다). */
export function getAssets(): Assets {
  const teams = read<Record<string, { logo?: string }>>("teams.json", {});
  const table = getChampionTable();
  const champs: Record<string, string> = {};
  for (const c of Object.values(table?.champions ?? {})) {
    champs[c.ko] = c.id;
    champs[c.en] = c.id;
  }
  return {
    logos: Object.fromEntries(Object.entries(teams).flatMap(([id, t]) => (t.logo ? [[id, t.logo]] : []))),
    iconBase: table?.icon_base ?? "",
    champs,
  };
}
