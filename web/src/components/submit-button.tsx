'use client'

import { faSpinnerThird } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useFormStatus } from 'react-dom'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type SubmitButtonProps = React.ComponentProps<typeof Button> & {
  /** Shown while the action is in flight. Defaults to the idle label. */
  pendingLabel?: string
}

/**
 * A submit button that reports the enclosing form's pending state.
 *
 * `useFormStatus` reads it from the form rather than from local state, so a Server
 * Action needs no `useState` to disable its own button — and the button cannot get
 * out of step with the request.
 */
export function SubmitButton({
  children,
  pendingLabel,
  className,
  disabled,
  ...props
}: SubmitButtonProps) {
  const { pending } = useFormStatus()

  return (
    <Button
      type="submit"
      disabled={pending || disabled}
      aria-busy={pending}
      className={cn('press', className)}
      {...props}
    >
      {pending && <FontAwesomeIcon icon={faSpinnerThird} className="h-4 w-4 animate-spin" />}
      {pending && pendingLabel ? pendingLabel : children}
    </Button>
  )
}
