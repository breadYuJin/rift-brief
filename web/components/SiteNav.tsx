"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "홈" },
  { href: "/schedule/", label: "리그 일정" },
  { href: "/upcoming/", label: "예정 경기" },
  { href: "/teams/", label: "팀 전적" },
  { href: "/draft/", label: "밴픽 예측" },
  { href: "/rules/", label: "대회 규칙" },
  { href: "/terms/", label: "밴픽·용어" },
  { href: "/about/", label: "만드는 방식" },
];

export function SiteNav() {
  const pathname = usePathname();
  const isCurrent = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/matches") : pathname.startsWith(href);
  return (
    <nav className="nav" aria-label="주요 메뉴">
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className="nav__link" aria-current={isCurrent(l.href) ? "page" : undefined}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
