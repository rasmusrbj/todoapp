import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { ForgotPasswordForm } from './forgot-password-form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('auth')
  return { title: t('forgotTitle') }
}

export default async function ForgotPasswordPage() {
  const t = await getTranslations('auth')

  return (
    <Card className="rounded-xl p-2 sm:p-3">
      <CardHeader className="gap-1.5">
        <CardTitle className="text-2xl font-semibold tracking-tight">
          {t('forgotTitle')}
        </CardTitle>
        <CardDescription className="text-[15px]">{t('forgotSubtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <ForgotPasswordForm />
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
