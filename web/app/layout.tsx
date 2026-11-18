import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
import { AssetsProvider } from "@/components/Assets";
import { getAssets, getMeta } from "@/lib/data";
import { formatStamp } from "@/lib/format";
import { REPO_URL, SITE_NAME, SITE_TAGLINE } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description: `${SITE_TAGLINE}. 주요 경기, 리그 일정, 팀 전적, 대회 규칙을 한곳에서 봅니다.`,
};

export const viewport: Viewport = { themeColor: "#12213a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const meta = getMeta();
  return (
    <html lang="ko" data-scroll-behavior="smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap"
        />
      </head>
      <body>
        <AssetsProvider value={getAssets()}>
          <a className="skip" href="#main">
            본문으로 건너뛰기
          </a>
          <header className="site-header">
            <div className="wrap site-header__inner">
              <Link href="/" className="site-header__name">
                {SITE_NAME}
              </Link>
              <SiteNav />
            </div>
          </header>
          {meta.sample && (
            <p className="notice" role="note">
              <span className="wrap">지금 보이는 팀과 경기는 화면 확인용 샘플입니다. 실제 팀이나 경기가 아닙니다.</span>
            </p>
          )}
          {meta.source === "archive" && (
            <p className="notice notice--quiet" role="note">
              <span className="wrap">경기 기록은 하루 몇 차례 자동으로 갱신됩니다 ({meta.source_note}).</span>
            </p>
          )}
          <main id="main" className="wrap">
            {children}
          </main>
          <footer className="site-footer">
            <div className="wrap">
              <p>
                {meta.updated_at && <>마지막 갱신 {formatStamp(meta.updated_at)} (한국 시간). </>}
                {meta.source === "archive" ? (
                  <>
                    경기 기록 출처는 <a href="https://lol.fandom.com/">Leaguepedia</a>이며 CC BY-SA 라이선스를 따릅니다.
                  </>
                ) : (
                  <>경기 데이터는 PandaScore API에서 가져오며, 진행 중 표시는 마지막 갱신 시점 기준입니다.</>
                )}
              </p>
              <p>
                요약과 예측은 자동으로 만들어져 틀릴 수 있습니다. 예측은 재미로 보는 참고용이며 베팅 용도가 아닙니다.
              </p>
              <p>
                협곡 브리핑은 팬이 만든 비공식 사이트입니다. Riot Games가 보증하거나 후원하지 않으며, Riot Games나 리그
                오브 레전드의 제작·운영에 공식적으로 관여하는 누구의 견해도 반영하지 않습니다. 리그 오브 레전드와 Riot
                Games는 Riot Games, Inc.의 상표 또는 등록 상표입니다. 챔피언 이미지는 Riot Games의 자산이고, 팀 로고는
                각 팀의 자산입니다.
              </p>
              {REPO_URL && (
                <p>
                  <a href={REPO_URL}>GitHub에서 소스 보기</a>
                </p>
              )}
            </div>
          </footer>
        </AssetsProvider>
      </body>
    </html>
  );
}
