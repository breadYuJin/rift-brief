"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { Assets } from "@/lib/types";

const Ctx = createContext<Assets>({ logos: {}, iconBase: "", champs: {} });

export function AssetsProvider({ value, children }: { value: Assets; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** 그림이 열리지 않으면 아무것도 그리지 않는다. 이름은 늘 옆에 글자로 있으므로 그림은 장식이다. */
function Picture({ src, size, className }: { src: string; size: number; className: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) return null;
  return (
    // 외부 이미지 서버의 그림을 그대로 불러온다(정적 사이트라 이미지 최적화 서버가 없다).
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className={className}
      onError={() => setBroken(true)}
    />
  );
}

export function TeamLogo({ id, size = 20, className = "" }: { id: number; size?: number; className?: string }) {
  const src = useContext(Ctx).logos[String(id)];
  return src ? <Picture src={src} size={size} className={`logo ${className}`} /> : null;
}

export function ChampIcon({ name, size = 24, className = "" }: { name: string; size?: number; className?: string }) {
  const { iconBase, champs } = useContext(Ctx);
  const file = champs[name];
  return iconBase && file ? (
    <Picture src={`${iconBase}${file}.png`} size={size} className={`champ ${className}`} />
  ) : null;
}
