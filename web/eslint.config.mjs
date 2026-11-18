// 웹 코드 규칙: Next.js 권장 규칙(React, 훅, 접근성, 성능)에 TypeScript 규칙을 더한다. 실행: npm run lint
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  {
    ignores: [".next/**", "out/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    rules: {
      // App Router 의 루트 레이아웃에 넣은 글꼴은 모든 페이지에 적용된다(이 규칙은 Pages Router 용이다).
      "@next/next/no-page-custom-font": "off",
    },
  },
];

export default config;
