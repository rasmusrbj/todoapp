/**
 * Enum display names, design tokens, and option lists.
 *
 * Nothing here hard-codes a value name. `enumToJson` turns a numeric enum value into
 * its proto name — `TASK_STATUS_DONE` — which is exactly the key in the `enums`
 * message namespace. Adding a value to the proto therefore surfaces as a visible
 * missing-translation warning rather than as a silently blank label.
 *
 * The design tokens map enum values to Tailwind classes drawn from the Happenings
 * palette. Colour is never the only signal: a status also carries an icon, and a
 * priority also carries a word.
 */

import { enumToJson, type DescEnum } from '@bufbuild/protobuf'

import {
  ListColor,
  ListColorSchema,
  ListSortField,
  ListSortFieldSchema,
  ListVisibility,
  ListVisibilitySchema,
  Locale as ProtoLocale,
  LocaleSchema,
  MemberRole,
  MemberRoleSchema,
  RecurrenceFrequency,
  RecurrenceFrequencySchema,
  SessionClient,
  SessionClientSchema,
  TaskPriority,
  TaskPrioritySchema,
  TaskSortField,
  TaskSortFieldSchema,
  TaskStatus,
  TaskStatusSchema,
  ThemePreference,
  ThemePreferenceSchema,
  UserRole,
  UserRoleSchema,
  UserStatus,
  UserStatusSchema,
} from '@/gen/todo/v1/enums_pb'
import { ActivityAction, ActivityActionSchema } from '@/gen/todo/v1/enums_pb'

/** Maps a web locale to its proto enum value. */
export function toProtoLocale(locale: 'da' | 'en'): ProtoLocale {
  return locale === 'en' ? ProtoLocale.EN : ProtoLocale.DA
}

/** Maps a proto locale to a web locale, defaulting to Danish. */
export function fromProtoLocale(locale: ProtoLocale): 'da' | 'en' {
  return locale === ProtoLocale.EN ? 'en' : 'da'
}

/** Returns the proto value name for an enum value, e.g. `TASK_STATUS_DONE`. */
export function valueName(schema: DescEnum, value: number): string {
  return enumToJson(schema, value) as string
}

/** Every value of an enum except the `_UNSPECIFIED` sentinel, in proto order. */
export function realValues(schema: DescEnum): number[] {
  return schema.values.filter((value) => value.number !== 0).map((value) => value.number)
}

/**
 * Builds the option list for a `<Select>`: value, proto name, and its message key.
 *
 * Order comes from the proto, which is deliberate — `TaskPriority` is declared least
 * to most urgent, so a priority dropdown reads as a ramp without a sort here.
 */
export function options(
  schema: DescEnum,
  namespace: string,
): Array<{ value: number; name: string; key: string }> {
  return realValues(schema).map((value) => {
    const name = valueName(schema, value)
    return { value, name, key: `${namespace}.${name}` }
  })
}

/** The enum schemas the UI needs, paired with their message namespace. */
export const enumMeta = {
  taskStatus: { schema: TaskStatusSchema, namespace: 'taskStatus' },
  taskPriority: { schema: TaskPrioritySchema, namespace: 'taskPriority' },
  listVisibility: { schema: ListVisibilitySchema, namespace: 'listVisibility' },
  listColor: { schema: ListColorSchema, namespace: 'listColor' },
  memberRole: { schema: MemberRoleSchema, namespace: 'memberRole' },
  userRole: { schema: UserRoleSchema, namespace: 'userRole' },
  userStatus: { schema: UserStatusSchema, namespace: 'userStatus' },
  locale: { schema: LocaleSchema, namespace: 'locale' },
  theme: { schema: ThemePreferenceSchema, namespace: 'theme' },
  recurrence: { schema: RecurrenceFrequencySchema, namespace: 'recurrence' },
  sessionClient: { schema: SessionClientSchema, namespace: 'sessionClient' },
  activityAction: { schema: ActivityActionSchema, namespace: 'activityAction' },
  taskSortField: { schema: TaskSortFieldSchema, namespace: 'taskSortField' },
  listSortField: { schema: ListSortFieldSchema, namespace: 'listSortField' },
} as const

// --- Design tokens -----------------------------------------------------------

/**
 * Accent classes per list colour.
 *
 * Borders and tinted backgrounds only — the Happenings system uses a single brand
 * accent for actions, so a list's colour is decoration and must never compete with
 * a primary button.
 */
