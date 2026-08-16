import Observation
import SwiftUI

/// One task, in full: what it is, its checklist, its conversation, and its history.
struct TaskDetailScreen: View {
    let taskId: String

    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale
    @Environment(\.dismiss) private var dismiss

    @State private var model: TaskDetailModel?
    @State private var composing: ComposerRequest?
    @State private var confirmingDelete = false

    var body: some View {
        ScreenScaffold(refresh: { await model?.load() }) {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let model, let task = model.task {
                    summary(task, model: model)
                    if model.canWrite || !task.subtasks.isEmpty {
                        SubtaskCard(task: task, canEdit: model.canWrite)
                    }
                    CommentsCard(
                        taskId: taskId,
                        comments: model.comments,
                        viewerId: session.viewer?.id ?? "",
                        isListOwner: model.list?.viewerRole.isOwner ?? false,
                        canComment: model.canComment
                    )
                    if !model.activity.isEmpty {
                        ScreenSection("activity.title") {
                            VStack(spacing: 0) {
                                ForEach(Array(model.activity.enumerated()), id: \.element.id) { index, entry in
                                    if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.lg) }
                                    ActivityRow(activity: entry, showsList: false)
                                }
                            }
                            .cardSurface()
                        }
                    }
                } else if let failure = model?.taskState.failure {
                    StateMessage(
                        symbol: failure.reason == .taskNotFound ? "questionmark.folder" : "exclamationmark.triangle",
                        title: failure.reason == .taskNotFound ? "tasks.notFoundTitle" : "state.failedTitle",
                        message: LocalizedStringKey(failure.messageKey),
                        actionTitle: "action.retry",
                        action: { Task { await model?.load() } }
                    )
                } else {
                    VStack(spacing: Theme.Space.sm) {
                        Skeleton(height: 140, cornerRadius: Theme.Radius.card)
                        Skeleton(height: 120, cornerRadius: Theme.Radius.card)
                    }
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle(model?.task?.title ?? "")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let model, let task = model.task, model.canWrite {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button {
                            composing = .edit(task)
                        } label: {
                            Label("action.edit", systemImage: "pencil")
                        }

                        Menu {
                            ForEach(Todo_V1_TaskStatus.selectable, id: \.self) { status in
                                Button {
                                    Task { await actions.setStatus(taskId: task.id, status: status) }
                                } label: {
                                    Label(status.displayName, systemImage: status.symbol)
                                }
                            }
                        } label: {
                            Label("tasks.status", systemImage: "arrow.triangle.2.circlepath")
                        }

                        if model.otherWritableLists.count > 0 {
                            Menu {
                                ForEach(model.otherWritableLists, id: \.id) { target in
                                    Button(target.name) {
                                        Task {
                                            await actions.move(
                                                taskId: task.id,
                                                toList: target.id,
                                                position: 0
                                            )
                                        }
                                    }
                                }
                            } label: {
                                Label("tasks.moveToList", systemImage: "arrow.right.arrow.left")
                            }
                        }

                        Divider()
                        Button(role: .destructive) {
                            confirmingDelete = true
                        } label: {
                            Label("action.delete", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .accessibilityLabel("action.more")
                }
            }
        }
        .task {
            if model == nil { model = TaskDetailModel(backend: session.backend, taskId: taskId) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(item: $composing) { request in
            TaskComposerSheet(request: request, lists: model?.composerLists ?? [])
        }
        .confirmationDialog(
            "tasks.confirmDeleteTitle",
            isPresented: $confirmingDelete,
            titleVisibility: .visible
        ) {
            Button("action.delete", role: .destructive) {
                Task {
                    await actions.delete(taskId: taskId)
                    // Nothing left to show once it is gone, so go back rather than
                    // leaving a detail screen for a task that no longer exists.
                    if actions.failure == nil { dismiss() }
                }
            }
            Button("action.cancel", role: .cancel) {}
        } message: {
            Text("tasks.confirmDeleteBody")
        }
    }

    // MARK: Summary

    private func summary(_ task: Todo_V1_Task, model: TaskDetailModel) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            HStack(alignment: .top, spacing: Theme.Space.sm) {
                TaskCheckButton(task: task, canEdit: model.canWrite, size: 26)
                    .padding(.leading, -Theme.Space.sm)
                Text(task.title)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Theme.textPrimary)
                    .strikethrough(Todo_V1_TaskStatus.terminal.contains(task.status), color: Theme.textTertiary)
                Spacer(minLength: 0)
            }

            if !task.description_p.isEmpty {
                Text(task.description_p)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textSecondary)
            }

