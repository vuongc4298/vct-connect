import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingIncludes: {
    "/api/v1/extension-download": ["./private/vct-connect-extension.zip"],
  },
};

export default nextConfig;
