import SwiftUI

/// The proto-aware badges. These know about `todo.v1` enums, which is why they
/// live in the app rather than in `DesignSystem`.
///
/// Each one renders a localized display name — never a raw enum — through
/// `DisplayableEnum`.

/// A task's status.
struct StatusBadge: View {
    let status: Todo_V1_TaskStatus

    var body: some View {
        Badge(text: status.displayName, tint: status.tint, symbol: status.symbol)
    }
}

/// Priority as filled bars rather than a word.
///
/// A row already carries a title, a due date, a list and maybe labels; another
/// text pill for "High" is the one that pushes it over. Three ascending bars read
/// as urgency at a glance and cost 12 points. The word is still there for
/// VoiceOver, and the detail pane spells it out.
struct PriorityIndicator: View {
    let priority: Todo_V1_TaskPriority

    var body: some View {
        if priority.isWorthShowing {
            HStack(alignment: .bottom, spacing: 1.5) {
                ForEach(1...3, id: \.self) { step in
                    RoundedRectangle(cornerRadius: 0.5)
                        .fill(step <= priority.bars ? priority.tint : Theme.surfaceInset)
                        .frame(width: 2.5, height: 4 + CGFloat(step) * 2)
                }
            }
            .accessibilityElement()
            .accessibilityLabel(Text(priority.displayName))
        }
    }
}

/// Priority spelled out, for detail panes and pickers.
struct PriorityBadge: View {
    let priority: Todo_V1_TaskPriority

    var body: some View {
        Badge(text: priority.displayName, tint: priority.tint, symbol: "flag")
    }
}

/// A label chip in its list's colour.
struct LabelChip: View {
    let name: String
    let color: Todo_V1_ListColor
    var compact = false

    var body: some View {
        Text(name)
            .font(compact ? .caption2.weight(.medium) : .caption.weight(.medium))
            .foregroundStyle(color.tint)
            .lineLimit(1)
            .padding(.horizontal, compact ? 6 : Theme.Space.sm)
            .padding(.vertical, compact ? 2 : 3)
            .background(color.wash, in: Capsule())
    }
}

/// A member's role.
struct RoleBadge: View {
    let role: Todo_V1_MemberRole

    var body: some View {
        Badge(
            text: role.displayName,
            tint: role.isOwner ? Theme.accent : Theme.textSecondary
        )
    }
}

/// Who can see a list.
struct VisibilityBadge: View {
    let visibility: Todo_V1_ListVisibility

    var body: some View {
        Badge(text: visibility.displayName, tint: Theme.textSecondary, symbol: visibility.symbol)
    }
}

/// An account's lifecycle state, for the admin screens.
struct UserStatusBadge: View {
    let status: Todo_V1_UserStatus

    var body: some View {
        Badge(text: status.displayName, tint: status.tint)
    }
}

/// A due date, red when it is in the past and the task is still open.
struct DueDateLabel: View {
    let date: Date
    let hasTime: Bool
    let isOverdue: Bool
    var compact = false
    @Environment(\.locale) private var locale

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: isOverdue ? "exclamationmark.circle" : "calendar")
                .font(.system(size: compact ? 9 : 10, weight: .semibold))
            Text(Format.due(date, hasTime: hasTime, locale: locale))
        }
        .font(compact ? .caption2.weight(.medium) : .caption.weight(.medium))
        .foregroundStyle(isOverdue ? Theme.danger : Theme.textSecondary)
        .lineLimit(1)
        .fixedSize()
        // `children: .ignore` is what makes the label below *replace* the icon and text
        // rather than being added alongside them. Without it VoiceOver reads the date
        // twice — once from the custom label, once from the Text inside.
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            isOverdue
                ? Text("a11y.overdueOn \(Format.due(date, hasTime: hasTime, locale: locale))")
                : Text("a11y.dueOn \(Format.due(date, hasTime: hasTime, locale: locale))")
        )
    }
}

/// A list's identity in one compact unit: colour dot plus name.
struct ListTag: View {
    let name: String
    let color: Todo_V1_ListColor

    var body: some View {
        HStack(spacing: Theme.Space.xs + 1) {
            ColorDot(color: color.tint, size: 6)
            Text(name)
                .lineLimit(1)
        }
        .font(.caption.weight(.medium))
        .foregroundStyle(Theme.textSecondary)
    }
}

/// A picker over any localized proto enum. One control for status, priority,
/// colour, visibility, role, language and appearance, so they all behave alike.
struct EnumPicker<Value: DisplayableEnum>: View {
    let title: LocalizedStringKey
    @Binding var selection: Value
    /// Restricts the offered values — a status picker on a list you can only
    /// comment on, for instance.
    var allowed: [Value]?

    private var values: [Value] { allowed ?? Value.selectable }

    var body: some View {
        Picker(title, selection: $selection) {
            ForEach(values, id: \.self) { value in
                Text(value.displayName).tag(value)
            }
        }
    }
}