            FlowLayout(spacing: Theme.Space.sm, lineSpacing: Theme.Space.sm) {
                StatusBadge(status: task.status)
                PriorityBadge(priority: task.priority)
                if task.hasDueAt {
                    DueDateLabel(
                        date: task.dueAt.date,
                        hasTime: task.dueHasTime,
                        isOverdue: task.overdue
                    )
                }
                if task.repeatsRegularly {
                    Badge(
                        text: task.recurrence.frequency.displayName,
                        tint: Theme.textSecondary,
                        symbol: "repeat"
                    )
                }
                if task.estimateMinutes > 0 {
                    Badge(
                        text: LocalizedStringKey(Format.minutes(Int(task.estimateMinutes), locale: locale)),
                        tint: Theme.textSecondary,
                        symbol: "clock"
                    )
                }
            }

            if !task.labels.isEmpty {
                FlowLayout(spacing: Theme.Space.sm, lineSpacing: Theme.Space.sm) {
                    ForEach(task.labels, id: \.id) { label in
                        LabelChip(name: label.name, color: label.color)
                    }
                }
            }

            InsetDivider(leading: 0)

            // The facts pane: list, assignee, and provenance.
            VStack(alignment: .leading, spacing: Theme.Space.sm) {
                if task.hasList {
                    factRow(label: "tasks.list") {
                        NavigationLink(value: TodoRoute.list(task.list.id)) {
                            ListTag(name: task.list.name, color: task.list.color)
                        }
                        .pressable(0.96)
                    }
                }

                factRow(label: "tasks.assignee") {
                    AssigneeControl(
                        task: task,
                        members: model.assignableMembers,
                        viewerId: session.viewer?.id ?? "",
                        canEdit: model.canWrite
                    )
                }

                if !task.labels.isEmpty || !(model.list?.labels.isEmpty ?? true) {
                    if model.canWrite, let labels = model.list?.labels, !labels.isEmpty {
                        factRow(label: "tasks.labels") {
                            LabelQuickPicker(
                                taskId: task.id,
                                labels: labels,
                                selected: task.labels.map(\.id)
                            )
                        }
                    }
                }

                provenance(task)
            }
        }
        .padding(Theme.Space.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardSurface()
    }

    private func factRow<Content: View>(
        label: LocalizedStringKey,
        @ViewBuilder content: () -> Content
    ) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.caption.weight(.medium))
                .foregroundStyle(Theme.textTertiary)
                .frame(width: 76, alignment: .leading)
            content()
            Spacer(minLength: 0)
        }
    }

    private func provenance(_ task: Todo_V1_Task) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            if task.hasCreatedBy {
                Text("tasks.createdBy \(task.createdBy.displayName) \(Format.relative(task.createdAt.date, locale: locale))")
            }
            if task.hasCompletedBy, task.hasCompletedAt {
                Text("tasks.completedBy \(task.completedBy.displayName) \(Format.relative(task.completedAt.date, locale: locale))")
            }
        }
        .font(.caption2)
        .foregroundStyle(Theme.textTertiary)
        .padding(.top, Theme.Space.xs)
    }
}

extension Todo_V1_Task {
    /// Whether the repeat rule actually repeats. A `Recurrence` is always present on
    /// the wire, with `NONE`, so checking `hasRecurrence` would say yes for every task.
    var repeatsRegularly: Bool {
        recurrence.frequency.isConcrete && recurrence.frequency != .none
    }
}

// MARK: - Assignee

/// Assigns the task, with "assign to me" as the first option.
struct AssigneeControl: View {
    let task: Todo_V1_Task
    let members: [Todo_V1_ListMember]
    let viewerId: String
    let canEdit: Bool

    @Environment(Actions.self) private var actions

    var body: some View {
        if canEdit {
            Menu {
                if !viewerId.isEmpty, task.assignee.id != viewerId {
                    Button {
                        Task { await actions.assign(taskId: task.id, to: viewerId) }
                    } label: {
                        Label("tasks.assignToMe", systemImage: "person.crop.circle.badge.checkmark")
                    }
                    Divider()
                }
                ForEach(members, id: \.id) { member in
                    Button {
                        Task { await actions.assign(taskId: task.id, to: member.user.id) }
                    } label: {
                        if member.user.id == task.assignee.id {
                            Label(member.user.displayName, systemImage: "checkmark")
                        } else {
                            Text(member.user.displayName)
                        }
                    }
                }
                if task.hasAssignee {
                    Divider()
                    Button(role: .destructive) {
                        Task { await actions.assign(taskId: task.id, to: nil) }
                    } label: {
                        Label("tasks.unassign", systemImage: "person.crop.circle.badge.xmark")
                    }
                }
            } label: {
                label
            }
            .pressable(0.97)
        } else {
            label
        }
    }

