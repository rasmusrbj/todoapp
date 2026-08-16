/**
 * Turning a `ConnectError` into something a person can read.
 *
 * The server sends an English developer message plus a machine-readable
 * `todo.v1.ErrorReason`. The reason is the translation key, so the same failure
 * reads natively in Danish and in English, and adding a locale needs no server
 * change. The developer message is never shown.
 */

import { Code, ConnectError } from '@connectrpc/connect'

import { ErrorDetailSchema, ErrorReason, ErrorReasonSchema } from '@/gen/todo/v1/errors_pb'
import { enumToJson } from '@bufbuild/protobuf'

/** A failure, ready for a form or a toast. */
export type ActionFailure = {
  ok: false
  /** Key into the `errors` message namespace. */
  reasonKey: string
  /** Values for the message's placeholders, e.g. `{max_length: '200'}`. */
  values: Record<string, string>
  /** Request field at fault, so a form can highlight the right input. */
  field?: string
}

/** A successful action, optionally carrying a payload. */
export type ActionSuccess<T = undefined> = { ok: true; data: T }

/** What every Server Action in this app returns. */
export type ActionResult<T = undefined> = ActionSuccess<T> | ActionFailure

/** Wraps a value as a success result. */
export function succeed<T>(data: T): ActionSuccess<T> {
  return { ok: true, data }
}

/** Builds a failure result from a reason key, bypassing the wire format. */
export function fail(reasonKey: string, field?: string): ActionFailure {
  return { ok: false, reasonKey, values: {}, field }
}

/**
 * Converts any thrown value into an {@link ActionFailure}.
 *
 * Called at the edge of every Server Action, because an uncaught throw in an action
 * becomes an opaque "server error" in the browser — losing exactly the detail the
 * form needs.
 */
export function toFailure(error: unknown): ActionFailure {
  if (!(error instanceof ConnectError)) {
    // A network-level failure: the API is down or unreachable.
    const message = error instanceof Error ? error.message : String(error)
    console.error('[api] non-Connect failure:', message)
    return { ok: false, reasonKey: 'network', values: {} }
  }

  const detail = error.findDetails(ErrorDetailSchema)[0]
  if (!detail) {
    // A Connect error with no detail is one our own handlers did not raise —
    // a timeout, a cancellation, or a proxy in the way.
    return {
      ok: false,
      reasonKey: error.code === Code.Unauthenticated ? 'ERROR_REASON_NOT_AUTHENTICATED' : 'unknown',
      values: {},
    }
  }

  return {
    ok: false,
    reasonKey: enumToJson(ErrorReasonSchema, detail.reason) as string,
    values: detail.metadata ?? {},
    field: detail.field || undefined,
  }
}

/** Whether a failure means "sign in again", which the layout redirects on. */
export function isAuthFailure(failure: ActionFailure): boolean {
  return (
    failure.reasonKey === 'ERROR_REASON_NOT_AUTHENTICATED' ||
    failure.reasonKey === 'ERROR_REASON_SESSION_EXPIRED'
  )
}

/** Whether a thrown value is an unauthenticated `ConnectError`. */
export function isUnauthenticated(error: unknown): boolean {
  if (!(error instanceof ConnectError)) return false
  if (error.code === Code.Unauthenticated) return true
  const detail = error.findDetails(ErrorDetailSchema)[0]
  return (
    detail?.reason === ErrorReason.NOT_AUTHENTICATED ||
    detail?.reason === ErrorReason.SESSION_EXPIRED
  )
}
