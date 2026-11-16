import fs from "node:fs";
import path from "node:path";
import type { Brief, Meta, Preview } from "./types";

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
export const getMeta = () => read<Meta>("meta.json", { updated_at: null, sample: false, llm: "template" });
