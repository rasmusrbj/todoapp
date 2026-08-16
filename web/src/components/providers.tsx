'use client'

import { config as fontAwesomeConfig } from '@fortawesome/fontawesome-svg-core'
import { ThemeProvider } from 'next-themes'

import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'

// next/font already injects the stylesheet, so Font Awesome must not add its own.
// Without this, icons briefly render at their natural size before the CSS lands.
fontAwesomeConfig.autoAddCss = false

/** Client-side context every page needs: theme, tooltips, and toasts. */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      // The theme flips instantly; animating it just draws attention to the flash.
      disableTransitionOnChange
    >
      <TooltipProvider delayDuration={200}>
        {children}
        <Toaster position="bottom-right" />
      </TooltipProvider>
    </ThemeProvider>
  )
}