    private var label: some View {
        HStack(spacing: Theme.Space.sm - 2) {
            if task.hasAssignee {
                AvatarView(name: task.assignee.displayName, url: task.assignee.avatarURL, size: 22)
                Text(task.assignee.displayName)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(Theme.textPrimary)
            } else {
                Image(systemName: "person.crop.circle.dashed")
                    .font(.caption)
                    .foregroundStyle(Theme.textTertiary)
                Text("tasks.unassigned")
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
            }
            if canEdit {
                Image(systemName: "chevron.up.chevron.down")
                    .font(.system(size: 8, weight: .semibold))
                    .foregroundStyle(Theme.textTertiary)
            }
        }
    }
}

/// Toggles labels from the detail pane, without opening the whole composer.
struct LabelQuickPicker: View {
    let taskId: String
    let labels: [Todo_V1_LabelRef]
    let selected: [String]

    @Environment(Actions.self) private var actions

    var body: some View {
        Menu {
            ForEach(labels, id: \.id) { label in
                Button {
                    var next = selected
                    if next.contains(label.id) {
                        next.removeAll { $0 == label.id }
                    } else {
                        next.append(label.id)
                    }
                    Task { await actions.setLabels(taskId: taskId, labelIds: next) }
                } label: {
                    if selected.contains(label.id) {
                        Label(label.name, systemImage: "checkmark")
                    } else {
                        Text(label.name)
                    }
                }
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "tag")
                    .font(.system(size: 10, weight: .semibold))
                Text(selected.isEmpty ? "tasks.addLabels" : "tasks.editLabels")
                    .font(.caption.weight(.medium))
            }
            .foregroundStyle(Theme.accent)
        }
        .pressable(0.97)
    }
}

// MARK: - Subtasks

/// The checklist.
struct SubtaskCard: View {
    let task: Todo_V1_Task
    let canEdit: Bool

    @Environment(Actions.self) private var actions
    @State private var newTitle = ""
    @FocusState private var addingFocused: Bool

    var body: some View {
        ScreenSection("tasks.subtasks") {
            VStack(spacing: 0) {
                if task.subtaskCount > 0 {
                    HStack(spacing: Theme.Space.sm) {
                        ProgressBar(
                            percent: Int(
                                Double(task.completedSubtaskCount) / Double(max(task.subtaskCount, 1)) * 100
                            ),
                            tint: Theme.accent
                        )
                        Text(verbatim: "\(task.completedSubtaskCount)/\(task.subtaskCount)")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Theme.textSecondary)
                            .monospacedDigit()
                    }
                    .padding(.horizontal, Theme.Space.lg)
                    .padding(.vertical, Theme.Space.md)
                    InsetDivider(leading: 0)
                }

                ForEach(Array(task.subtasks.enumerated()), id: \.element.id) { index, subtask in
                    if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.md) }
                    SubtaskRow(subtask: subtask, canEdit: canEdit)
                }

                if canEdit {
                    if task.subtaskCount > 0 { InsetDivider(leading: 0) }
                    HStack(spacing: Theme.Space.sm) {
                        Image(systemName: "plus.circle")
                            .font(.system(size: 17, weight: .light))
                            .foregroundStyle(Theme.textTertiary)
                        TextField("tasks.addSubtaskPlaceholder", text: $newTitle)
                            .font(.subheadline)
                            .focused($addingFocused)
                            .onSubmit(add)
                            // Submitting keeps focus so a checklist can be typed in
                            // one go, which is how anyone enters more than one item.
                            .submitLabel(.next)
                    }
                    .padding(.horizontal, Theme.Space.lg)
                    .padding(.vertical, Theme.Space.md)
                }
            }
            .cardSurface()
        }
    }

    private func add() {
        let trimmed = newTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        newTitle = ""
        addingFocused = true
        Task { await actions.addSubtask(taskId: task.id, title: trimmed) }
    }
}

