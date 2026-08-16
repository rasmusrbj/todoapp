import Observation
import SwiftUI

/// Every task the account can reach, filtered and sorted.
///
/// The counterpart to the per-list view: this is where "everything assigned to me
/// that is overdue" lives, across lists.
struct TasksScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: TasksModel?
    @State private var composing: ComposerRequest?
    @State private var showingFilters = false

    var body: some View {
        NavigationStack {
            ScreenScaffold(refresh: { await model?.load() }) {
                VStack(alignment: .leading, spacing: Theme.Space.lg) {
                    if let model {
                        quickFilters(model)

                        if model.hasActiveFilters {
                            ActiveFilterSummary(model: model)
                        }

                        StateView(
                            state: model.state,
                            emptySymbol: "checklist",
                            emptyTitle: model.hasActiveFilters ? "tasks.noMatchesTitle" : "tasks.emptyTitle",
                            emptyMessage: model.hasActiveFilters ? "tasks.noMatchesBody" : "tasks.emptyBody",
                            emptyActionTitle: model.hasActiveFilters ? "tasks.clearFilters" : nil,
                            emptyAction: model.hasActiveFilters ? { Task { await model.clearFilters() } } : nil,
                            skeletonRows: 6,
                            retry: { await model.load() }
                        ) { tasks in
                            TaskCardGroup(tasks: tasks) { task in
                                TaskLink(task: task, canEdit: true, showsList: true)
                                    .swipeActions(edge: .trailing) {
                                        Button(role: .destructive) {
                                            Task { await actions.delete(taskId: task.id) }
                                        } label: {
                                            Label("action.delete", systemImage: "trash")
                                        }
                                    }
                            }
                        }

                        if model.hasMore {
                            Button {
                                Task { await model.loadMore() }
                            } label: {
                                if model.isLoadingMore {
                                    ProgressView().controlSize(.small)
                                } else {
                                    Text("action.loadMore")
                                        .font(.subheadline.weight(.semibold))
                                }
                            }
                            .pressable()
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Space.md)
                        }
                    }
                }
                .padding(.top, Theme.Space.sm)
            }
            .navigationTitle("nav.tasks")
            // Locale-independent handle for the UI tests: the visible title is
            // translated, and the app follows the *account's* language, so
            // asserting on "Today" fails for a Danish account.
            .accessibilityIdentifier("screen.tasks")
            .todoDestinations()
            .toolbar {
                AccountToolbarItem()
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingFilters = true } label: {
                        Image(
                            systemName: model?.hasActiveFilters == true
                                ? "line.3.horizontal.decrease.circle.fill"
                                : "line.3.horizontal.decrease.circle"
                        )
                    }
                    .accessibilityLabel("tasks.filters")
                }
                if let lists = model?.writableLists, !lists.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            composing = .create(listId: lists[0].id)
                        } label: {
                            Image(systemName: "plus")
                        }
                        .accessibilityLabel("tasks.newTask")
                    }
                }
            }
        }
        .task {
            if model == nil { model = TasksModel(backend: session.backend) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(isPresented: $showingFilters) {
            if let model {
                TaskFilterSheet(model: model)
            }
        }
        .sheet(item: $composing) { request in
            TaskComposerSheet(request: request, lists: model?.writableLists ?? [])
        }
    }

    /// The three filters worth one tap, inline. Everything else is in the sheet.
    private func quickFilters(_ model: TasksModel) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Space.sm) {
                FilterChip(title: "filter.open", isOn: model.openOnly) {
                    Task { await model.toggleOpenOnly() }
                }
                FilterChip(title: "filter.mine", isOn: model.mineOnly) {
                    Task { await model.toggleMine(viewerId: session.viewer?.id ?? "") }
                }
                FilterChip(title: "filter.overdue", isOn: model.overdueOnly) {
                    Task { await model.toggleOverdue() }
                }
                FilterChip(title: "filter.unassigned", isOn: model.unassignedOnly) {
                    Task { await model.toggleUnassigned() }
                }
            }
        }
        .scrollClipDisabled()
    }
}

/// What is currently narrowing the list, and a way out of it.
///
/// Filters hidden behind a sheet are how someone concludes the app has lost their
/// tasks; this makes the state visible on the screen it affects.
private struct ActiveFilterSummary: View {
    let model: TasksModel

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            Image(systemName: "line.3.horizontal.decrease")
                .font(.caption2.weight(.semibold))
            Text("tasks.filterCount \(model.activeFilterCount)")
                .font(.caption.weight(.medium))
                .monospacedDigit()
            Spacer(minLength: 0)
            Button("tasks.clearFilters") {
                Task { await model.clearFilters() }
            }
            .font(.caption.weight(.semibold))
            .pressable()
        }
        .foregroundStyle(Theme.textSecondary)
        .padding(.horizontal, Theme.Space.md)
        .padding(.vertical, Theme.Space.sm)
        .background(
            Theme.surfaceInset,
            in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
        )
    }
}

