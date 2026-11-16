import type { Metadata } from "next";
import { TournamentView } from "@/components/TournamentView";
import { TOURNAMENTS } from "@/content/tournaments";

export const metadata: Metadata = { title: "대회 규칙: LCK" };

// 대회 규칙의 첫 화면은 LCK 다.
export default function RulesPage() {
  return <TournamentView tournament={TOURNAMENTS[0]} />;
}
