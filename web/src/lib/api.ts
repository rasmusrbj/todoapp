/**
 * Server-side ConnectRPC clients.
 *
 * Every call to the API happens here, on the server, with the bearer token pulled
 * from the `HttpOnly` session cookie by an interceptor. Nothing in this module can
 * be imported into a Client Component — `server-only` makes that a build error
 * rather than a leak.
 */

import 'server-only'

import { createClient, type Interceptor } from '@connectrpc/connect'
import { createConnectTransport } from '@connectrpc/connect-web'

import { AuthService } from '@/gen/todo/v1/auth_pb'
import { ListService } from '@/gen/todo/v1/list_pb'
import { TaskService } from '@/gen/todo/v1/task_pb'
import { UserService } from '@/gen/todo/v1/user_pb'
import { getSessionToken } from '@/lib/session'

/** Where the API lives. Server-side only, so it is not a `NEXT_PUBLIC_` variable. */
const baseUrl = process.env.TODOAPP_API_URL ?? 'http://127.0.0.1:8081'

/**
 * Attaches the caller's bearer token to every outgoing request.
 *
 * Reading the cookie per call rather than per client is deliberate: a Server Action
 * that signs in and then reads data does so within one request, and the interceptor
 * must see the token that action just set.
 */
const withAuthorization: Interceptor = (next) => async (request) => {
  const token = await getSessionToken()
  if (token) {
    request.header.set('Authorization', `Bearer ${token}`)
  }
  return next(request)
}

/** Marks the request as coming from the web client, for the session list. */
const withUserAgent: Interceptor = (next) => async (request) => {
  request.header.set('X-Client', 'web')
  return next(request)
}

const transport = createConnectTransport({
  baseUrl,
  // The fetch-based transport works in the Node runtime as well as the browser, and
  // JSON keeps a failing call reproducible with curl straight from a log line.
  useBinaryFormat: false,
  interceptors: [withAuthorization, withUserAgent],
  // Reads are cached by the page, not by fetch: task lists must never be stale.
  fetch: (input, init) => fetch(input, { ...init, cache: 'no-store' }),
})

/** `todo.v1.AuthService` — registration, sign-in, sessions, passwords. */
export const authClient = createClient(AuthService, transport)

/** `todo.v1.UserService` — profiles, preferences, admin accounts. */
export const userClient = createClient(UserService, transport)

/** `todo.v1.ListService` — lists, membership, labels. */
export const listClient = createClient(ListService, transport)

/** `todo.v1.TaskService` — tasks, subtasks, comments, activity. */
export const taskClient = createClient(TaskService, transport)