/// The full filter and sort surface.
struct TaskFilterSheet: View {
    let model: TasksModel

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    ForEach(Todo_V1_TaskStatus.selectable, id: \.self) { status in
                        Toggle(isOn: Binding(
                            get: { model.statuses.contains(status) },
                            set: { _ in Task { await model.toggleStatus(status) } }
                        )) {
                            Label {
                                Text(status.displayName)
                            } icon: {
                                Image(systemName: status.symbol).foregroundStyle(status.tint)
                            }
                        }
                    }
                } header: {
                    Text("tasks.status")
                }

                Section {
                    ForEach(Todo_V1_TaskPriority.selectable, id: \.self) { priority in
                        Toggle(isOn: Binding(
                            get: { model.priorities.contains(priority) },
                            set: { _ in Task { await model.togglePriority(priority) } }
                        )) {
                            Text(priority.displayName)
                        }
                    }
                } header: {
                    Text("tasks.priority")
                }

                if !model.allLists.isEmpty {
                    Section {
                        ForEach(model.allLists) { list in
                            Toggle(isOn: Binding(
                                get: { model.listIds.contains(list.id) },
                                set: { _ in Task { await model.toggleList(list.id) } }
                            )) {
                                HStack(spacing: Theme.Space.sm) {
                                    ColorDot(color: list.color.tint)
                                    Text(list.name)
                                }
                            }
                        }
                    } header: {
                        Text("nav.lists")
                    }
                }

                Section {
                    Picker("tasks.sortBy", selection: Binding(
                        get: { model.sortField },
                        set: { field in Task { await model.sort(by: field) } }
                    )) {
                        ForEach(TasksModel.SortOption.allCases, id: \.self) { option in
                            Text(option.displayName).tag(option)
                        }
                    }
                    Toggle(isOn: Binding(
                        get: { model.descending },
                        set: { _ in Task { await model.toggleDirection() } }
                    )) {
                        Text("tasks.sortDescending")
                    }
                } header: {
                    Text("tasks.sorting")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle("tasks.filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("tasks.clearFilters") {
                        Task { await model.clearFilters() }
                    }
                    .disabled(!model.hasActiveFilters)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("action.done") { dismiss() }
                        .fontWeight(.semibold)
                }
            }
        }
    }
}

// MARK: - Model

@MainActor
@Observable
final class TasksModel {
    /// The sortable columns, as the UI offers them.
    ///
    /// A separate enum from `Todo_V1_TaskSortField` because that one includes
    /// `UNSPECIFIED`, and a picker with an "unspecified" row is not a choice anyone
    /// wants to make.
    enum SortOption: CaseIterable, Hashable {
        case dueDate, priority, created, updated, title, manual

        var field: Todo_V1_TaskSortField {
            switch self {
            case .dueDate: .dueAt
            case .priority: .priority
            case .created: .createdAt
            case .updated: .updatedAt
            case .title: .title
            case .manual: .position
            }
        }

        var displayName: LocalizedStringKey {
            switch self {
            case .dueDate: "sort.dueDate"
            case .priority: "sort.priority"
            case .created: "sort.created"
            case .updated: "sort.updated"
            case .title: "sort.title"
            case .manual: "sort.manual"
            }
        }
    }

    private let backend: TodoBackend

    private(set) var state: LoadState<[Todo_V1_Task]> = .loading
    private(set) var allLists: [Todo_V1_TodoList] = []
    private(set) var isLoadingMore = false
    private(set) var hasMore = false

    // Filters.
    private(set) var statuses: Set<Todo_V1_TaskStatus> = []
    private(set) var priorities: Set<Todo_V1_TaskPriority> = []
    private(set) var listIds: Set<String> = []
    private(set) var assigneeIds: Set<String> = []
    private(set) var unassignedOnly = false
    private(set) var overdueOnly = false
    private(set) var openOnly = true
    private(set) var sortField: SortOption = .dueDate
    private(set) var descending = false

    private var cursor = ""
    private var loaded: [Todo_V1_Task] = []

    var writableLists: [Todo_V1_TodoList] {
        allLists.filter { $0.viewerRole.canWrite && !$0.archived }
    }

