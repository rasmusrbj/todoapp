"use client"

import * as React from "react"
import { format, parse, setMonth, setYear } from "date-fns"
import { da } from "date-fns/locale/da"
import { de } from "date-fns/locale/de"
import { es } from "date-fns/locale/es"
import { nl } from "date-fns/locale/nl"
import { enUS } from "date-fns/locale/en-US"
import type { Locale } from "date-fns"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import {
  faCalendar,
  faChevronLeft,
  faChevronRight,
} from "@fortawesome/pro-solid-svg-icons"

import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import { Calendar } from "./ui/calendar"
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverTrigger,
} from "./ui/popover"

// ---------------------------------------------------------------------------
// Locale resolution
// ---------------------------------------------------------------------------

const DATE_FNS_LOCALES: Record<string, Locale> = {
  da,
  de,
  es,
  nl,
  en: enUS,
  "en-US": enUS,
}

const TIME_LABELS: Record<string, string> = {
  da: "Tid",
  de: "Zeit",
  fr: "Heure",
  es: "Hora",
  nl: "Tijd",
  sv: "Tid",
  nb: "Tid",
  nn: "Tid",
}

function getLocaleCookie(): string | undefined {
  if (typeof document === "undefined") return undefined
  return document.cookie
    .split(";")
    .find((c) => c.trim().startsWith("locale="))
    ?.split("=")[1]
    ?.trim()
}

function resolveLocale(locale?: string): string {
  return locale ?? getLocaleCookie() ?? "en"
}

function getDateFnsLocale(locale: string): Locale {
  return DATE_FNS_LOCALES[locale] ?? enUS
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function dateFromString(value: string): Date | undefined {
  if (!value) return undefined
  const d = parse(value, "yyyy-MM-dd", new Date())
  return isNaN(d.getTime()) ? undefined : d
}

function dateToString(date: Date): string {
  return format(date, "yyyy-MM-dd")
}

// ---------------------------------------------------------------------------
// DatePicker – replaces <Input type="date" />
// ---------------------------------------------------------------------------

interface DatePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  min?: string
  max?: string
  id?: string
  className?: string
  locale?: string
}

function DatePicker({
  value,
  onChange,
  placeholder = "Pick a date",
  disabled,
  min,
  max,
  id,
  className,
  locale: localeProp,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false)
  const selected = dateFromString(value)
  const minDate = min ? dateFromString(min) : undefined
  const maxDate = max ? dateFromString(max) : undefined
  const effectiveLocale = resolveLocale(localeProp)
  const dateFnsLocale = getDateFnsLocale(effectiveLocale)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="outline"
          disabled={disabled}
          className={cn(
            "w-full justify-start text-left font-normal",
            !value && "text-muted-foreground",
            className,
          )}
        >
          <FontAwesomeIcon icon={faCalendar} className="mr-2 size-3.5" />
          {selected ? format(selected, "PPP", { locale: dateFnsLocale }) : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          locale={dateFnsLocale}
          selected={selected}
          onSelect={(day) => {
            if (day) {
              onChange(dateToString(day))
              setOpen(false)
            }
          }}
          {...(selected ? { defaultMonth: selected } : {})}
          disabled={(date) => {
            if (minDate && date < minDate) return true
            if (maxDate && date > maxDate) return true
            return false
          }}
        />
      </PopoverContent>
    </Popover>
  )
}

// ---------------------------------------------------------------------------
// DateTimePicker
// ---------------------------------------------------------------------------

interface DateTimePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  min?: string
  max?: string
  id?: string
  className?: string
  locale?: string
  timeLabel?: string
}

type PickerMode = "full" | "month" | "year" | "time"

function datetimeFromString(
  value: string,
): { date: Date; hour: number; minute: number } | undefined {
  if (!value) return undefined
  const [datePart, timePart] = value.split("T")
  if (!datePart) return undefined
  const d = parse(datePart, "yyyy-MM-dd", new Date())
  if (isNaN(d.getTime())) return undefined
  const [h, m] = (timePart ?? "00:00").split(":").map(Number)
  return { date: d, hour: h ?? 0, minute: m ?? 0 }
}

