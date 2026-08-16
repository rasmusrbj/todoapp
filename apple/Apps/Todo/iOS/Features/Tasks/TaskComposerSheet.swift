import SwiftUI

/// Creating and editing a task.
///
/// Three bands, in the order a person thinks: **what it is**, **when it happens**,
/// **who and what it touches**. That is the same grouping as the web dialog, so a
/// user moving between the two is not relearning the form.
///
/// Native pickers throughout — `DatePicker` for dates, `Picker` for enums — rather
/// than anything hand-rolled. On iOS the platform control is both the better date
/// picker and the one people already know.
struct TaskComposerSheet: View {
    let request: ComposerRequest
    /// Lists the caller may write to. Only more than one makes the picker worth showing.
    let lists: [Todo_V1_TodoList]

    @Environment(Actions.self) private var actions
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    @State private var draft: TaskDraft
    @State private var hasDueDate: Bool
    @State private var hasStartDate: Bool
    @State private var newSubtask = ""
    @State private var isSaving = false

    /// The task being edited, if any. Editing takes several RPCs, not one.
    private let editing: Todo_V1_Task?

    init(request: ComposerRequest, lists: [Todo_V1_TodoList]) {
        self.request = request
        self.lists = lists
        switch request.mode {
        case let .create(draft):
            _draft = State(initialValue: draft)
            self.editing = nil
        case let .edit(task):
            _draft = State(initialValue: TaskDraft(task: task))
            self.editing = task
        }
        let seeded = _draft.wrappedValue
        _hasDueDate = State(initialValue: seeded.dueAt != nil)
        _hasStartDate = State(initialValue: seeded.startsAt != nil)
    }

    /// The list the task lives on, for its labels and its members.
    private var currentList: Todo_V1_TodoList? {
        lists.first { $0.id == draft.listId }
    }

    private var assignableMembers: [Todo_V1_ListMember] {
        (currentList?.members ?? []).filter { $0.role.canWrite }
    }

