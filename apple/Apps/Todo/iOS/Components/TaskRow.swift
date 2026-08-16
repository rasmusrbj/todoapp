import SwiftUI

/// The leading circle that completes a task.
///
/// A `Button` and not a tap gesture, so it is reachable by VoiceOver and Switch
/// Control and gets the press animation for free. It is also the one control on a
/// row that must not navigate — hence the separate hit area.
struct TaskCheckButton: View {
    let task: Todo_V1_Task
    var canEdit: Bool
    var size: CGFloat = 22

    @Environment(Actions.self) private var actions

    private var isPending: Bool { actions.isPending(task.id) }

    var body: some View {
        Button {
            Task { await actions.toggleDone(task) }
        } label: {
            ZStack {
                Image(systemName: task.status.symbol)
                    .font(.system(size: size, weight: .light))
                    .foregroundStyle(task.status.tint)
                    // The symbol swap is the feedback for the tap, so it should
                    // feel like a switch throwing rather than a fade.
                    .contentTransition(.symbolEffect(.replace))
                    .opacity(isPending ? 0.35 : 1)
                if isPending {
                    ProgressView().controlSize(.mini)
                }
            }
            .frame(width: size + 12, height: size + 12)
            .contentShape(Rectangle())
        }
        .pressable(0.85)
        .disabled(!canEdit || isPending)
        .accessibilityLabel(task.status == .done ? "a11y.markNotDone" : "a11y.markDone")
        .accessibilityValue(Text(task.status.displayName))
    }
}

/// A task as it appears in every list in the app.
///
/// Deliberately one component rather than a per-screen variant: a task should look
/// identical on Today, in a list, and in search results, so the eye learns it once.
/// `showsList` is the only difference — inside one list, repeating its name on
/// every row is noise.
struct TaskRow: View {
    let task: Todo_V1_Task
    var canEdit: Bool = true
    var showsList: Bool = true
    /// Multi-select support. `nil` means selection is off.
    var isSelected: Bool?
    var onToggleSelection: (() -> Void)?

    @Environment(\.locale) private var locale

