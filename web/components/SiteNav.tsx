"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "경기 결과" },
  { href: "/upcoming/", label: "예정 경기" },
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
