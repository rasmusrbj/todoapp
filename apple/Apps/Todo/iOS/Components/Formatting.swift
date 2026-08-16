import Foundation
import SwiftProtobuf
import SwiftUI

/// Dates and durations, formatted the way each surface needs them.
///
/// All of it goes through `Locale`, so a Danish reader gets Danish month names and
/// 24-hour times without a second code path. Nothing here hardcodes a format
/// string beyond what `Date.FormatStyle` needs.
enum Format {
    /// A due date as a row shows it: "Today 14:00", "Tomorrow", "3 Mar".
    ///
    /// Relative words for the days either side of today, because that is how
    /// people talk about them; an absolute date beyond that, because "in 9 days"
    /// is harder to act on than "24 Mar".
    static func due(_ date: Date, hasTime: Bool, locale: Locale, calendar: Calendar = .current) -> String {
        var calendar = calendar
        calendar.locale = locale
        let day = relativeDay(date, locale: locale, calendar: calendar)
        guard hasTime else { return day }
        let time = date.formatted(.dateTime.hour().minute().locale(locale))
        return "\(day) \(time)"
    }

    /// The day part alone.
    static func relativeDay(_ date: Date, locale: Locale, calendar: Calendar = .current) -> String {
        var calendar = calendar
        calendar.locale = locale
        if calendar.isDateInToday(date) {
            return Localized.string("date.today", locale: locale)
        }
        if calendar.isDateInTomorrow(date) {
            return Localized.string("date.tomorrow", locale: locale)
        }
        if calendar.isDateInYesterday(date) {
            return Localized.string("date.yesterday", locale: locale)
        }
        // Inside this year the year is noise; outside it, it is the whole point.
        let sameYear = calendar.component(.year, from: date) == calendar.component(.year, from: .now)
        return sameYear
            ? date.formatted(.dateTime.day().month(.abbreviated).locale(locale))
            : date.formatted(.dateTime.day().month(.abbreviated).year().locale(locale))
    }

    /// "2 hours ago" — for activity feeds and comment timestamps.
    static func relative(_ date: Date, locale: Locale) -> String {
        date.formatted(.relative(presentation: .named).locale(locale))
    }

    /// An absolute moment with day and time, for detail panes.
    static func dateTime(_ date: Date, locale: Locale) -> String {
        date.formatted(.dateTime.day().month(.abbreviated).year().hour().minute().locale(locale))
    }

    /// A day only, no time.
    static func date(_ date: Date, locale: Locale) -> String {
        date.formatted(.dateTime.day().month(.wide).year().locale(locale))
    }

    /// An estimate in minutes as "45 min" or "1 h 30 min".
    static func minutes(_ total: Int, locale: Locale) -> String {
        guard total > 0 else { return "" }
        let hours = total / 60
        let minutes = total % 60
        let hourUnit = Localized.string("unit.hourShort", locale: locale)
        let minuteUnit = Localized.string("unit.minuteShort", locale: locale)
        if hours == 0 { return "\(minutes) \(minuteUnit)" }
        if minutes == 0 { return "\(hours) \(hourUnit)" }
        return "\(hours) \(hourUnit) \(minutes) \(minuteUnit)"
    }
}

extension Google_Protobuf_Timestamp {
    /// The `Date` this timestamp represents.
    ///
    /// SwiftProtobuf already offers `.date`; this alias exists so call sites read
    /// the same whether they came from a required or an optional field.
    var asDate: Date { date }
}