    private var isDone: Bool { Todo_V1_TaskStatus.terminal.contains(task.status) }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.sm) {
            if let isSelected, let onToggleSelection {
                Button(action: onToggleSelection) {
                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.system(size: 20, weight: .light))
                        .foregroundStyle(isSelected ? Theme.accent : Theme.textTertiary)
                        .frame(width: 32, height: 32)
                        .contentShape(Rectangle())
                }
                .pressable(0.85)
                .accessibilityLabel(isSelected ? "a11y.deselect" : "a11y.select")
            } else {
                TaskCheckButton(task: task, canEdit: canEdit)
            }

            VStack(alignment: .leading, spacing: Theme.Space.xs + 1) {
                HStack(alignment: .firstTextBaseline, spacing: Theme.Space.sm) {
                    Text(task.title)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(isDone ? Theme.textTertiary : Theme.textPrimary)
                        .strikethrough(isDone, color: Theme.textTertiary)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Spacer(minLength: 0)
                    PriorityIndicator(priority: task.priority)
                }

                if !task.description_p.isEmpty {
                    Text(task.description_p)
                        .font(.caption)
                        .foregroundStyle(Theme.textSecondary)
                        .lineLimit(1)
                }

                metadata
            }

            if task.hasAssignee {
                AvatarView(
                    name: task.assignee.displayName,
                    url: task.assignee.avatarURL,
                    size: 24
                )
                .padding(.top, 2)
            }
        }
        .padding(.vertical, Theme.Space.sm + 2)
        .padding(.horizontal, Theme.Space.lg)
        .contentShape(Rectangle())
        .opacity(task.status == .cancelled ? 0.6 : 1)
    }

    /// The second line: only what is actually set, so a bare task stays a single
    /// line and a rich one earns its height.
    ///
    /// `ViewThatFits` picks the richest variant the width allows and drops whole items
    /// rather than shrinking them. That distinction matters: an `HStack` given too
    /// little room compresses its children, and a squeezed chip renders as a single
    /// letter — "Ærinder" became "Æ", which says nothing at all. Dropping the least
    /// important item is the honest degradation.
    ///
    /// Order of sacrifice: labels first (a task's list matters more than its tag), then
    /// the estimate, then the comment count. The due date, the list and the checklist
    /// progress survive at every width.
    @ViewBuilder
    private var metadata: some View {
        let hasAnything = task.hasDueAt
            || (showsList && task.hasList)
            || !task.labels.isEmpty
            || task.subtaskCount > 0
            || task.commentCount > 0
            || task.estimateMinutes > 0

        if hasAnything {
            ViewThatFits(in: .horizontal) {
                metaRow(showsLabels: true, showsEstimate: true, showsComments: true)
                metaRow(showsLabels: false, showsEstimate: true, showsComments: true)
                metaRow(showsLabels: false, showsEstimate: false, showsComments: true)
                metaRow(showsLabels: false, showsEstimate: false, showsComments: false)
            }
        }
    }

    private func metaRow(
        showsLabels: Bool,
        showsEstimate: Bool,
        showsComments: Bool
    ) -> some View {
        HStack(spacing: Theme.Space.sm) {
            if task.hasDueAt {
                DueDateLabel(
                    date: task.dueAt.date,
                    hasTime: task.dueHasTime,
                    isOverdue: task.overdue,
                    compact: true
                )
            }

            if showsList, task.hasList {
                ListTag(name: task.list.name, color: task.list.color)
                    .fixedSize()
            }

            if task.subtaskCount > 0 {
                metaItem(
                    symbol: "checklist",
                    text: "\(task.completedSubtaskCount)/\(task.subtaskCount)"
                )
            }

            if showsComments, task.commentCount > 0 {
                metaItem(symbol: "text.bubble", text: "\(task.commentCount)")
            }

            if showsEstimate, task.estimateMinutes > 0 {
                metaItem(
                    symbol: "clock",
                    text: Format.minutes(Int(task.estimateMinutes), locale: locale)
                )
            }

            if showsLabels, !task.labels.isEmpty {
                LabelChip(
                    name: task.labels[0].name,
                    color: task.labels[0].color,
                    compact: true
                )
                .fixedSize()
                if task.labels.count > 1 {
                    Text(verbatim: "+\(task.labels.count - 1)")
                        .font(.caption2.weight(.medium))
                        .foregroundStyle(Theme.textTertiary)
                        .fixedSize()
                }
            }

            Spacer(minLength: 0)
        }
        .lineLimit(1)
    }

    private func metaItem(symbol: String, text: String) -> some View {
        HStack(spacing: 3) {
            Image(systemName: symbol).font(.system(size: 9, weight: .semibold))
            Text(text).monospacedDigit()
        }
        .font(.caption2.weight(.medium))
        .foregroundStyle(Theme.textTertiary)
        // One line, at its natural width. Without `fixedSize` the enclosing HStack
        // compresses these and "1 h 30 min" wraps onto a second line, which grows the
        // row by a whole line for no extra information.
        .lineLimit(1)
        .fixedSize()
    }
}

/// A group of task rows in one bordered card, divided by hairlines.
///
/// The card is the container, not each row: twenty individually-bordered cards is a
/// stack of boxes, while one card with dividers reads as a list.
///
/// Named `TaskCardGroup` rather than `TaskGroup`, which is Swift concurrency's own
/// type — the shadowing made `TaskCardGroup(tasks:)` resolve to the stdlib initializer
/// and fail with an unrelated error about `ChildTaskResult`.
struct TaskCardGroup<Row: View>: View {
    let tasks: [Todo_V1_Task]
    @ViewBuilder var row: (Todo_V1_Task) -> Row

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(tasks.enumerated()), id: \.element.id) { index, task in
                if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.xl) }
                row(task)
            }
        }
        .cardSurface()
    }
}