export const listColorClasses: Record<ListColor, { dot: string; tint: string; ring: string }> = {
  [ListColor.UNSPECIFIED]: {
    dot: 'bg-zinc-400 dark:bg-zinc-500',
    tint: 'bg-zinc-50 dark:bg-zinc-900',
    ring: 'border-zinc-200 dark:border-zinc-800',
  },
  [ListColor.ZINC]: {
    dot: 'bg-zinc-400 dark:bg-zinc-500',
    tint: 'bg-zinc-50 dark:bg-zinc-900',
    ring: 'border-zinc-200 dark:border-zinc-800',
  },
  [ListColor.RED]: {
    dot: 'bg-red-500',
    tint: 'bg-red-50 dark:bg-red-950/40',
    ring: 'border-red-200 dark:border-red-900/60',
  },
  [ListColor.AMBER]: {
    dot: 'bg-amber-500',
    tint: 'bg-amber-50 dark:bg-amber-950/40',
    ring: 'border-amber-200 dark:border-amber-900/60',
  },
  [ListColor.GREEN]: {
    dot: 'bg-emerald-500',
    tint: 'bg-emerald-50 dark:bg-emerald-950/40',
    ring: 'border-emerald-200 dark:border-emerald-900/60',
  },
  [ListColor.BLUE]: {
    dot: 'bg-blue-500',
    tint: 'bg-blue-50 dark:bg-blue-950/40',
    ring: 'border-blue-200 dark:border-blue-900/60',
  },
  [ListColor.VIOLET]: {
    dot: 'bg-violet-500',
    tint: 'bg-violet-50 dark:bg-violet-950/40',
    ring: 'border-violet-200 dark:border-violet-900/60',
  },
  [ListColor.PINK]: {
    dot: 'bg-pink-500',
    tint: 'bg-pink-50 dark:bg-pink-950/40',
    ring: 'border-pink-200 dark:border-pink-900/60',
  },
}

/** Badge classes per task status. Muted by design — a row is not a warning label. */
export const taskStatusClasses: Record<TaskStatus, string> = {
  [TaskStatus.UNSPECIFIED]: 'text-muted-foreground border-border',
  [TaskStatus.TODO]: 'text-muted-foreground border-border',
  [TaskStatus.IN_PROGRESS]: 'text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-900',
  [TaskStatus.BLOCKED]: 'text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900',
  [TaskStatus.DONE]:
    'text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900',
  [TaskStatus.CANCELLED]: 'text-muted-foreground border-border line-through',
}

/** Badge classes per priority. Only the top two are tinted, so they stand out. */
export const taskPriorityClasses: Record<TaskPriority, string> = {
  [TaskPriority.UNSPECIFIED]: 'text-muted-foreground border-border',
  [TaskPriority.NONE]: 'text-muted-foreground border-border',
  [TaskPriority.LOW]: 'text-muted-foreground border-border',
  [TaskPriority.MEDIUM]: 'text-zinc-700 dark:text-zinc-300 border-border',
  [TaskPriority.HIGH]: 'text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900',
  [TaskPriority.URGENT]: 'text-red-700 dark:text-red-300 border-red-200 dark:border-red-900',
}

/** Statuses that mean the task is finished. Mirrors the server's terminal set. */
export const terminalStatuses: readonly TaskStatus[] = [TaskStatus.DONE, TaskStatus.CANCELLED]

/** Whether a task in this status is still outstanding. */
export function isOpen(status: TaskStatus): boolean {
  return !terminalStatuses.includes(status)
}

/** Statuses a "show me what's left" filter should select. */
export const openStatuses: readonly TaskStatus[] = realValues(TaskStatusSchema).filter((value) =>
  isOpen(value as TaskStatus),
) as TaskStatus[]

/** Roles allowed to change a list's content. Mirrors the server's write set. */
export const writeRoles: readonly MemberRole[] = [MemberRole.OWNER, MemberRole.EDITOR]

/** Whether this role may create and edit tasks. */
export function canWrite(role: MemberRole): boolean {
  return writeRoles.includes(role)
}

/** Whether this role may comment. */
export function canComment(role: MemberRole): boolean {
  return canWrite(role) || role === MemberRole.COMMENTER
}

/** Whether this role owns the list, and so may share or delete it. */
export function isOwner(role: MemberRole): boolean {
  return role === MemberRole.OWNER
}

export {
  ActivityAction,
  ListColor,
  ListSortField,
  ListVisibility,
  MemberRole,
  ProtoLocale,
  RecurrenceFrequency,
  SessionClient,
  TaskPriority,
  TaskSortField,
  TaskStatus,
  ThemePreference,
  UserRole,
  UserStatus,
}
