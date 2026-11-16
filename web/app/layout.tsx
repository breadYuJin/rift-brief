import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
import { getMeta } from "@/lib/data";
import { formatStamp } from "@/lib/format";
import { REPO_URL, SITE_NAME, SITE_TAGLINE } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
  description: `${SITE_TAGLINE}. 멀티에이전트가 경기 데이터를 모아 요약하고 사실 여부를 다시 확인합니다.`,
};

export const viewport: Viewport = { themeColor: "#12213a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const meta = getMeta();
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap"
        />
      </head>
      <body>
        <a className="skip" href="#main">
          본문으로 건너뛰기
        </a>
        <header className="site-header">
          <div className="wrap">
            <Link href="/" className="site-header__name">
              {SITE_NAME}
            </Link>
            <p className="site-header__tagline">{SITE_TAGLINE}</p>
            <SiteNav />
          </div>
        </header>
        {meta.sample && (
          <p className="notice" role="note">
            <span className="wrap">
              지금 보이는 팀과 경기는 화면 확인용 샘플입니다. 실제 팀이나 경기가 아닙니다.
            </span>
          </p>
        )}
        <main id="main" className="wrap">
          {children}
        </main>
        <footer className="site-footer">
          <div className="wrap">
            <p>
              {meta.updated_at && <>마지막 갱신 {formatStamp(meta.updated_at)} (한국 시간). </>}
              경기 데이터는 PandaScore API에서 가져옵니다.
            </p>
            <p>
              요약은 자동으로 작성되어 틀릴 수 있습니다. 이 사이트는 팬이 만든 비공식 사이트이며 Riot Games와
              관련이 없습니다.
            </p>
            {REPO_URL && (
              <p>
                <a href={REPO_URL}>GitHub에서 소스 보기</a>
              </p>
            )}
          </div>
        </footer>
      </body>
    </html>
  );
}
