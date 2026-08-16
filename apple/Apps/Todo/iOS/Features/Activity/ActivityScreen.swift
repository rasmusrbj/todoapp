import Observation
import SwiftUI

/// What has happened, newest first, across every list the account can reach.
struct ActivityScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions

    @State private var model: ActivityModel?

    var body: some View {
        NavigationStack {
            ScreenScaffold(refresh: { await model?.load() }) {
                VStack(alignment: .leading, spacing: Theme.Space.lg) {
                    if let model {
                        if !model.lists.isEmpty {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: Theme.Space.sm) {
                                    FilterChip(title: "filter.all", isOn: model.listId == nil) {
                                        Task { await model.filter(listId: nil) }
                                    }
                                    ForEach(model.lists) { list in
                                        FilterChip(
                                            title: LocalizedStringKey(list.name),
                                            isOn: model.listId == list.id,
                                            tint: list.color.tint
                                        ) { Task { await model.filter(listId: list.id) } }
                                    }
                                }
                            }
                            .scrollClipDisabled()
                        }

                        StateView(
                            state: model.state,
                            emptySymbol: "clock.arrow.circlepath",
                            emptyTitle: "activity.emptyTitle",
                            emptyMessage: "activity.emptyBody",
                            skeletonRows: 6,
                            retry: { await model.load() }
                        ) { entries in
                            VStack(spacing: 0) {
                                ForEach(Array(entries.enumerated()), id: \.element.id) { index, entry in
                                    if index > 0 {
                                        InsetDivider(leading: Theme.Space.xxl + Theme.Space.lg)
                                    }
                                    ActivityLink(activity: entry, showsList: model.listId == nil)
                                }
                            }
                            .cardSurface()
                        }

                        if model.hasMore {
                            Button {
                                Task { await model.loadMore() }
                            } label: {
                                if model.isLoadingMore {
                                    ProgressView().controlSize(.small)
                                } else {
                                    Text("action.loadMore").font(.subheadline.weight(.semibold))
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
            .navigationTitle("nav.activity")
            // Locale-independent handle for the UI tests: the visible title is
            // translated, and the app follows the *account's* language, so
            // asserting on "Today" fails for a Danish account.
            .accessibilityIdentifier("screen.activity")
            .todoDestinations()
            .toolbar { AccountToolbarItem() }
        }
        .task {
            if model == nil { model = ActivityModel(backend: session.backend) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
    }
}

/// An activity row that navigates to whatever it is about, when that still exists.
///
/// A deleted task keeps its entry in the feed — that is the point of an audit trail —
/// but the row must not offer a link to a screen that will only report "not found".
private struct ActivityLink: View {
    let activity: Todo_V1_Activity
    let showsList: Bool

    var body: some View {
        if activity.action == .deleted {
            ActivityRow(activity: activity, showsList: showsList)
        } else if let route {
            NavigationLink(value: route) {
                ActivityRow(activity: activity, showsList: showsList)
            }
            .buttonStyle(RowButtonStyle())
        } else {
            ActivityRow(activity: activity, showsList: showsList)
        }
    }

    private var route: TodoRoute? {
        switch activity.targetType {
        case .task: .task(activity.targetID)
        case .list: .list(activity.targetID)
        // A comment or a membership lives inside something else, so link to the list
        // the entry is scoped to rather than to an id with no screen of its own.
        case .comment, .membership: activity.hasList ? .list(activity.list.id) : nil
        case .unspecified, .UNRECOGNIZED: nil
        }
    }
}

// MARK: - Model

@MainActor
@Observable
final class ActivityModel {
    private let backend: TodoBackend

    private(set) var state: LoadState<[Todo_V1_Activity]> = .loading
    private(set) var lists: [Todo_V1_TodoList] = []
    private(set) var listId: String?
    private(set) var hasMore = false
    private(set) var isLoadingMore = false

    private var cursor = ""
    private var loaded: [Todo_V1_Activity] = []

    init(backend: TodoBackend) {
        self.backend = backend
    }

    func filter(listId: String?) async {
        self.listId = listId
        await load()
    }

    func load() async {
        cursor = ""
        loaded = []
        switch await fetch(cursor: "") {
        case let .success(message):
            loaded = message.activities
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
            loaded.append(contentsOf: message.activities)
            cursor = message.page.nextCursor
            hasMore = message.page.hasMore_p
            state = loaded.isEmpty ? .empty : .loaded(loaded)
        }
    }

    private func fetch(cursor: String) async -> Result<Todo_V1_ListActivityResponse, AppFailure> {
        let request = Todo_V1_ListActivityRequest.with {
            $0.page = .with {
                $0.limit = 30
                $0.cursor = cursor
            }
            if let listId { $0.listID = listId }
        }
        return unwrap(await backend.tasks.listActivity(request: request)) { $0 }
    }

    private func loadLists() async {
        guard lists.isEmpty else { return }
        let request = Todo_V1_ListListsRequest.with { $0.page = .with { $0.limit = 60 } }
        lists = unwrap(await backend.lists.listLists(request: request)) { $0.lists }.value ?? []
    }
}
