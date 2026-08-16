import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merges class names, letting a later Tailwind class win over an earlier one. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Fallback label for a dialog's close button.
 *
 * The Happenings `Dialog` calls this when no `closeLabel` prop is given, from a
 * non-component context where a translation hook is unavailable — hence reading the
 * locale cookie directly. Every dialog in this app passes `closeLabel` explicitly, so
 * this is only ever the safety net.
 */
export function getCloseLabel(): string {
  if (typeof document !== 'undefined') {
    const locale = document.cookie.match(/todoapp_locale=(da|en)/)?.[1]
    return locale === 'en' ? 'Close' : 'Luk'
  }
  return 'Luk'
}
