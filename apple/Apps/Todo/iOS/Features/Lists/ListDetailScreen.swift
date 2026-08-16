import Observation
import SwiftUI

/// One list: its header, its tasks, and everything you can do to it.
struct ListDetailScreen: View {
    let listId: String

    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: ListDetailModel?
    @State private var composing: ComposerRequest?
    @State private var editing: ListEditorRequest?
    @State private var selection: Set<String> = []

    private var isSelecting: Bool { !selection.isEmpty }

    var body: some View {
        ScreenScaffold(refresh: { await model?.load() }) {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let model, let list = model.list {
                    header(list)
                    statusFilter(model)
                    tasks(model, list: list)
                } else if let model, let failure = model.listState.failure {
                    StateMessage(
                        symbol: "exclamationmark.triangle",
                        title: "state.failedTitle",
                        message: LocalizedStringKey(failure.messageKey),
                        actionTitle: "action.retry",
                        action: { Task { await model.load() } }
                    )
                } else {
                    VStack(spacing: Theme.Space.sm) {
                        Skeleton(height: 92, cornerRadius: Theme.Radius.card)
                        Skeleton(height: 200, cornerRadius: Theme.Radius.card)
                    }
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle(model?.list?.name ?? "")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { toolbar }
        .safeAreaInset(edge: .bottom) {
            if isSelecting, let list = model?.list {
                BulkActionBar(
                    selection: $selection,
                    list: list,
                    allLists: model?.writableLists ?? []
                )
            }
        }
        .task {
            if model == nil { model = ListDetailModel(backend: session.backend, listId: listId) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(item: $composing) { request in
            TaskComposerSheet(request: request, lists: model?.composerLists ?? [])
        }
        .sheet(item: $editing) { request in
            ListEditorSheet(request: request)
        }
    }

    // MARK: Pieces

    private func header(_ list: Todo_V1_TodoList) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            HStack(spacing: Theme.Space.sm) {
                ColorDot(color: list.color.tint, size: 10)
                Text(list.name)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Theme.textPrimary)
                Spacer(minLength: Theme.Space.sm)
                VisibilityBadge(visibility: list.visibility)
            }

            if !list.description_p.isEmpty {
                Text(list.description_p)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textSecondary)
            }

            ProgressBar(percent: Int(list.stats.completionPercent), tint: list.color.tint)

            HStack(spacing: Theme.Space.md) {
                Text("lists.progressSummary \(Int(list.stats.completedTaskCount)) \(Int(list.stats.totalTaskCount))")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(Theme.textSecondary)
                    .monospacedDigit()
                if list.stats.overdueTaskCount > 0 {
                    Text("lists.overdueCount \(Int(list.stats.overdueTaskCount))")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.danger)
                        .monospacedDigit()
                }
                Spacer(minLength: 0)
                RoleBadge(role: list.viewerRole)
            }

            if list.stats.memberCount > 1 {
                NavigationLink(value: TodoRoute.listMembers(list.id)) {
                    HStack(spacing: Theme.Space.sm) {
                        MemberStack(members: list.members)
                        Text("lists.memberCount \(Int(list.stats.memberCount))")
                            .font(.caption)
                            .foregroundStyle(Theme.textSecondary)
                        Image(systemName: "chevron.right")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(Theme.textTertiary)
                    }
                }
                .pressable(0.98)
            }
        }
        .padding(Theme.Space.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cardSurface()
    }