private struct SubtaskRow: View {
    let subtask: Todo_V1_Subtask
    let canEdit: Bool

    @Environment(Actions.self) private var actions
    @State private var isEditing = false
    @State private var title = ""

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            Button {
                Task {
                    await actions.setSubtaskCompleted(
                        subtaskId: subtask.id,
                        completed: !subtask.completed
                    )
                }
            } label: {
                Image(systemName: subtask.completed ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 17, weight: .light))
                    .foregroundStyle(subtask.completed ? Theme.success : Theme.textTertiary)
                    .contentTransition(.symbolEffect(.replace))
            }
            .pressable(0.85)
            .disabled(!canEdit)
            .accessibilityLabel(subtask.completed ? "a11y.markNotDone" : "a11y.markDone")

            if isEditing {
                TextField("tasks.subtaskTitle", text: $title)
                    .font(.subheadline)
                    .onSubmit {
                        isEditing = false
                        let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !trimmed.isEmpty, trimmed != subtask.title else { return }
                        Task { await actions.renameSubtask(subtaskId: subtask.id, title: trimmed) }
                    }
            } else {
                Text(subtask.title)
                    .font(.subheadline)
                    .foregroundStyle(subtask.completed ? Theme.textTertiary : Theme.textPrimary)
                    .strikethrough(subtask.completed, color: Theme.textTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .onTapGesture {
                        guard canEdit else { return }
                        title = subtask.title
                        isEditing = true
                    }
            }

            Spacer(minLength: 0)

            if canEdit {
                Button {
                    Task { await actions.deleteSubtask(subtaskId: subtask.id) }
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(Theme.textTertiary)
                }
                .pressable(0.9)
                .accessibilityLabel("action.delete")
            }
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md - 2)
    }
}

// MARK: - Comments

/// The conversation on a task.
struct CommentsCard: View {
    let taskId: String
    let comments: [Todo_V1_Comment]
    let viewerId: String
    let isListOwner: Bool
    let canComment: Bool

    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale
    @State private var draft = ""
    @State private var editingId: String?
    @State private var editingBody = ""

    var body: some View {
        ScreenSection("tasks.comments") {
            VStack(spacing: 0) {
                if comments.isEmpty, !canComment {
                    Text("tasks.noComments")
                        .font(.subheadline)
                        .foregroundStyle(Theme.textTertiary)
                        .padding(Theme.Space.lg)
                }

                ForEach(Array(comments.enumerated()), id: \.element.id) { index, comment in
                    if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.md) }
                    commentRow(comment)
                }

                if canComment {
                    if !comments.isEmpty { InsetDivider(leading: 0) }
                    composer
                }
            }
            .cardSurface()
        }
    }

    private func commentRow(_ comment: Todo_V1_Comment) -> some View {
        HStack(alignment: .top, spacing: Theme.Space.md) {
            AvatarView(name: comment.author.displayName, url: comment.author.avatarURL, size: 28)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: Theme.Space.sm) {
                    Text(comment.author.displayName)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.textPrimary)
                    Text(Format.relative(comment.createdAt.date, locale: locale))
                        .font(.caption2)
                        .foregroundStyle(Theme.textTertiary)
                    if comment.edited {
                        Text("tasks.commentEdited")
                            .font(.caption2)
                            .foregroundStyle(Theme.textTertiary)
                    }
                    Spacer(minLength: 0)
                }

                if editingId == comment.id {
                    HStack {
                        TextField("tasks.commentPlaceholder", text: $editingBody, axis: .vertical)
                            .font(.subheadline)
                            .lineLimit(1...6)
                        Button("action.save") {
                            let trimmed = editingBody.trimmingCharacters(in: .whitespacesAndNewlines)
                            editingId = nil
                            guard !trimmed.isEmpty else { return }
                            Task { await actions.editComment(id: comment.id, body: trimmed) }
                        }
                        .font(.caption.weight(.semibold))
                        .pressable()
                    }
                } else {
                    Text(comment.body)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }

            // The author may edit; the author or the list's owner may delete. Same
            // rule as the server, so the menu never offers something that will fail.
            if comment.author.id == viewerId || isListOwner {
                Menu {
                    if comment.author.id == viewerId {
                        Button {
                            editingBody = comment.body
                            editingId = comment.id
                        } label: {
                            Label("action.edit", systemImage: "pencil")
                        }
                    }
                    Button(role: .destructive) {
                        Task { await actions.deleteComment(id: comment.id) }
                    } label: {
                        Label("action.delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis")
                        .font(.caption)
                        .foregroundStyle(Theme.textTertiary)
                        .frame(width: 24, height: 24)
                        .contentShape(Rectangle())
                }
                .accessibilityLabel("action.more")
            }
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: Theme.Space.sm) {
            TextField("tasks.commentPlaceholder", text: $draft, axis: .vertical)
                .font(.subheadline)
                .lineLimit(1...5)
                .padding(.horizontal, Theme.Space.md)
                .padding(.vertical, Theme.Space.sm)
                .background(Theme.surfaceInset, in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))

            Button {
                let trimmed = draft.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else { return }
                draft = ""
                Task { await actions.comment(taskId: taskId, body: trimmed) }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 26))
                    // Lights up only with something to send — the affordance says
                    // whether the tap will do anything before it is made.
                    .foregroundStyle(canSend ? Theme.accent : Theme.textTertiary)
            }
            .pressable(0.88)
            .disabled(!canSend)
            .accessibilityLabel("tasks.postComment")
        }
        .padding(Theme.Space.md)
    }

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

