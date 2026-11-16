import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { TournamentView } from "@/components/TournamentView";
import { TOURNAMENTS, getTournament } from "@/content/tournaments";

export const dynamicParams = false;

// LCK 는 /rules/ 에서 보여 주므로 나머지 대회만 경로를 만든다.
export function generateStaticParams() {
  return TOURNAMENTS.filter((t) => t.slug !== "lck").map((t) => ({ slug: t.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const t = getTournament((await params).slug);
  return { title: t ? `대회 규칙: ${t.tab}` : "대회 규칙" };
}

export default async function TournamentPage({ params }: Props) {
  const t = getTournament((await params).slug);
  if (!t) notFound();
  return <TournamentView tournament={t} />;
}
