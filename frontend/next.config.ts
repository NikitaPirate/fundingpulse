import type { NextConfig } from "next";

const internalApiBaseUrl =
  process.env.FUNDING_API_INTERNAL_BASE_URL?.replace(/\/$/, "") ?? "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiBaseUrl}/api/:path*`,
      },
    ];
  },
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