// MARK: - Model

@MainActor
@Observable
final class TaskDetailModel {
    private let backend: TodoBackend
    private let taskId: String

    private(set) var taskState: LoadState<Todo_V1_Task> = .loading
    private(set) var list: Todo_V1_TodoList?
    private(set) var comments: [Todo_V1_Comment] = []
    private(set) var activity: [Todo_V1_Activity] = []
    private(set) var writableLists: [Todo_V1_TodoList] = []

    var task: Todo_V1_Task? { taskState.value }

    /// Permissions come from the *list*, not the task — the task carries only a
    /// reference, so the full list is fetched for `viewer_role`.
    var canWrite: Bool { list?.viewerRole.canWrite ?? false }
    var canComment: Bool { list?.viewerRole.canComment ?? false }

    var assignableMembers: [Todo_V1_ListMember] {
        (list?.members ?? []).filter { $0.role.canWrite }
    }

    var otherWritableLists: [Todo_V1_TodoList] {
        writableLists.filter { $0.id != list?.id }
    }

    var composerLists: [Todo_V1_TodoList] {
        guard let list else { return writableLists }
        return [list] + writableLists.filter { $0.id != list.id }
    }

    init(backend: TodoBackend, taskId: String) {
        self.backend = backend
        self.taskId = taskId
    }

    func load() async {
        let request = Todo_V1_GetTaskRequest.with { $0.id = taskId }
        let result = unwrap(await backend.tasks.getTask(request: request)) { $0.hasTask ? $0.task : nil }
        taskState = result.loadState

        guard case let .success(task) = result else { return }

        // The task's own screen needs three more reads; they are independent of each
        // other, so they go out together.
        async let listResult = fetchList(task.list.id)
        async let commentsResult = fetchComments()
        async let activityResult = fetchActivity()
        async let listsResult = fetchWritableLists()
        let (loadedList, loadedComments, loadedActivity, loadedLists) =
            await (listResult, commentsResult, activityResult, listsResult)

        list = loadedList
        comments = loadedComments
        activity = loadedActivity
        writableLists = loadedLists
    }

    private func fetchList(_ id: String) async -> Todo_V1_TodoList? {
        let request = Todo_V1_GetListRequest.with { $0.id = id }
        return unwrap(await backend.lists.getList(request: request)) { $0.hasList ? $0.list : nil }.value
    }

    private func fetchComments() async -> [Todo_V1_Comment] {
        let request = Todo_V1_ListCommentsRequest.with {
            $0.taskID = taskId
            $0.page = .with { $0.limit = 50 }
        }
        return unwrap(await backend.tasks.listComments(request: request)) { $0.comments }.value ?? []
    }

    private func fetchActivity() async -> [Todo_V1_Activity] {
        let request = Todo_V1_ListActivityRequest.with {
            $0.taskID = taskId
            $0.page = .with { $0.limit = 15 }
        }
        return unwrap(await backend.tasks.listActivity(request: request)) { $0.activities }.value ?? []
    }

    private func fetchWritableLists() async -> [Todo_V1_TodoList] {
        let request = Todo_V1_ListListsRequest.with { $0.page = .with { $0.limit = 60 } }
        let result = unwrap(await backend.lists.listLists(request: request)) { $0.lists }
        return (result.value ?? []).filter { $0.viewerRole.canWrite && !$0.archived }
    }
}
