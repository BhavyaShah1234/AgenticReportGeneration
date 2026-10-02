import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Proxy API calls to FastAPI so the browser stays same-origin (session cookie just works).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  experimental: {
    // Report generation (queries + LLM narrative + PDF) is synchronous and can take a while.
    proxyTimeout: 300_000,
  },
};

export default nextConfig;
