import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  // ponytail: standalone only for the optional Docker image; Vercel keeps its own output
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" as const } : {}),
};

const withNextIntl = createNextIntlPlugin();
export default withNextIntl(nextConfig);