    private func statusFilter(_ model: ListDetailModel) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Space.sm) {
                FilterChip(
                    title: "filter.open",
                    count: model.openCount,
                    isOn: model.filter == .open
                ) { Task { await model.apply(.open) } }

                FilterChip(
                    title: "filter.all",
                    count: model.totalCount,
                    isOn: model.filter == .all
                ) { Task { await model.apply(.all) } }

                ForEach(Todo_V1_TaskStatus.selectable, id: \.self) { status in
                    FilterChip(
                        title: status.displayName,
                        count: model.count(for: status),
                        isOn: model.filter == .status(status),
                        tint: status.tint
                    ) { Task { await model.apply(.status(status)) } }
                }
            }
            .padding(.horizontal, 1)
        }
        // The chip row is the one place a horizontal scroller is right: it is a
        // single row of peers, and the first few are always visible.
        .scrollClipDisabled()
    }

    @ViewBuilder
    private func tasks(_ model: ListDetailModel, list: Todo_V1_TodoList) -> some View {
        StateView(
            state: model.tasks,
            emptySymbol: "checklist",
            emptyTitle: model.filter == .open ? "lists.noOpenTasksTitle" : "lists.noTasksTitle",
            emptyMessage: model.filter == .open ? "lists.noOpenTasksBody" : "lists.noTasksBody",
            emptyActionTitle: list.viewerRole.canWrite ? "tasks.newTask" : nil,
            emptyAction: list.viewerRole.canWrite ? { composing = .create(listId: listId) } : nil,
            skeletonRows: 5,
            retry: { await model.load() }
        ) { tasks in
            TaskCardGroup(tasks: tasks) { task in
                if list.viewerRole.canWrite {
                    TaskLink(
                        task: task,
                        canEdit: true,
                        showsList: false
                    )
                    // A selection starts from a long press, so the row keeps its
                    // ordinary tap. `selection` being non-empty is what puts every
                    // other row into select mode.
                    .simultaneousGesture(
                        LongPressGesture().onEnded { _ in
                            Haptics.impact(.medium)
                            selection.insert(task.id)
                        }
                    )
                    .overlay {
                        if isSelecting {
                            SelectionOverlay(
                                isSelected: selection.contains(task.id),
                                task: task,
                                showsList: false
                            ) { toggle(task.id) }
                        }
                    }
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) {
                            Task { await actions.delete(taskId: task.id) }
                        } label: {
                            Label("action.delete", systemImage: "trash")
                        }
                    }
                } else {
                    TaskLink(task: task, canEdit: false, showsList: false)
                }
            }
        }
    }

    @ToolbarContentBuilder
    private var toolbar: some ToolbarContent {
        if let list = model?.list {
            if isSelecting {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("action.done") { selection = [] }
                        .fontWeight(.semibold)
                }
            } else {
                if list.viewerRole.canWrite {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            composing = .create(listId: listId)
                        } label: {
                            Image(systemName: "plus")
                        }
                        .accessibilityLabel("tasks.newTask")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        ListContextMenu(list: list) { editing = .edit(list) }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .accessibilityLabel("action.more")
                }
            }
        }
    }

    private func toggle(_ id: String) {
        if selection.contains(id) {
            selection.remove(id)
        } else {
            selection.insert(id)
        }
    }
}

/// Covers a row while a multi-selection is running, so the row's own tap and its
/// check button cannot fire by accident mid-selection.
struct SelectionOverlay: View {
    let isSelected: Bool
    let task: Todo_V1_Task
    var showsList: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: Theme.Space.sm) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 20, weight: .light))
                    .foregroundStyle(isSelected ? Theme.accent : Theme.textTertiary)
                Text(task.title)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.textPrimary)
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, Theme.Space.lg)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(isSelected ? Theme.accent.opacity(0.06) : Theme.surface)
            .contentShape(Rectangle())
        }
        .pressable(1, haptic: nil)
        .accessibilityLabel(Text(task.title))
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }
}

/// The floating bar that appears with a multi-selection.
struct BulkActionBar: View {
    @Binding var selection: Set<String>
    let list: Todo_V1_TodoList
    let allLists: [Todo_V1_TodoList]

    @Environment(Actions.self) private var actions

    var body: some View {
        HStack(spacing: Theme.Space.md) {
            Text("tasks.selectedCount \(selection.count)")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.textPrimary)
                .monospacedDigit()

            Spacer(minLength: 0)

            Menu {
                Section {
                    ForEach(Todo_V1_TaskStatus.selectable, id: \.self) { status in
                        Button {
                            apply(.status(status))
                        } label: {
                            Label(status.displayName, systemImage: status.symbol)
                        }
                    }
                } header: {
                    Text("tasks.status")
                }

                Section {
                    ForEach(Todo_V1_TaskPriority.selectable, id: \.self) { priority in
                        Button(action: { apply(.priority(priority)) }) {
                            Text(priority.displayName)
                        }
                    }
                } header: {
                    Text("tasks.priority")
                }

                if allLists.count > 1 {
                    Section {
                        ForEach(allLists.filter { $0.id != list.id }, id: \.id) { target in
                            Button(action: { apply(.list(target.id)) }) {
                                Text(target.name)
                            }
                        }
                    } header: {
                        Text("tasks.moveToList")
                    }
                }

                Section {
                    Button(action: { apply(.clearAssignee) }) {
                        Label("tasks.unassigned", systemImage: "person.crop.circle.badge.xmark")
                    }
                }
            } label: {
                Label("tasks.bulkEdit", systemImage: "slider.horizontal.3")
                    .font(.subheadline.weight(.semibold))
            }
            .pressable()

            Button("action.cancel") { selection = [] }
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
                .pressable()
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
        .background(.regularMaterial)
        .overlay(alignment: .top) { Divider().overlay(Theme.border) }
    }

