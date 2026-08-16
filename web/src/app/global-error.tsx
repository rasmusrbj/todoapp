'use client'

import { useEffect } from 'react'

import './globals.css'

/**
 * The last-resort boundary, for a failure in the root layout itself.
 *
 * It has to render its own `<html>` and `<body>`, because the layout that normally
 * provides them is the thing that failed. That also means no translations: the
 * `NextIntlClientProvider` lives in that same layout, so `useTranslations` here would
 * throw and take the boundary down with it. The two strings below are therefore the
 * only hardcoded copy in the app, and they are duplicated per language rather than
 * translated — which is the honest trade at this depth.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[global error]', error.digest ?? error.message)
  }, [error])

  return (
    <html lang="da" suppressHydrationWarning>
      <body className="antialiased">
        <div
          style={{
            minHeight: '100svh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
            fontFamily:
              '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
          }}
        >
          <div style={{ maxWidth: '28rem', textAlign: 'center' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 600, margin: 0 }}>
              Noget gik galt · Something went wrong
            </h1>
            <p style={{ marginTop: '0.5rem', opacity: 0.7 }}>
              Prøv igen om et øjeblik. · Give it another go in a moment.
            </p>
            <button
              type="button"
              onClick={reset}
              style={{
                marginTop: '1.5rem',
                cursor: 'pointer',
                borderRadius: '0.5rem',
                border: '1px solid currentColor',
                background: 'transparent',
                padding: '0.5rem 1rem',
                font: 'inherit',
                color: 'inherit',
              }}
            >
              Prøv igen · Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}
