import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { LoginForm } from './login-form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('auth')
  return { title: t('signInTitle') }
}

export default async function LoginPage() {
  const t = await getTranslations('auth')

  return (
    <Card className="rounded-xl p-2 sm:p-3">
      <CardHeader className="gap-1.5">
        <CardTitle className="text-2xl font-semibold tracking-tight">
          {t('signInTitle')}
        </CardTitle>
        <CardDescription className="text-[15px]">{t('signInSubtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <LoginForm />
        <p className="text-center text-sm text-muted-foreground">
          {t('noAccount')}{' '}
          <Link
            href="/register"
            className="cursor-pointer font-medium text-foreground underline underline-offset-4 transition-colors duration-100 hover:text-primary"
          >
            {t('signUp')}
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}
