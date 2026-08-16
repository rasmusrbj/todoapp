import Observation
import SwiftUI

/// The board of lists.
///
/// A grid whose column count follows the available width — `.adaptive` rather than
/// a size-class branch, so an iPad in portrait, an iPad in landscape and a split
/// view each get the right number of columns instead of three hardcoded cases. The
/// cards keep their size; the grid gains columns.
struct ListsScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: ListsModel?
    @State private var editing: ListEditorRequest?
    @State private var reordering = false

    var body: some View {
        NavigationStack {
            ScreenScaffold(refresh: { await model?.load() }) {
                VStack(alignment: .leading, spacing: Theme.Space.lg) {
                    if let model {
                        controls(model)

                        if reordering, let lists = model.state.value {
                            ListReorderPanel(lists: lists) { reordering = false }
                        }

                        StateView(
                            state: model.state,
                            emptySymbol: "square.stack.3d.up",
                            emptyTitle: "lists.emptyTitle",
                            emptyMessage: "lists.emptyBody",
                            emptyActionTitle: "lists.newList",
                            emptyAction: { editing = .create },
                            skeletonRows: 4,
                            retry: { await model.load() }
                        ) { lists in
                            LazyVGrid(
                                columns: [GridItem(.adaptive(minimum: 260), spacing: Theme.Space.md)],
                                spacing: Theme.Space.md
                            ) {
                                ForEach(lists, id: \.id) { list in
                                    NavigationLink(value: TodoRoute.list(list.id)) {
                                        ListCard(list: list)
                                    }
                                    .pressable(0.98)
                                    .contextMenu {
                                        ListContextMenu(list: list) { editing = .edit(list) }
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(.top, Theme.Space.sm)
            }
            .navigationTitle("nav.lists")
            // Locale-independent handle for the UI tests: the visible title is
            // translated, and the app follows the *account's* language, so
            // asserting on "Today" fails for a Danish account.
            .accessibilityIdentifier("screen.lists")
            .todoDestinations()
            .toolbar {
                AccountToolbarItem()
                ToolbarItem(placement: .topBarTrailing) {
                    Button { editing = .create } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("lists.newList")
                }
            }
        }
        .task {
            if model == nil { model = ListsModel(backend: session.backend) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(item: $editing) { request in
            ListEditorSheet(request: request)
        }
    }

    @ViewBuilder
    private func controls(_ model: ListsModel) -> some View {
        HStack(spacing: Theme.Space.sm) {
            FilterChip(title: "lists.showArchived", isOn: model.includeArchived) {
                Task { await model.toggleArchived() }
            }
            Spacer(minLength: 0)
            if let lists = model.state.value, lists.count > 1 {
                Button {
                    withAnimation(.snappy(duration: 0.2)) { reordering.toggle() }
                } label: {
                    Label("lists.reorder", systemImage: "arrow.up.arrow.down")
                        .font(.subheadline.weight(.medium))
                        .labelStyle(.iconOnly)
                        .frame(width: 34, height: 34)
                        .background(reordering ? Theme.accent : Theme.surface, in: Circle())
                        .foregroundStyle(reordering ? Theme.onAccent : Theme.textSecondary)
                        .overlay(reordering ? nil : Circle().stroke(Theme.border, lineWidth: 1))
                }
                .pressable(0.92)
                .accessibilityLabel("lists.reorder")
            }
        }
    }
}

/// The per-list actions, shared by the card's context menu and the detail screen's
/// toolbar menu so the two cannot offer different things.
struct ListContextMenu: View {
    let list: Todo_V1_TodoList
    let onEdit: () -> Void

    @Environment(Actions.self) private var actions
    @State private var confirmingDelete = false

    var body: some View {
        if list.viewerRole.isOwner {
            Button {
                onEdit()
            } label: {
                Label("action.edit", systemImage: "pencil")
            }
        }

        Button {
            Task { await actions.setListArchived(id: list.id, archived: !list.archived) }
        } label: {
            Label(
                list.archived ? "lists.restore" : "lists.archive",
                systemImage: list.archived ? "arrow.uturn.backward" : "archivebox"
            )
        }

        if list.viewerRole.isOwner {
            NavigationLink(value: TodoRoute.listMembers(list.id)) {
                Label("lists.members", systemImage: "person.2")
            }
        }
        NavigationLink(value: TodoRoute.listLabels(list.id)) {
            Label("lists.labels", systemImage: "tag")
        }

        if list.viewerRole.isOwner {
            Divider()
            // A destructive, irreversible action, so it confirms. `role: .destructive`
            // is what makes the system render it red and read it out as destructive.
            Button(role: .destructive) {
                Task { await actions.deleteList(id: list.id) }
            } label: {
                Label("action.delete", systemImage: "trash")
            }
        }
    }
}

/// Reordering the board.
///
/// Move-up/move-down buttons rather than drag-and-drop: both are operable by
/// keyboard and VoiceOver, neither needs a long-press on a touch screen, and the
/// whole rearrangement is saved as one call rather than one per step.
struct ListReorderPanel: View {
    let lists: [Todo_V1_TodoList]
    let onDone: () -> Void

    @Environment(Actions.self) private var actions
    @State private var order: [Todo_V1_TodoList] = []

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(order.enumerated()), id: \.element.id) { index, list in
                if index > 0 { InsetDivider() }
                HStack(spacing: Theme.Space.sm) {
                    ColorDot(color: list.color.tint)
                    Text(list.name)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textPrimary)
                        .lineLimit(1)
                    Spacer(minLength: Theme.Space.sm)
                    Button {
                        move(from: index, by: -1)
                    } label: {
                        Image(systemName: "arrow.up")
                    }
                    .pressable(0.9)
                    .disabled(index == 0)
                    .accessibilityLabel("lists.moveUp")

                    Button {
                        move(from: index, by: 1)
                    } label: {
                        Image(systemName: "arrow.down")
                    }
                    .pressable(0.9)
                    .disabled(index == order.count - 1)
                    .accessibilityLabel("lists.moveDown")
                }
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
                .padding(.horizontal, Theme.Space.lg)
                .padding(.vertical, Theme.Space.md)
            }

            InsetDivider(leading: 0)
            HStack {
                Button("action.cancel", action: onDone)
                    .foregroundStyle(Theme.textSecondary)
                Spacer()
                Button("action.save") {
                    Task {
                        await actions.reorderLists(ids: order.map(\.id))
                        onDone()
                    }
                }
                .fontWeight(.semibold)
            }
            .font(.subheadline)
            .padding(Theme.Space.lg)
        }
        .cardSurface()
        // Start from what is on screen now, not a snapshot from when the panel was
        // last opened.
        .onAppear { order = lists }
        .onChange(of: lists.map(\.id)) { _, _ in order = lists }
    }

    private func move(from index: Int, by delta: Int) {
        let target = index + delta
        guard order.indices.contains(target) else { return }
        withAnimation(.snappy(duration: 0.2)) {
            order.swapAt(index, target)
        }
        Haptics.impact(.light)
    }
}

// MARK: - Model

@MainActor
@Observable
final class ListsModel {
    private let backend: TodoBackend

    private(set) var state: LoadState<[Todo_V1_TodoList]> = .loading
    private(set) var includeArchived = false

    init(backend: TodoBackend) {
        self.backend = backend
    }

    func toggleArchived() async {
        includeArchived.toggle()
        await load()
    }

    func load() async {
        let request = Todo_V1_ListListsRequest.with {
            $0.page = .with { $0.limit = 60 }
            $0.includeArchived = includeArchived
            $0.sortField = .position
            $0.sortDirection = .asc
        }
        state = unwrap(await backend.lists.listLists(request: request)) { $0.lists }.listState
    }
}
