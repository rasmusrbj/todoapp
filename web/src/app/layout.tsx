import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { getLocale, getMessages, getTranslations } from 'next-intl/server'
import { NextIntlClientProvider } from 'next-intl'

import { Providers } from '@/components/providers'
import { intlTags, type Locale } from '@/i18n/config'

import './globals.css'

// Self-hosted by next/font: no request to a third-party font CDN, and no layout
// shift while the font loads.
const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('app')
  return {
    title: { default: t('name'), template: `%s · ${t('name')}` },
    description: t('tagline'),
    // Every string in the shell is localized, including the browser tab.
    applicationName: t('name'),
    robots: { index: false, follow: false },
  }
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: 'oklch(1 0 0)' },
    { media: '(prefers-color-scheme: dark)', color: 'oklch(0.145 0 0)' },
  ],
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // The locale comes from the cookie via src/i18n/request.ts, so the first byte is
  // already in the right language — no client-side swap.
  const locale = (await getLocale()) as Locale
  const messages = await getMessages()

  return (
    <html lang={intlTags[locale]} suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