    var mineOnly: Bool { !assigneeIds.isEmpty }

    var activeFilterCount: Int {
        var count = 0
        if !statuses.isEmpty { count += 1 }
        if !priorities.isEmpty { count += 1 }
        if !listIds.isEmpty { count += 1 }
        if !assigneeIds.isEmpty { count += 1 }
        if unassignedOnly { count += 1 }
        if overdueOnly { count += 1 }
        return count
    }

    /// `openOnly` is the default, so it does not count as a filter someone has to be
    /// told about — otherwise the summary bar would be permanently on screen.
    var hasActiveFilters: Bool { activeFilterCount > 0 }

    init(backend: TodoBackend) {
        self.backend = backend
    }

    // MARK: Filter mutations

    func toggleOpenOnly() async {
        openOnly.toggle()
        if openOnly { statuses = [] }
        await load()
    }

    func toggleMine(viewerId: String) async {
        guard !viewerId.isEmpty else { return }
        if assigneeIds.contains(viewerId) {
            assigneeIds.remove(viewerId)
        } else {
            assigneeIds.insert(viewerId)
            // "Assigned to me" and "unassigned" are contradictory; asking for both
            // returns nothing, which reads as a bug.
            unassignedOnly = false
        }
        await load()
    }

    func toggleUnassigned() async {
        unassignedOnly.toggle()
        if unassignedOnly { assigneeIds = [] }
        await load()
    }

    func toggleOverdue() async {
        overdueOnly.toggle()
        await load()
    }

    func toggleStatus(_ status: Todo_V1_TaskStatus) async {
        if statuses.contains(status) {
            statuses.remove(status)
        } else {
            statuses.insert(status)
            // An explicit status choice supersedes the "open" shorthand.
            openOnly = false
        }
        await load()
    }

    func togglePriority(_ priority: Todo_V1_TaskPriority) async {
        if priorities.contains(priority) {
            priorities.remove(priority)
        } else {
            priorities.insert(priority)
        }
        await load()
    }

    func toggleList(_ id: String) async {
        if listIds.contains(id) { listIds.remove(id) } else { listIds.insert(id) }
        await load()
    }

    func sort(by option: SortOption) async {
        sortField = option
        await load()
    }

    func toggleDirection() async {
        descending.toggle()
        await load()
    }

    func clearFilters() async {
        statuses = []
        priorities = []
        listIds = []
        assigneeIds = []
        unassignedOnly = false
        overdueOnly = false
        openOnly = true
        await load()
    }

    // MARK: Loading

    func load() async {
        cursor = ""
        loaded = []
        let result = await fetch(cursor: "")
        switch result {
        case let .success(message):
            loaded = message.tasks
            cursor = message.page.nextCursor
            hasMore = message.page.hasMore_p
            state = loaded.isEmpty ? .empty : .loaded(loaded)
        case let .failure(failure):
            state = .failed(failure)
        }
        await loadLists()
    }

    func loadMore() async {
        guard hasMore, !cursor.isEmpty, !isLoadingMore else { return }
        isLoadingMore = true
        defer { isLoadingMore = false }
        if case let .success(message) = await fetch(cursor: cursor) {
            loaded.append(contentsOf: message.tasks)
            cursor = message.page.nextCursor
            hasMore = message.page.hasMore_p
            state = loaded.isEmpty ? .empty : .loaded(loaded)
        }
    }

    private func fetch(cursor: String) async -> Result<Todo_V1_ListTasksResponse, AppFailure> {
        let request = Todo_V1_ListTasksRequest.with {
            $0.page = .with {
                $0.limit = 40
                $0.cursor = cursor
            }
            $0.statuses = statuses.isEmpty
                ? (openOnly ? Todo_V1_TaskStatus.open : [])
                : Array(statuses)
            $0.priorities = Array(priorities)
            $0.listIds = Array(listIds)
            $0.assigneeIds = Array(assigneeIds)
            $0.unassignedOnly = unassignedOnly
            $0.overdueOnly = overdueOnly
            $0.sortField = sortField.field
            $0.sortDirection = descending ? .desc : .asc
        }
        return unwrap(await backend.tasks.listTasks(request: request)) { $0 }
    }

    private func loadLists() async {
        guard allLists.isEmpty else { return }
        let request = Todo_V1_ListListsRequest.with { $0.page = .with { $0.limit = 60 } }
        allLists = unwrap(await backend.lists.listLists(request: request)) { $0.lists }.value ?? []
    }
}
