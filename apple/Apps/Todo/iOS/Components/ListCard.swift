import SwiftUI

/// A list on the board.
///
/// Content-led: the list's own colour, its name, and the numbers that say whether
/// it needs attention. Flat, bordered, no shadow — the colour is the only thing
/// carrying identity, which is why nothing else in the card competes for hue.
struct ListCard: View {
    let list: Todo_V1_TodoList
    @Environment(\.locale) private var locale

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            HStack(spacing: Theme.Space.sm) {
                ColorDot(color: list.color.tint, size: 10)
                Text(list.name)
                    .font(.headline)
                    .foregroundStyle(Theme.textPrimary)
                    .lineLimit(1)
                Spacer(minLength: Theme.Space.sm)
                if list.archived {
                    Badge(text: "lists.archived", tint: Theme.textTertiary, symbol: "archivebox")
                }
            }

            if !list.description_p.isEmpty {
                Text(list.description_p)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textSecondary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
            }

            VStack(alignment: .leading, spacing: Theme.Space.sm) {
                ProgressBar(percent: Int(list.stats.completionPercent), tint: list.color.tint)

                HStack(spacing: Theme.Space.md) {
                    Text("lists.openCount \(Int(list.stats.openTaskCount))")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.textSecondary)
                        .monospacedDigit()

                    if list.stats.overdueTaskCount > 0 {
                        Label {
                            Text("lists.overdueCount \(Int(list.stats.overdueTaskCount))")
                        } icon: {
                            Image(systemName: "exclamationmark.circle")
                        }
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.danger)
                        .monospacedDigit()
                    }

                    Spacer(minLength: 0)

                    Text(verbatim: "\(list.stats.completionPercent)%")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.textTertiary)
                        .monospacedDigit()
                }
            }

            HStack(spacing: Theme.Space.sm) {
                // Members only when there is more than one, since "1 member" on a
                // private list is a fact nobody needs.
                if list.stats.memberCount > 1 {
                    MemberStack(members: list.members)
                }
                Spacer(minLength: 0)
                if let next = nextDue {
                    DueDateLabel(date: next, hasTime: false, isOverdue: false, compact: true)
                }
                RoleBadge(role: list.viewerRole)
            }
        }
        .padding(Theme.Space.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardSurface()
        .opacity(list.archived ? 0.65 : 1)
    }

    private var nextDue: Date? {
        list.stats.hasNextDueAt ? list.stats.nextDueAt.date : nil
    }
}

/// Overlapping avatars — the standard "who else is here" motif.
struct MemberStack: View {
    let members: [Todo_V1_ListMember]
    var size: CGFloat = 22
    var limit: Int = 4

    var body: some View {
        HStack(spacing: -size / 3) {
            ForEach(members.prefix(limit), id: \.id) { member in
                AvatarView(name: member.user.displayName, url: member.user.avatarURL, size: size)
            }
            if members.count > limit {
                Text(verbatim: "+\(members.count - limit)")
                    .font(.system(size: size * 0.36, weight: .semibold))
                    .foregroundStyle(Theme.textSecondary)
                    .frame(width: size, height: size)
                    .background(Theme.surfaceInset, in: Circle())
                    .overlay(Circle().stroke(Theme.border, lineWidth: 1))
            }
        }
        .accessibilityElement()
        .accessibilityLabel("a11y.memberCount \(members.count)")
    }
}

/// One entry in the activity feed.
struct ActivityRow: View {
    let activity: Todo_V1_Activity
    var showsList: Bool = true
    @Environment(\.locale) private var locale

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.md) {
            Image(systemName: activity.action.symbol)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Theme.textSecondary)
                .frame(width: 26, height: 26)
                .background(Theme.surfaceInset, in: Circle())

            VStack(alignment: .leading, spacing: 2) {
                // Actor and action in one sentence, target quoted after it. The
                // target label is the name as it was at the time, so the feed still
                // reads correctly after a rename or a delete.
                (
                    Text(activity.actor.displayName).font(.subheadline.weight(.semibold))
                        + Text(verbatim: " ")
                        + Text(activity.action.displayName).font(.subheadline)
                )
                .foregroundStyle(Theme.textPrimary)

                if !activity.targetLabel.isEmpty {
                    Text(activity.targetLabel)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                        .lineLimit(2)
                }

                if let change = changeSummary {
                    Text(change)
                        .font(.caption)
                        .foregroundStyle(Theme.textTertiary)
                }

                HStack(spacing: Theme.Space.sm) {
                    Text(Format.relative(activity.createdAt.date, locale: locale))
                    if showsList, activity.hasList {
                        ListTag(name: activity.list.name, color: activity.list.color)
                    }
                }
                .font(.caption)
                .foregroundStyle(Theme.textTertiary)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, Theme.Space.md)
        .padding(.horizontal, Theme.Space.lg)
    }

    /// "todo → done", with both ends resolved to their display names.
    ///
    /// The server sends enum *names*, never localized text, precisely so the
    /// client can translate them — so a raw `TASK_STATUS_DONE` here would be a bug.
    private var changeSummary: String? {
        guard activity.hasChange else { return nil }
        let change = activity.change
        let from = Self.localizedValue(change.fromValue, locale: locale)
        let to = Self.localizedValue(change.toValue, locale: locale)
        guard !from.isEmpty || !to.isEmpty else { return nil }
        if from.isEmpty { return to }
        if to.isEmpty { return from }
        return "\(from) → \(to)"
    }

    /// Resolves an enum name from an activity diff to its display name, leaving
    /// plain text (a renamed title, say) alone.
    private static func localizedValue(_ raw: String, locale: Locale) -> String {
        guard !raw.isEmpty else { return "" }
        guard let key = ActivityValueNames.displayKey(for: raw) else { return raw }
        return Localized.string(key, locale: locale)
    }
}

/// Maps the enum names that appear in `ActivityChange` onto display keys.
///
/// `ActivityChange.from_value`/`to_value` are `string`, not a typed enum — they
/// have to be, because the same field carries a status on one row and a renamed
/// title on the next. So the lookup is by name, and a name that matches nothing is
/// passed through as the free text it is.
enum ActivityValueNames {
    static func displayKey(for protoName: String) -> String? {
        table[protoName]
    }

    /// Built from the enums that actually appear in an activity diff: status,
    /// priority and role changes.
    private static let table: [String: String] = {
        var table: [String: String] = [:]
        for value in Todo_V1_TaskStatus.selectable { table[value.protoName] = value.displayKey }
        for value in Todo_V1_TaskPriority.selectable { table[value.protoName] = value.displayKey }
        for value in Todo_V1_MemberRole.selectable { table[value.protoName] = value.displayKey }
        return table
    }()

}
