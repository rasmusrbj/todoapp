import Observation
import SwiftUI

/// Search across tasks, lists and — for admins — people.
///
/// This is the phone's answer to the web's ⌘K palette. It sits in a `Tab` with the
/// `.search` role, which puts it in the tab bar on iPhone and wires it into the
/// sidebar's search field on iPad — the platform's own idiom in each case.
struct SearchScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions

    @State private var model: SearchModel?
    @State private var query = ""

    var body: some View {
        NavigationStack {
            ScreenScaffold {
                VStack(alignment: .leading, spacing: Theme.Space.lg) {
                    if query.trimmingCharacters(in: .whitespaces).isEmpty {
                        StateMessage(
                            symbol: "magnifyingglass",
                            title: "search.promptTitle",
                            message: "search.promptBody"
                        )
                        .padding(.top, Theme.Space.xxl)
                    } else if let model {
                        if model.isSearching, !model.hasAnyResult {
                            VStack(spacing: Theme.Space.sm) {
                                ForEach(0..<4, id: \.self) { _ in
                                    Skeleton(height: 56, cornerRadius: Theme.Radius.card)
                                }
                            }
                        } else if !model.hasAnyResult {
                            StateMessage(
                                symbol: "questionmark.circle",
                                title: "search.noResultsTitle",
                                message: "search.noResultsBody"
                            )
                            .padding(.top, Theme.Space.xxl)
                        } else {
                            if !model.tasks.isEmpty {
                                ScreenSection("nav.tasks") {
                                    TaskCardGroup(tasks: model.tasks) { task in
                                        TaskLink(task: task)
                                    }
                                }
                            }
                            if !model.lists.isEmpty {
                                ScreenSection("nav.lists") {
                                    VStack(spacing: 0) {
                                        ForEach(Array(model.lists.enumerated()), id: \.element.id) { index, list in
                                            if index > 0 { InsetDivider(leading: Theme.Space.lg) }
                                            NavigationLink(value: TodoRoute.list(list.id)) {
                                                HStack(spacing: Theme.Space.sm) {
                                                    ColorDot(color: list.color.tint)
                                                    Text(list.name)
                                                        .font(.subheadline.weight(.medium))
                                                        .foregroundStyle(Theme.textPrimary)
                                                    Spacer(minLength: 0)
                                                    Text("lists.openCount \(Int(list.stats.openTaskCount))")
                                                        .font(.caption)
                                                        .foregroundStyle(Theme.textTertiary)
                                                        .monospacedDigit()
                                                }
                                                .padding(.horizontal, Theme.Space.lg)
                                                .padding(.vertical, Theme.Space.md)
                                            }
                                            .buttonStyle(RowButtonStyle())
                                        }
                                    }
                                    .cardSurface()
                                }
                            }
                            if !model.people.isEmpty {
                                ScreenSection("search.people") {
                                    VStack(spacing: 0) {
                                        ForEach(Array(model.people.enumerated()), id: \.element.id) { index, person in
                                            if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.md) }
                                            HStack(spacing: Theme.Space.md) {
                                                AvatarView(name: person.displayName, url: person.avatarURL, size: 32)
                                                VStack(alignment: .leading, spacing: 1) {
                                                    Text(person.displayName)
                                                        .font(.subheadline.weight(.medium))
                                                        .foregroundStyle(Theme.textPrimary)
                                                    Text(person.email)
                                                        .font(.caption)
                                                        .foregroundStyle(Theme.textSecondary)
                                                }
                                                Spacer(minLength: 0)
                                            }
                                            .padding(.horizontal, Theme.Space.lg)
                                            .padding(.vertical, Theme.Space.md)
                                        }
                                    }
                                    .cardSurface()
                                }
                            }
                        }
                    }
                }
                .padding(.top, Theme.Space.sm)
            }
            .navigationTitle("nav.search")
            // Locale-independent handle for the UI tests: the visible title is
            // translated, and the app follows the *account's* language, so
            // asserting on "Today" fails for a Danish account.
            .accessibilityIdentifier("screen.search")
            .todoDestinations()
        }
        .searchable(text: $query, prompt: Text("search.prompt"))
        .task {
            if model == nil { model = SearchModel(backend: session.backend) }
        }
        // Debounced, and cancellation-aware: `.task(id:)` cancels the previous task
        // when the query changes, so a slow reply for "ta" can no longer land after
        // the results for "task" and overwrite them.
        .task(id: query) {
            let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else {
                model?.clear()
                return
            }
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await model?.search(trimmed, includePeople: session.viewer?.role == .admin)
        }
    }
}

// MARK: - Model

@MainActor
@Observable
final class SearchModel {
    private let backend: TodoBackend

    private(set) var tasks: [Todo_V1_Task] = []
    private(set) var lists: [Todo_V1_TodoList] = []
    private(set) var people: [Todo_V1_UserRef] = []
    private(set) var isSearching = false

    var hasAnyResult: Bool { !tasks.isEmpty || !lists.isEmpty || !people.isEmpty }

    init(backend: TodoBackend) {
        self.backend = backend
    }

    func clear() {
        tasks = []
        lists = []
        people = []
        isSearching = false
    }

    func search(_ query: String, includePeople: Bool) async {
        isSearching = true
        defer { isSearching = false }

        // Three independent queries in parallel. `SearchUsers` is admin-only, so it
        // is skipped rather than sent and refused — a `PERMISSION_DENIED` in the log
        // on every keystroke is noise that hides real failures.
        async let foundTasks = searchTasks(query)
        async let foundLists = searchLists(query)
        async let foundPeople = includePeople ? searchPeople(query) : []

        let (t, l, p) = await (foundTasks, foundLists, foundPeople)
        // Nothing is written until every leg is in, so the sections appear together
        // rather than popping in one at a time.
        tasks = t
        lists = l
        people = p
    }

    private func searchTasks(_ query: String) async -> [Todo_V1_Task] {
        let request = Todo_V1_ListTasksRequest.with {
            $0.page = .with { $0.limit = 20 }
            $0.query = query
            $0.sortField = .updatedAt
            $0.sortDirection = .desc
        }
        return unwrap(await backend.tasks.listTasks(request: request)) { $0.tasks }.value ?? []
    }

    private func searchLists(_ query: String) async -> [Todo_V1_TodoList] {
        let request = Todo_V1_ListListsRequest.with {
            $0.page = .with { $0.limit = 10 }
            $0.query = query
            $0.includeArchived = true
        }
        return unwrap(await backend.lists.listLists(request: request)) { $0.lists }.value ?? []
    }

    private func searchPeople(_ query: String) async -> [Todo_V1_UserRef] {
        let request = Todo_V1_SearchUsersRequest.with {
            $0.query = query
            $0.limit = 8
        }
        return unwrap(await backend.users.searchUsers(request: request)) { $0.users }.value ?? []
    }
}
