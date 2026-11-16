import type { NextConfig } from "next";

// GitHub Pages 프로젝트 사이트는 /<레포명>/ 아래에서 서빙된다.
// 배포 워크플로가 NEXT_PUBLIC_BASE_PATH 를 넣어 준다. 로컬에서는 비워 둔다.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  images: { unoptimized: true },
};

export default config;
