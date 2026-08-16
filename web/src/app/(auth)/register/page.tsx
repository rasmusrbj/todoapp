import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { RegisterForm } from './register-form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('auth')
  return { title: t('signUpTitle') }
}

export default async function RegisterPage() {
  const t = await getTranslations('auth')

  return (
    <Card className="rounded-xl p-2 sm:p-3">
      <CardHeader className="gap-1.5">
        <CardTitle className="text-2xl font-semibold tracking-tight">
          {t('signUpTitle')}
        </CardTitle>
        <CardDescription className="text-[15px]">{t('signUpSubtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <RegisterForm />
        <p className="text-center text-sm text-muted-foreground">
          {t('haveAccount')}{' '}
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
