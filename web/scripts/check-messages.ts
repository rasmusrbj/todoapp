/**
 * Verifies the message catalogues against the proto contract.
 *
 * Three things go wrong quietly and this catches all of them:
 *
 * 1. A locale gains a key the other one lacks, so one language silently falls back.
 * 2. A proto enum gains a value with no display name, so the UI renders `⚠️ key`.
 * 3. A catalogue keeps a display name for a value the proto no longer has.
 *
 * Run with `pnpm check:messages`, or as part of `make lint`.
 *
 * Executed with tsx rather than plain node: the generated code uses TypeScript
 * `enum`, which Node's strip-only mode rejects.
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { enumToJson } from '@bufbuild/protobuf'

import * as enums from '../src/gen/todo/v1/enums_pb'
import { ErrorReasonSchema } from '../src/gen/todo/v1/errors_pb'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const locales = ['da', 'en'] as const

/** Every enum namespace in `messages.enums`, paired with its generated schema. */
const ENUM_NAMESPACES = {
  taskStatus: enums.TaskStatusSchema,
  taskPriority: enums.TaskPrioritySchema,
  listVisibility: enums.ListVisibilitySchema,
  listColor: enums.ListColorSchema,
  memberRole: enums.MemberRoleSchema,
  userRole: enums.UserRoleSchema,
  userStatus: enums.UserStatusSchema,
  locale: enums.LocaleSchema,
  theme: enums.ThemePreferenceSchema,
  recurrence: enums.RecurrenceFrequencySchema,
  sessionClient: enums.SessionClientSchema,
  activityAction: enums.ActivityActionSchema,
  taskSortField: enums.TaskSortFieldSchema,
  listSortField: enums.ListSortFieldSchema,
}

// Namespaces whose `_UNSPECIFIED` sentinel never reaches a screen, so it needs no
// translation: a sort field or a hint is always chosen explicitly.
const SENTINEL_NOT_NEEDED = new Set([
  'taskSortField',
  'listSortField',
  'listVisibilityHint',
  'memberRoleHint',
])

/** The proto name of an enum value, e.g. `TASK_STATUS_DONE`. */
function valueName(schema: Parameters<typeof enumToJson>[0], number: number): string {
  return enumToJson(schema, number) as string
}

function flatten(value: Record<string, unknown>, prefix = ''): Set<string> {
  const keys = new Set<string>()
  for (const [key, child] of Object.entries(value)) {
    const path = `${prefix}${key}`
    if (child !== null && typeof child === 'object') {
      for (const nested of flatten(child as Record<string, unknown>, `${path}.`)) keys.add(nested)
    } else {
      keys.add(path)
    }
  }
  return keys
}

/** The shape this script cares about; the rest of a catalogue is free-form. */
type Catalogue = {
  enums?: Record<string, Record<string, string>>
  errors?: Record<string, string>
}

const catalogues = Object.fromEntries(
  locales.map((locale) => [
    locale,
    JSON.parse(readFileSync(join(root, 'messages', `${locale}.json`), 'utf8')) as Catalogue &
      Record<string, unknown>,
  ]),
) as Record<(typeof locales)[number], Catalogue & Record<string, unknown>>

const problems: string[] = []

// 1. The two locales must carry the same keys.
const [first, ...rest] = locales
const reference = flatten(catalogues[first])
for (const locale of rest) {
  const other = flatten(catalogues[locale])
  for (const key of reference) {
    if (!other.has(key)) problems.push(`${locale}: missing key "${key}"`)
  }
  for (const key of other) {
    if (!reference.has(key)) problems.push(`${first}: missing key "${key}"`)
  }
}

// 2 and 3. Every enum value needs a name, and every name needs a value.
for (const [namespace, schema] of Object.entries(ENUM_NAMESPACES)) {
  const expected = new Set(
    schema.values
      .filter((value) => value.number !== 0 || !SENTINEL_NOT_NEEDED.has(namespace))
      .map((value) => valueName(schema, value.number)),
  )

  for (const locale of locales) {
    const provided = catalogues[locale].enums?.[namespace]
    if (!provided) {
      problems.push(`${locale}: missing enum namespace "enums.${namespace}"`)
      continue
    }
    for (const name of expected) {
      if (!(name in provided)) {
        problems.push(`${locale}: enums.${namespace} has no display name for ${name}`)
      }
    }
    for (const name of Object.keys(provided)) {
      if (!expected.has(name)) {
        problems.push(`${locale}: enums.${namespace}.${name} is not a value of this enum`)
      }
    }
  }
}

// Every ErrorReason needs a sentence, or a failure surfaces as a raw key.
for (const locale of locales) {
  const provided = catalogues[locale].errors ?? {}
  for (const value of ErrorReasonSchema.values) {
    const name = valueName(ErrorReasonSchema, value.number)
    if (!(name in provided)) {
      problems.push(`${locale}: errors has no message for ${name}`)
    }
  }
}

if (problems.length > 0) {
  console.error(`✗ ${problems.length} message problem(s):\n`)
  for (const problem of problems) console.error(`  ${problem}`)
  process.exit(1)
}

console.log(
  `✓ ${locales.length} locales, ${reference.size} keys, ` +
    `${Object.keys(ENUM_NAMESPACES).length} enums, all in parity`,
)
