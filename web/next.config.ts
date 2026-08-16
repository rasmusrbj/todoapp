import type { NextConfig } from 'next'
import createNextIntlPlugin from 'next-intl/plugin'

// Points next-intl at the request-scoped config that resolves the cookie locale.
const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts')

const nextConfig: NextConfig = {
  // Fail the build on a type error rather than shipping one.
  typescript: { ignoreBuildErrors: false },
  // The API token lives in an HttpOnly cookie that only the Next server reads, so
  // no backend URL is ever exposed to the browser bundle.
  serverExternalPackages: [],
  experimental: {
    // Server Actions are the only write path; 1 MB is ample for our payloads.
    serverActions: { bodySizeLimit: '1mb' },
  },
}

export default withNextIntl(nextConfig)
