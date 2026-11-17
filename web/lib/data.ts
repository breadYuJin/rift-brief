import fs from "node:fs";
import path from "node:path";
import type { Brief, ChampionTable, DraftIndex, League, MatchSets, Meta, Models, PlayerAverage, Preview } from "./types";

// 파이프라인이 레포 루트의 data/ 에 커밋한 JSON 을 빌드 시점에 읽는다.
const DATA_DIR = path.join(process.cwd(), "..", "data");

function read<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf-8")) as T;
  } catch {
    return fallback;
  }
}

export const getResults = () => read<Brief[]>("results.json", []);
export const getPreviews = () => read<Preview[]>("previews.json", []);
export const getLeagues = () => read<League[]>("leagues.json", []);
export const getMeta = () => read<Meta>("meta.json", { updated_at: null, sample: false, llm: "template" });

// ---- 세트 상세·예측 ----

export const getMatchSets = (matchId: number | string) => read<MatchSets | null>(`sets/${matchId}.json`, null);
export const getModels = () => read<Models | null>("models.json", null);
export const getDraftIndex = () => read<DraftIndex>("draft.json", { recent: [], upcoming: [] });
export const getPlayers = () => read<Record<string, PlayerAverage[]>>("players.json", {});

let championTable: ChampionTable | null | undefined;

/** 기록에 적힌 영어 챔피언 이름을 한국어 이름으로 바꾼다. 이름표가 없거나 모르는 이름이면 그대로 돌려준다. */
export function championName(english: string): string {
  if (championTable === undefined) championTable = read<ChampionTable | null>("champions.json", null);
  const key = english.toLowerCase().replace(/[^a-z0-9]/g, "");
  return championTable?.champions[key]?.ko ?? english;
}

export interface CollectEntry {
  what: string;
  needs: string;
  state: "수집됨" | "키 없음" | "준비 중" | "실패";
  note: string;
  at?: string;
}

export const getCollectStatus = () => read<Record<string, CollectEntry>>("collect.json", {});

/** 팀 로고와 챔피언 아이콘 주소 묶음(레이아웃이 화면 전체에 내려 준다). */
export function getAssets() {
  const teams = read<Record<string, { logo?: string }>>("teams.json", {});
  const table = read<(ChampionTable & { icon_base?: string }) | null>("champions.json", null);
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

export interface PatchMeta {
  patch: string;
  sets: number;
  from: string;
  to: string;
  leagues: string[];
  champions: {
    champion: string;
    picks: number;
    bans: number;
    presence: number;
    win_rate: number | null;
    role: string;
    change: number | null;
  }[];
}

export const getPatches = () => read<PatchMeta[]>("patches.json", []);

/** 대회가 끝난 뒤 따로 발표되는 상(파이널 MVP 등). 경기 ID 별. 보도로 확인한 것만 들어 있다. */
export interface Award {
  award: string;
  player: string;
  source: string;
}

export const getAwards = () => read<Record<string, Award>>("awards.json", {});