    private func apply(_ change: Actions.BulkChange) {
        let ids = Array(selection)
        Task {
            let updated = await actions.bulkUpdate(taskIds: ids, change: change)
            if updated > 0 {
                Haptics.success()
                selection = []
            }
        }
    }
}

// MARK: - Model

@MainActor
@Observable
final class ListDetailModel {
    /// Which slice of the list is showing.
    enum Filter: Equatable {
        case open
        case all
        case status(Todo_V1_TaskStatus)
    }

    private let backend: TodoBackend
    private let listId: String

    private(set) var listState: LoadState<Todo_V1_TodoList> = .loading
    private(set) var tasks: LoadState<[Todo_V1_Task]> = .loading
    private(set) var filter: Filter = .open
    /// Per-status totals across the whole filtered set, for the chip counts.
    private(set) var statusCounts: [String: Int32] = [:]
    private(set) var totalCount = 0
    private(set) var writableLists: [Todo_V1_TodoList] = []

    var list: Todo_V1_TodoList? { listState.value }

    /// Lists the composer may target: this one plus any other writable list, so a
    /// task can be filed elsewhere without leaving the screen.
    var composerLists: [Todo_V1_TodoList] {
        guard let list else { return writableLists }
        var lists = [list]
        lists.append(contentsOf: writableLists.filter { $0.id != list.id })
        return lists
    }

    init(backend: TodoBackend, listId: String) {
        self.backend = backend
        self.listId = listId
    }

    func apply(_ filter: Filter) async {
        self.filter = filter
        await loadTasks()
    }

    func load() async {
        async let list: Void = loadList()
        async let tasks: Void = loadTasks()
        async let lists: Void = loadWritableLists()
        _ = await (list, tasks, lists)
    }

    func count(for status: Todo_V1_TaskStatus) -> Int? {
        // Keyed by the proto enum *name* on the wire — a proto map cannot be keyed
        // by an enum — so the lookup goes through `protoName`.
        statusCounts[status.protoName].map(Int.init)
    }

    var openCount: Int? {
        let open = Todo_V1_TaskStatus.open.compactMap { count(for: $0) }
        return open.isEmpty ? nil : open.reduce(0, +)
    }

    private func loadList() async {
        let request = Todo_V1_GetListRequest.with { $0.id = listId }
        listState = unwrap(await backend.lists.getList(request: request)) {
            $0.hasList ? $0.list : nil
        }.loadState
    }

    private func loadTasks() async {
        let request = Todo_V1_ListTasksRequest.with {
            $0.page = .with { $0.limit = 100 }
            $0.listIds = [listId]
            switch filter {
            case .open: $0.statuses = Todo_V1_TaskStatus.open
            case .all: break
            case let .status(status): $0.statuses = [status]
            }
            $0.sortField = .position
            $0.sortDirection = .asc
        }
        let result = unwrap(await backend.tasks.listTasks(request: request)) { $0 }
        if case let .success(message) = result {
            statusCounts = message.statusCounts
            totalCount = Int(message.page.totalCount)
        }
        tasks = result.map(\.tasks).listState
    }

    private func loadWritableLists() async {
        let request = Todo_V1_ListListsRequest.with {
            $0.page = .with { $0.limit = 60 }
        }
        let result = unwrap(await backend.lists.listLists(request: request)) { $0.lists }
        writableLists = (result.value ?? []).filter { $0.viewerRole.canWrite && !$0.archived }
    }
}