function detectIs12h(locale?: string): boolean {
  try {
    const parts = new Intl.DateTimeFormat(locale, {
      hour: "numeric",
    }).formatToParts(new Date(2000, 0, 1, 13))
    const localePrefers12h = parts.some((p) => p.type === "dayPeriod")
    if (!localePrefers12h) return false

    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone ?? ""
    const is12hRegion =
      tz.startsWith("America/") ||
      tz.startsWith("Australia/") ||
      tz.startsWith("Pacific/") ||
      tz === "Europe/London" ||
      tz === "Europe/Dublin" ||
      tz === "Asia/Kolkata" ||
      tz === "Asia/Manila"
    return is12hRegion
  } catch {
    return false
  }
}

function getTimezoneLabel(): string {
  const offset = new Date().getTimezoneOffset()
  const sign = offset <= 0 ? "+" : "-"
  const h = Math.floor(Math.abs(offset) / 60)
  const m = Math.abs(offset) % 60
  return m
    ? `GMT${sign}${h}:${String(m).padStart(2, "0")}`
    : `GMT${sign}${h}`
}

function formatTimeValue(
  hour: number,
  minute: number,
  is12h: boolean,
): string {
  if (!is12h) {
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`
  }
  const period = hour >= 12 ? "PM" : "AM"
  const h = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
  return `${h}:${String(minute).padStart(2, "0")} ${period}`
}

function formatTimeSlotLabel(hour: number, is12h: boolean): string {
  if (!is12h) return `${String(hour).padStart(2, "0")}:00`
  const period = hour >= 12 ? "PM" : "AM"
  const h = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
  return `${h}:00 ${period}`
}

function buildValue(date: Date, hours: number, minutes: number): string {
  return `${dateToString(date)}T${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`
}

function extractTime(
  text: string,
): { hours: number; minutes: number } | null {
  let m: RegExpMatchArray | null

  m = text.match(/^(\d{1,2})[.:](\d{2})$/)
  if (m) {
    const h = parseInt(m[1]!)
    const min = parseInt(m[2]!)
    if (h >= 0 && h <= 23 && min >= 0 && min <= 59)
      return { hours: h, minutes: min }
  }

  m = text.match(/^(\d{1,2})\s+(\d{2})$/)
  if (m) {
    const h = parseInt(m[1]!)
    const min = parseInt(m[2]!)
    if (h >= 0 && h <= 23 && min >= 0 && min <= 59)
      return { hours: h, minutes: min }
  }

  m = text.match(/^(\d{2})(\d{2})$/)
  if (m) {
    const h = parseInt(m[1]!)
    const min = parseInt(m[2]!)
    if (h >= 0 && h <= 23 && min >= 0 && min <= 59)
      return { hours: h, minutes: min }
  }

  m = text.match(/^(\d)(\d{2})$/)
  if (m) {
    const h = parseInt(m[1]!)
    const min = parseInt(m[2]!)
    if (h >= 0 && h <= 9 && min >= 0 && min <= 59)
      return { hours: h, minutes: min }
  }

  m = text.match(/^(\d{1,2})[.:](\d{2})\s*(AM|PM)$/i)
  if (m) {
    let h = parseInt(m[1]!)
    const min = parseInt(m[2]!)
    const period = m[3]!.toUpperCase()
    if (period === "PM" && h < 12) h += 12
    if (period === "AM" && h === 12) h = 0
    if (h >= 0 && h <= 23 && min >= 0 && min <= 59)
      return { hours: h, minutes: min }
  }

  return null
}

function parseUserInput(
  text: string,
  currentValue: string,
): string | null {
  const cleaned = text
    .replace(/\s+(?:GMT|UTC)[+-]?\d*(?::\d+)?\s*$/i, "")
    .trim()
  if (!cleaned) return null

  const timeOnly = extractTime(cleaned)
  if (timeOnly) {
    const current = datetimeFromString(currentValue)
    const datePart = current ? current.date : new Date()
    return buildValue(datePart, timeOnly.hours, timeOnly.minutes)
  }

  const timeTrailMatch = cleaned.match(
    /(\d{1,2})[.:]\s*(\d{2})\s*(AM|PM)?\s*$/i,
  )
  if (timeTrailMatch) {
    const dateStr = cleaned.slice(0, timeTrailMatch.index).trim()
    let hours = parseInt(timeTrailMatch[1]!)
    const minutes = parseInt(timeTrailMatch[2]!)
    const period = timeTrailMatch[3]?.toUpperCase()

    if (period === "PM" && hours < 12) hours += 12
    if (period === "AM" && hours === 12) hours = 0
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59)
      return null

    let date: Date | undefined
    const formats = [
      "MMMM d, yyyy",
      "MMMM d yyyy",
      "MMM d, yyyy",
      "MMM d yyyy",
      "d MMMM yyyy",
      "d MMM yyyy",
      "yyyy-MM-dd",
      "dd/MM/yyyy",
      "d/M/yyyy",
      "d/M",
    ]
    for (const fmt of formats) {
      try {
        const d = parse(dateStr, fmt, new Date())
        if (!isNaN(d.getTime()) && d.getFullYear() >= 1900) {
          date = d
          break
        }
      } catch {
        /* skip */
      }
    }

    if (!date) {
      const d = new Date(dateStr)
      if (!isNaN(d.getTime()) && d.getFullYear() >= 1900) date = d
    }

    if (!date) return null
    return buildValue(date, hours, minutes)
  }

  return null
}

// ---------------------------------------------------------------------------
// MonthPicker sub-component
// ---------------------------------------------------------------------------

function MonthPicker({
  selectedMonth,
  locale,
  onSelect,
}: {
  selectedMonth: number
  locale: string
  onSelect: (month: number) => void
}) {
  const months = React.useMemo(() => {
    const fmt = new Intl.DateTimeFormat(locale, { month: "long" })
    return Array.from({ length: 12 }, (_, i) => {
      const name = fmt.format(new Date(2000, i, 1))
      return name.charAt(0).toUpperCase() + name.slice(1)
    })
  }, [locale])

  return (
    <div className="grid grid-cols-3 gap-1 p-3">
      {months.map((name, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onSelect(i)}
          className={cn(
            "cursor-pointer rounded-md px-2 py-2 text-sm transition-colors hover:bg-accent",
            i === selectedMonth &&
              "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
        >
          {name}
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// YearPicker sub-component
// ---------------------------------------------------------------------------

function YearPicker({
  selectedYear,
  onSelect,
}: {
  selectedYear: number
  onSelect: (year: number) => void
}) {
  const [pageStart, setPageStart] = React.useState(
    () => selectedYear - ((selectedYear % 12) - (selectedYear >= 0 ? 0 : 12)),
  )

  React.useEffect(() => {
    setPageStart(
      selectedYear - ((selectedYear % 12) - (selectedYear >= 0 ? 0 : 12)),
    )
  }, [selectedYear])

  const years = Array.from({ length: 12 }, (_, i) => pageStart + i)

  return (
    <div className="p-3">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setPageStart((s) => s - 12)}
          className="inline-flex size-7 cursor-pointer items-center justify-center rounded-md hover:bg-accent"
        >
          <FontAwesomeIcon icon={faChevronLeft} className="size-3" />
        </button>
        <span className="text-sm font-medium">
          {years[0]} – {years[11]}
        </span>
        <button
          type="button"
          onClick={() => setPageStart((s) => s + 12)}
          className="inline-flex size-7 cursor-pointer items-center justify-center rounded-md hover:bg-accent"
        >
          <FontAwesomeIcon icon={faChevronRight} className="size-3" />
        </button>
      </div>
      <div className="grid grid-cols-3 gap-1">
        {years.map((y) => (
          <button
            key={y}
            type="button"
            onClick={() => onSelect(y)}
            className={cn(
              "cursor-pointer rounded-md px-2 py-2 text-sm transition-colors hover:bg-accent",
              y === selectedYear &&
                "bg-primary text-primary-foreground hover:bg-primary/90",
            )}
          >
            {y}
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// TimeColumn sub-component
// ---------------------------------------------------------------------------

function TimeColumn({
  selectedHour,
  selectedMinute,
  is12h,
  timeLabel,
  listRef,
  onSelect,
  onSelectExact,
}: {
  selectedHour: number
  selectedMinute: number
  is12h: boolean
  timeLabel: string
  listRef: React.RefObject<HTMLDivElement | null>
  onSelect: (hour: number) => void
  onSelectExact: (hour: number, minute: number) => void
}) {
  const [timeInput, setTimeInput] = React.useState("")
  const slots = React.useMemo(
    () =>
      Array.from({ length: 24 }, (_, h) => ({
        hour: h,
        label: formatTimeSlotLabel(h, is12h),
      })),
    [is12h],
  )

  function handleTimeInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      const parsed = extractTime(timeInput.trim())
      if (parsed) {
        onSelectExact(parsed.hours, parsed.minutes)
        setTimeInput("")
      }
    }
  }

  return (
    <div className="w-[120px] shrink-0 border-l">
      <div className="px-3 py-2 text-center text-sm font-medium">
        {timeLabel}
      </div>
      <div className="px-2 pb-1.5">
        <input
          type="text"
          value={timeInput}
          onChange={(e) => setTimeInput(e.target.value)}
          onKeyDown={handleTimeInputKeyDown}
          placeholder={formatTimeValue(selectedHour, selectedMinute, is12h)}
          className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-center text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
      </div>
      <div ref={listRef} className="h-[248px] overflow-y-auto">
        {slots.map((slot) => (
          <button
            key={slot.hour}
            type="button"
            data-selected={slot.hour === selectedHour}
            onClick={() => onSelect(slot.hour)}
            className={cn(
              "w-full cursor-pointer px-4 py-1.5 text-center text-sm transition-colors hover:bg-accent",
              slot.hour === selectedHour &&
                "bg-primary text-primary-foreground hover:bg-primary/90",
            )}
          >
            {slot.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SegmentDisplay – renders clickable date/time segments
// ---------------------------------------------------------------------------

type SegmentType = "month" | "day" | "year" | "time"

function SegmentDisplay({
  date,
  hour,
  minute,
  is12h,
  tz,
  locale,
  activeSegment,
  onSegmentClick,
}: {
  date: Date
  hour: number
  minute: number
  is12h: boolean
  tz: string
  locale: string
  activeSegment: SegmentType | null
  onSegmentClick: (type: SegmentType) => void
}) {
  const dateParts = React.useMemo(() => {
    try {
      return new Intl.DateTimeFormat(locale, {
        year: "numeric",
        month: "long",
        day: "numeric",
      }).formatToParts(date)
    } catch {
      return new Intl.DateTimeFormat("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      }).formatToParts(date)
    }
  }, [date, locale])

  const timeStr = formatTimeValue(hour, minute, is12h)

  const segmentClass = (type: SegmentType) =>
    cn(
      "cursor-pointer rounded-sm px-0.5 transition-colors hover:bg-accent/60",
      activeSegment === type && "bg-accent",
    )

  return (
    <span className="flex items-center whitespace-nowrap">
      {dateParts.map((part, i) => {
        const segType =
          part.type === "month"
            ? "month"
            : part.type === "day"
              ? "day"
              : part.type === "year"
                ? "year"
                : null
        if (segType) {
          return (
            <span
              key={i}
              data-segment={segType}
              className={segmentClass(segType as SegmentType)}
              onMouseDown={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onSegmentClick(segType as SegmentType)
              }}
            >
              {part.value}
            </span>
          )
        }
        return <span key={i}>{part.value}</span>
      })}
      <span className="mx-1" />
      <span
        data-segment="time"
        className={segmentClass("time")}
        onMouseDown={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onSegmentClick("time")
        }}
      >
        {timeStr}
      </span>
      <span className="mx-1 text-muted-foreground">{tz}</span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// DateTimePicker main component
// ---------------------------------------------------------------------------

function DateTimePicker({
  value,
  onChange,
  placeholder = "Pick date & time",
  disabled,
  id,
  className,
  locale: localeProp,
  timeLabel,
}: DateTimePickerProps) {
  const [open, setOpen] = React.useState(false)
  const [pickerMode, setPickerMode] = React.useState<PickerMode>("full")
  const [editText, setEditText] = React.useState<string | null>(null)
  const blurTimeout = React.useRef<ReturnType<typeof setTimeout>>(undefined)
  const timeListRef = React.useRef<HTMLDivElement>(null)
  const inputRef = React.useRef<HTMLInputElement>(null)
  const containerRef = React.useRef<HTMLDivElement>(null)

  const [is12h, setIs12h] = React.useState(false)
  const [tz, setTz] = React.useState("GMT+0")
  const [effectiveLocale, setEffectiveLocale] = React.useState("en")
  React.useEffect(() => {
    const loc = resolveLocale(localeProp)
    setIs12h(detectIs12h(loc))
    setTz(getTimezoneLabel())
    setEffectiveLocale(loc)
  }, [localeProp])

  const effectiveTimeLabel =
    timeLabel ?? TIME_LABELS[effectiveLocale] ?? "Time"
  const dateFnsLocale = getDateFnsLocale(effectiveLocale)

  const parsed = datetimeFromString(value)
  const hour = parsed?.hour ?? 0
  const minute = parsed?.minute ?? 0

  function commitEdit() {
    if (editText === null) return
    const result = parseUserInput(editText, value)
    if (result) onChange(result)
    setEditText(null)
  }

  function handleDateSelect(day: Date | undefined) {
    if (!day) return
    clearTimeout(blurTimeout.current)
    onChange(buildValue(day, hour, minute))
    setEditText(null)
  }

  function handleTimeSelect(h: number) {
    clearTimeout(blurTimeout.current)
    const datePart = parsed?.date ?? new Date()
    onChange(buildValue(datePart, h, minute))
    setEditText(null)
    if (pickerMode === "time") setOpen(false)
  }

  function handleTimeSelectExact(h: number, m: number) {
    clearTimeout(blurTimeout.current)
    const datePart = parsed?.date ?? new Date()
    onChange(buildValue(datePart, h, m))
    setEditText(null)
    setOpen(false)
  }

  function handleMonthSelect(month: number) {
    if (!parsed) return
    const newDate = setMonth(parsed.date, month)
    onChange(buildValue(newDate, hour, minute))
    setOpen(false)
  }

  function handleYearSelect(year: number) {
    if (!parsed) return
    const newDate = setYear(parsed.date, year)
    onChange(buildValue(newDate, hour, minute))
    setOpen(false)
  }

  function handleOpenChange(nextOpen: boolean) {
    clearTimeout(blurTimeout.current)
    if (!nextOpen) {
      commitEdit()
      setPickerMode("full")
    }
    setOpen(nextOpen)
  }

  function handleSegmentClick(type: SegmentType) {
    if (disabled) return
    clearTimeout(blurTimeout.current)
    if (type === "day") {
      setPickerMode("full")
    } else {
      setPickerMode(type)
    }
    setOpen(true)
  }

  function handleContainerMouseDown(e: React.MouseEvent) {
    if (disabled) return
    const target = e.target as HTMLElement
    if (target.dataset.segment) return
    if (editText !== null) return
    e.preventDefault()
    setPickerMode("full")
    setOpen(true)
  }

  function handleContainerKeyDown(e: React.KeyboardEvent) {
    if (disabled) return
    if (editText !== null) return

    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      setPickerMode("full")
      setOpen(true)
      return
    }

    if (e.key === "Escape") {
      setOpen(false)
      return
    }

    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      setEditText(e.key)
      setOpen(false)
      requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.focus()
          const len = inputRef.current.value.length
          inputRef.current.setSelectionRange(len, len)
        }
      })
    }
  }

  function handleInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      commitEdit()
      setOpen(false)
      requestAnimationFrame(() => containerRef.current?.focus())
    }
    if (e.key === "Escape") {
      setEditText(null)
      setOpen(false)
      requestAnimationFrame(() => containerRef.current?.focus())
    }
  }

  function handleBlur(e: React.FocusEvent) {
    const related = e.relatedTarget as HTMLElement | null
    if (containerRef.current?.contains(related)) return
    blurTimeout.current = setTimeout(() => {
      commitEdit()
    }, 150)
  }

  React.useEffect(() => {
    if (!open || pickerMode !== "full") return
    requestAnimationFrame(() => {
      const el = timeListRef.current?.querySelector(
        '[data-selected="true"]',
      )
      el?.scrollIntoView({ block: "center" })
    })
  }, [open, pickerMode])

  React.useEffect(() => {
    if (!open || pickerMode !== "time") return
    requestAnimationFrame(() => {
      const el = timeListRef.current?.querySelector(
        '[data-selected="true"]',
      )
      el?.scrollIntoView({ block: "center" })
    })
  }, [open, pickerMode])

  React.useEffect(() => {
    return () => clearTimeout(blurTimeout.current)
  }, [])

  const activeSegment: SegmentType | null =
    open && pickerMode !== "full" ? pickerMode : null

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverAnchor asChild>
        <div
          ref={containerRef}
          id={id}
          role="combobox"
          tabIndex={editText !== null ? -1 : 0}
          aria-expanded={open}
          aria-haspopup="dialog"
          onMouseDown={handleContainerMouseDown}
          onKeyDown={handleContainerKeyDown}
          onBlur={handleBlur}
          className={cn(
            "flex h-9 w-full min-w-0 items-center rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground md:text-sm dark:bg-input/30",
            "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
            disabled &&
              "pointer-events-none cursor-not-allowed opacity-50",
            !value && !editText && "text-muted-foreground",
            className,
          )}
        >
          {editText !== null ? (
            <input
              ref={inputRef}
              type="text"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={handleInputKeyDown}
              onBlur={handleBlur}
              className="h-full w-full min-w-0 bg-transparent text-base outline-none selection:bg-primary selection:text-primary-foreground md:text-sm"
            />
          ) : parsed ? (
            <SegmentDisplay
              date={parsed.date}
              hour={hour}
              minute={minute}
              is12h={is12h}
              tz={tz}
              locale={effectiveLocale}
              activeSegment={activeSegment}
              onSegmentClick={handleSegmentClick}
            />
          ) : (
            <span>{placeholder}</span>
          )}
        </div>
      </PopoverAnchor>
      <PopoverContent
        className="w-auto p-0"
        align="start"
        collisionPadding={16}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {pickerMode === "full" && (
          <div className="flex">
            <Calendar
              mode="single"
              locale={dateFnsLocale}
              selected={parsed?.date}
              onSelect={handleDateSelect}
              {...(parsed?.date ? { defaultMonth: parsed.date } : {})}
            />
            <TimeColumn
              selectedHour={hour}
              selectedMinute={minute}
              is12h={is12h}
              timeLabel={effectiveTimeLabel}
              listRef={timeListRef}
              onSelect={handleTimeSelect}
              onSelectExact={handleTimeSelectExact}
            />
          </div>
        )}
        {pickerMode === "month" && parsed && (
          <MonthPicker
            selectedMonth={parsed.date.getMonth()}
            locale={effectiveLocale}
            onSelect={handleMonthSelect}
          />
        )}
        {pickerMode === "year" && parsed && (
          <YearPicker
            selectedYear={parsed.date.getFullYear()}
            onSelect={handleYearSelect}
          />
        )}
        {pickerMode === "time" && (
          <TimeColumn
            selectedHour={hour}
            selectedMinute={minute}
            is12h={is12h}
            timeLabel={effectiveTimeLabel}
            listRef={timeListRef}
            onSelect={handleTimeSelect}
            onSelectExact={handleTimeSelectExact}
          />
        )}
      </PopoverContent>
    </Popover>
  )
}

// ---------------------------------------------------------------------------
// TimePicker – replaces <input type="time" />
// ---------------------------------------------------------------------------

interface TimePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  locale?: string
}

function TimePicker({
  value,
  onChange,
  placeholder,
  disabled,
  className,
  locale: localeProp,
}: TimePickerProps) {
  const locale = resolveLocale(localeProp)
  const is12h = React.useMemo(() => detectIs12h(locale), [locale])
  const timeLabel = TIME_LABELS[locale] ?? "Time"
  const [open, setOpen] = React.useState(false)
  const [timeInput, setTimeInput] = React.useState("")
  const hourListRef = React.useRef<HTMLDivElement>(null)
  const minuteListRef = React.useRef<HTMLDivElement>(null)

  const parsed = React.useMemo(() => {
    if (!value) return { hour: -1, minute: -1 }
    const m = value.match(/^(\d{1,2}):(\d{2})$/)
    if (!m) return { hour: -1, minute: -1 }
    return { hour: parseInt(m[1]!), minute: parseInt(m[2]!) }
  }, [value])

  const displayValue = React.useMemo(() => {
    if (parsed.hour < 0) return ""
    return formatTimeValue(parsed.hour, parsed.minute, is12h)
  }, [parsed, is12h])

  function emitChange(hour: number, minute: number) {
    onChange(`${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`)
  }

  function handleTimeInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      const result = extractTime(timeInput.trim())
      if (result) {
        emitChange(result.hours, result.minutes)
        setTimeInput("")
        setOpen(false)
      }
    }
  }

  // Scroll selected items into view when popover opens
  React.useEffect(() => {
    if (!open || parsed.hour < 0) return
    const timeout = setTimeout(() => {
      const hourEl = hourListRef.current?.querySelector(
        `[data-selected="true"]`,
      )
      hourEl?.scrollIntoView({ block: "center" })
      const minuteEl = minuteListRef.current?.querySelector(
        `[data-selected="true"]`,
      )
      minuteEl?.scrollIntoView({ block: "center" })
    }, 50)
    return () => clearTimeout(timeout)
  }, [open, parsed.hour])

  const hours = React.useMemo(
    () =>
      Array.from({ length: 24 }, (_, h) => ({
        value: h,
        label: formatTimeSlotLabel(h, is12h),
      })),
    [is12h],
  )

  const minutes = React.useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => {
        const m = i * 5
        return { value: m, label: String(m).padStart(2, "0") }
      }),
    [],
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          className={cn(
            "w-full justify-start text-left font-normal",
            !displayValue && "text-muted-foreground",
            className,
          )}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mr-2 size-3.5"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          {displayValue || placeholder || timeLabel}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        <div className="px-3 pt-2.5 pb-1.5">
          <input
            type="text"
            value={timeInput}
            onChange={(e) => setTimeInput(e.target.value)}
            onKeyDown={handleTimeInputKeyDown}
            placeholder={
              displayValue || (is12h ? "e.g. 2:30 PM" : "e.g. 14:30")
            }
            className="w-full rounded-md border border-input bg-transparent px-2.5 py-1.5 text-center text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
        <div className="flex">
          {/* Hours column */}
          <div className="flex-1 border-r">
            <div className="px-2 py-1.5 text-center text-xs font-medium text-muted-foreground">
              {locale === "da" ? "Timer" : "Hours"}
            </div>
            <div ref={hourListRef} className="h-[240px] overflow-y-auto">
              {hours.map((slot) => (
                <button
                  key={slot.value}
                  type="button"
                  data-selected={slot.value === parsed.hour}
                  onClick={() => {
                    const m = parsed.minute >= 0 ? parsed.minute : 0
                    emitChange(slot.value, m)
                  }}
                  className={cn(
                    "w-full cursor-pointer px-3 py-1.5 text-center text-sm transition-colors hover:bg-accent",
                    slot.value === parsed.hour &&
                      "bg-primary text-primary-foreground hover:bg-primary/90",
                  )}
                >
                  {slot.label}
                </button>
              ))}
            </div>
          </div>
          {/* Minutes column */}
          <div className="flex-1">
            <div className="px-2 py-1.5 text-center text-xs font-medium text-muted-foreground">
              {locale === "da" ? "Min" : "Min"}
            </div>
            <div ref={minuteListRef} className="h-[240px] overflow-y-auto">
              {minutes.map((slot) => (
                <button
                  key={slot.value}
                  type="button"
                  data-selected={slot.value === parsed.minute}
                  onClick={() => {
                    const h = parsed.hour >= 0 ? parsed.hour : 0
                    emitChange(h, slot.value)
                    setOpen(false)
                  }}
                  className={cn(
                    "w-full cursor-pointer px-3 py-1.5 text-center text-sm transition-colors hover:bg-accent",
                    slot.value === parsed.minute &&
                      "bg-primary text-primary-foreground hover:bg-primary/90",
                  )}
                >
                  :{slot.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

export { DatePicker, DateTimePicker, TimePicker }
export type { DatePickerProps, DateTimePickerProps, TimePickerProps }