    var body: some View {
        NavigationStack {
            Form {
                whatItIs
                whenItHappens
                whoAndWhat
                if editing == nil { checklist }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle(editing == nil ? "tasks.newTask" : "tasks.editTask")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("action.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(editing == nil ? "action.create" : "action.save") {
                        Task { await save() }
                    }
                    .fontWeight(.semibold)
                    .disabled(!draft.isValid || isSaving)
                }
            }
            .interactiveDismissDisabled(isSaving)
            .overlay {
                if isSaving {
                    ProgressView().controlSize(.large)
                }
            }
        }
    }

    // MARK: Bands

    private var whatItIs: some View {
        Section {
            TextField("tasks.titlePlaceholder", text: $draft.title, axis: .vertical)
                .font(.body.weight(.medium))
                .lineLimit(1...3)

            TextField("tasks.descriptionPlaceholder", text: $draft.description, axis: .vertical)
                .lineLimit(2...6)
                .foregroundStyle(Theme.textSecondary)

            if lists.count > 1 {
                Picker("tasks.list", selection: $draft.listId) {
                    ForEach(lists, id: \.id) { list in
                        Text(list.name).tag(list.id)
                    }
                }
                // Changing list invalidates the labels, which belong to the list
                // being left. Keeping them would send ids the server will reject.
                .onChange(of: draft.listId) { _, _ in
                    draft.labelIds = []
                    draft.assigneeId = nil
                }
            }

            EnumPicker(title: "tasks.priority", selection: $draft.priority)

            if editing == nil {
                EnumPicker(title: "tasks.status", selection: $draft.status)
            }
        } header: {
            Text("tasks.sectionWhat")
        }
    }

    private var whenItHappens: some View {
        Section {
            Toggle("tasks.hasDueDate", isOn: $hasDueDate)
                .onChange(of: hasDueDate) { _, isOn in
                    // Default to 9am rather than this instant: an all-day task
                    // stamped 23:47 reads as overdue thirteen minutes later.
                    draft.dueAt = isOn ? Self.defaultDueDate() : nil
                    if !isOn { draft.dueHasTime = false }
                }

            if hasDueDate, draft.dueAt != nil {
                DatePicker(
                    "tasks.dueDate",
                    selection: Binding(
                        get: { draft.dueAt ?? Self.defaultDueDate() },
                        set: { draft.dueAt = $0 }
                    ),
                    displayedComponents: draft.dueHasTime ? [.date, .hourAndMinute] : [.date]
                )
                Toggle("tasks.hasDueTime", isOn: $draft.dueHasTime)
            }

            Toggle("tasks.hasStartDate", isOn: $hasStartDate)
                .onChange(of: hasStartDate) { _, isOn in
                    draft.startsAt = isOn ? Calendar.current.startOfDay(for: .now) : nil
                }

            if hasStartDate, draft.startsAt != nil {
                DatePicker(
                    "tasks.startDate",
                    selection: Binding(
                        get: { draft.startsAt ?? .now },
                        set: { draft.startsAt = $0 }
                    ),
                    displayedComponents: [.date]
                )
            }

            EnumPicker(title: "tasks.repeat", selection: $draft.recurrence)
            if draft.repeats {
                Stepper(
                    "tasks.repeatEvery \(draft.recurrenceInterval)",
                    value: $draft.recurrenceInterval,
                    in: 1...30
                )
            }

            Stepper(
                value: $draft.estimateMinutes,
                in: 0...(60 * 24),
                step: 15
            ) {
                HStack {
                    Text("tasks.estimate")
                    Spacer()
                    Text(
                        draft.estimateMinutes == 0
                            ? Localized.string("tasks.noEstimate", locale: locale)
                            : Format.minutes(draft.estimateMinutes, locale: locale)
                    )
                    .foregroundStyle(Theme.textSecondary)
                    .monospacedDigit()
                }
            }
        } header: {
            Text("tasks.sectionWhen")
        }
    }

    @ViewBuilder
    private var whoAndWhat: some View {
        Section {
            if assignableMembers.isEmpty {
                Text("tasks.noAssignableMembers")
                    .font(.caption)
                    .foregroundStyle(Theme.textTertiary)
            } else {
                Picker("tasks.assignee", selection: Binding(
                    get: { draft.assigneeId ?? "" },
                    set: { draft.assigneeId = $0.isEmpty ? nil : $0 }
                )) {
                    Text("tasks.unassigned").tag("")
                    ForEach(assignableMembers, id: \.id) { member in
                        Text(member.user.displayName).tag(member.user.id)
                    }
                }
            }

            if let labels = currentList?.labels, !labels.isEmpty {
                LabelSelector(labels: labels, selected: $draft.labelIds)
            } else {
                Text("tasks.noLabelsOnList")
                    .font(.caption)
                    .foregroundStyle(Theme.textTertiary)
            }
        } header: {
            Text("tasks.sectionWho")
        } footer: {
            if editing != nil {
                // Assignee and labels have their own RPCs — the server validates
                // membership and label ownership on each — so the sheet says which
                // parts it will save separately rather than pretending it is one write.
                Text("tasks.editFooter")
            }
        }
    }

    private var checklist: some View {
        Section {
            ForEach(Array(draft.subtaskTitles.enumerated()), id: \.offset) { index, title in
                HStack {
                    Image(systemName: "circle")
                        .font(.caption)
                        .foregroundStyle(Theme.textTertiary)
                    Text(title)
                    Spacer()
                    Button {
                        draft.subtaskTitles.remove(at: index)
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .foregroundStyle(Theme.textTertiary)
                    }
                    .pressable(0.9)
                    .accessibilityLabel("action.remove")
                }
            }

            HStack {
                TextField("tasks.addSubtaskPlaceholder", text: $newSubtask)
                    .onSubmit(appendSubtask)
                Button(action: appendSubtask) {
                    Image(systemName: "plus.circle.fill")
                }
                .pressable(0.9)
                .disabled(newSubtask.trimmingCharacters(in: .whitespaces).isEmpty)
                .accessibilityLabel("tasks.addSubtask")
            }
        } header: {
            Text("tasks.sectionChecklist")
        }
    }

    // MARK: Actions

    private func appendSubtask() {
        let trimmed = newSubtask.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        draft.subtaskTitles.append(trimmed)
        newSubtask = ""
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }

        if let editing {
            // The plain fields first. Only if that succeeds are the side-effecting
            // ones touched, so a rejected title does not leave the labels changed.
            guard await actions.update(draft, id: editing.id) else { return }

            let assigneeChanged = draft.assigneeId != (editing.hasAssignee ? editing.assignee.id : nil)
            if assigneeChanged {
                await actions.assign(taskId: editing.id, to: draft.assigneeId)
            }
            if Set(draft.labelIds) != Set(editing.labels.map(\.id)) {
                await actions.setLabels(taskId: editing.id, labelIds: draft.labelIds)
            }
            if draft.status != editing.status {
                await actions.setStatus(taskId: editing.id, status: draft.status)
            }
            if draft.listId != editing.list.id {
                await actions.move(taskId: editing.id, toList: draft.listId, position: 0)
            }
        } else {
            guard await actions.create(draft) != nil else { return }
        }

        guard actions.failure == nil else { return }
        Haptics.success()
        dismiss()
    }

    /// 9am tomorrow — the most likely thing someone means when they turn on a due
    /// date without saying when.
    private static func defaultDueDate() -> Date {
        let calendar = Calendar.current
        let tomorrow = calendar.date(byAdding: .day, value: 1, to: .now) ?? .now
        return calendar.date(bySettingHour: 9, minute: 0, second: 0, of: tomorrow) ?? tomorrow
    }
}

/// Multi-select over a list's labels, as chips rather than a stack of toggles.
struct LabelSelector: View {
    let labels: [Todo_V1_LabelRef]
    @Binding var selected: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            Text("tasks.labels")
                .font(.subheadline)
            // A wrapping flow, so ten labels do not become a ten-row list.
            FlowLayout(spacing: Theme.Space.sm) {
                ForEach(labels, id: \.id) { label in
                    let isOn = selected.contains(label.id)
                    Button {
                        if isOn {
                            selected.removeAll { $0 == label.id }
                        } else {
                            selected.append(label.id)
                        }
                    } label: {
                        HStack(spacing: 4) {
                            if isOn {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 9, weight: .bold))
                            }
                            Text(label.name)
                        }
                        .font(.caption.weight(.medium))
                        .foregroundStyle(isOn ? label.color.tint : Theme.textSecondary)
                        .padding(.horizontal, Theme.Space.sm + 2)
                        .padding(.vertical, 5)
                        .background(isOn ? label.color.wash : Theme.surfaceInset, in: Capsule())
                        .overlay(
                            isOn ? Capsule().stroke(label.color.tint.opacity(0.4), lineWidth: 1) : nil
                        )
                    }
                    .pressable(0.94)
                    .accessibilityAddTraits(isOn ? [.isButton, .isSelected] : .isButton)
                }
            }
        }
        .padding(.vertical, Theme.Space.xs)
    }
}
