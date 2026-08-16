import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { ResetPasswordForm } from './reset-password-form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { asLocale } from '@/i18n/config'
import { setLocaleCookie } from '@/lib/session'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('auth')
  return { title: t('resetTitle') }
}

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string; lang?: string }>
}) {
  const { token, lang } = await searchParams

  // The email was written in the account's language; honour it so the page the link
  // opens matches the message that carried it.
  const requested = asLocale(lang)
  if (requested) {
    await setLocaleCookie(requested)
  }

  const t = await getTranslations('auth')

  return (
    <Card className="rounded-xl p-2 sm:p-3">
      <CardHeader className="gap-1.5">
        <CardTitle className="text-2xl font-semibold tracking-tight">{t('resetTitle')}</CardTitle>
        <CardDescription className="text-[15px]">{t('resetSubtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <ResetPasswordForm token={token ?? ''} />
        <p className="text-center text-sm text-muted-foreground">
          <Link
            href="/login"
            className="cursor-pointer font-medium text-foreground underline underline-offset-4 transition-colors duration-100 hover:text-primary"
          >
            {t('signIn')}
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}
