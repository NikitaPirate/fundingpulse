import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const eslintConfig = [
  {
    ignores: ["public/mockServiceWorker.js"],
  },
  ...nextCoreWebVitals,
  ...nextTypeScript,
];

export default eslintConfig;
