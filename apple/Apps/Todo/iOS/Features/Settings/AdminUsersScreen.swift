import Observation
import SwiftUI

/// The admin user list: search, role, status, deletion.
///
/// Reachable only when the account's role is `admin`, and the server checks again on
/// every call (`ADMIN_REQUIRED`) — the hidden menu item is a convenience, not the
/// control.
struct AdminUsersScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: AdminUsersModel?
    @State private var query = ""
    @State private var suspending: Todo_V1_User?
    @State private var confirmingDelete: Todo_V1_User?

    var body: some View {
        ScreenScaffold(refresh: { await model?.load() }) {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let model {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: Theme.Space.sm) {
                            FilterChip(title: "filter.all", isOn: model.statusFilter == nil) {
                                Task { await model.filter(by: nil) }
                            }
                            ForEach(Todo_V1_UserStatus.selectable, id: \.self) { status in
                                FilterChip(
                                    title: status.displayName,
                                    isOn: model.statusFilter == status,
                                    tint: status.tint
                                ) { Task { await model.filter(by: status) } }
                            }
                        }
                    }
                    .scrollClipDisabled()

                    StateView(
                        state: model.state,
                        emptySymbol: "person.3",
                        emptyTitle: "admin.noUsersTitle",
                        skeletonRows: 6,
                        retry: { await model.load() }
                    ) { users in
                        VStack(spacing: 0) {
                            ForEach(Array(users.enumerated()), id: \.element.id) { index, user in
                                if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.lg) }
                                AdminUserRow(
                                    user: user,
                                    isSelf: user.id == session.viewer?.id,
                                    onSuspend: { suspending = user },
                                    onDelete: { confirmingDelete = user }
                                )
                            }
                        }
                        .cardSurface()
                    }

                    if model.totalCount > 0 {
                        Text("admin.totalUsers \(model.totalCount)")
                            .font(.caption)
                            .foregroundStyle(Theme.textTertiary)
                            .monospacedDigit()
                    }
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle("admin.users")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: Text("admin.searchPrompt"))
        .task {
            if model == nil { model = AdminUsersModel(backend: session.backend) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        // Debounced: a search-as-you-type that fires per keystroke sends six requests
        // for a three-letter query and races their replies.
        .task(id: query) {
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            await model?.search(query)
        }
        .sheet(item: $suspending) { user in
            SuspendUserSheet(user: user)
        }
        .confirmationDialog(
            "admin.confirmDeleteTitle",
            isPresented: .init(
                get: { confirmingDelete != nil },
                set: { if !$0 { confirmingDelete = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("action.delete", role: .destructive) {
                if let user = confirmingDelete {
                    Task { await actions.deleteUser(id: user.id) }
                }
                confirmingDelete = nil
            }
            Button("action.cancel", role: .cancel) { confirmingDelete = nil }
        } message: {
            Text("admin.confirmDeleteBody")
        }
    }
}

private struct AdminUserRow: View {
    let user: Todo_V1_User
    let isSelf: Bool
    let onSuspend: () -> Void
    let onDelete: () -> Void

    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    var body: some View {
        HStack(spacing: Theme.Space.md) {
            AvatarView(name: user.displayName, url: user.avatarURL, size: 36)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: Theme.Space.sm) {
                    Text(user.displayName)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Theme.textPrimary)
                        .lineLimit(1)
                    if isSelf {
                        Badge(text: "lists.memberIsYou", tint: Theme.textTertiary)
                    }
                }
                Text(user.email)
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
                    .lineLimit(1)
                HStack(spacing: Theme.Space.xs + 2) {
                    UserStatusBadge(status: user.status)
                    if user.role == .admin {
                        Badge(text: user.role.displayName, tint: Theme.accent)
                    }
                    if user.hasLastSeenAt {
                        Text(Format.relative(user.lastSeenAt.date, locale: locale))
                            .font(.caption2)
                            .foregroundStyle(Theme.textTertiary)
                    }
                }
                .padding(.top, 1)
            }

            Spacer(minLength: 0)

            Menu {
                Section {
                    ForEach(Todo_V1_UserRole.selectable, id: \.self) { role in
                        Button {
                            Task { await actions.setUserRole(userId: user.id, role: role) }
                        } label: {
                            if role == user.role {
                                Label(role.displayName, systemImage: "checkmark")
                            } else {
                                Text(role.displayName)
                            }
                        }
                    }
                } header: {
                    Text("admin.role")
                }

                Section {
                    Button(action: onSuspend) {
                        Label("admin.changeStatus", systemImage: "person.badge.clock")
                    }
                }

                // An admin removing their own account, or demoting themselves, locks
                // everyone out of administration. The server refuses both
                // (`CANNOT_DEMOTE_SELF`); the menu simply does not offer them.
                if !isSelf {
                    Section {
                        Button(role: .destructive, action: onDelete) {
                            Label("action.delete", systemImage: "trash")
                        }
                    }
                }
            } label: {
                Image(systemName: "ellipsis")
                    .font(.caption)
                    .foregroundStyle(Theme.textTertiary)
                    .frame(width: 28, height: 28)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel("action.more")
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
    }
}

/// Changing an account's status, with the reason the API asks for.
private struct SuspendUserSheet: View {
    let user: Todo_V1_User

    @Environment(Actions.self) private var actions
    @Environment(\.dismiss) private var dismiss

    @State private var status: Todo_V1_UserStatus
    @State private var reason = ""

    init(user: Todo_V1_User) {
        self.user = user
        _status = State(initialValue: user.status)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(user.email)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                }
                Section {
                    EnumPicker(title: "admin.status", selection: $status)
                        .pickerStyle(.inline)
                        .labelsHidden()
                } header: {
                    Text("admin.status")
                }
                Section {
                    TextField("admin.reasonPlaceholder", text: $reason, axis: .vertical)
                        .lineLimit(2...4)
                } header: {
                    Text("admin.reason")
                } footer: {
                    // Recorded on the account, so a later admin can see why.
                    Text("admin.reasonFooter")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle("admin.changeStatus")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("action.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("action.save") {
                        Task {
                            await actions.setUserStatus(
                                userId: user.id,
                                status: status,
                                reason: reason.trimmingCharacters(in: .whitespacesAndNewlines)
                            )
                            if actions.failure == nil { dismiss() }
                        }
                    }
                    .fontWeight(.semibold)
                    .disabled(status == user.status)
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

// MARK: - Model

@MainActor
@Observable
final class AdminUsersModel {
    private let backend: TodoBackend

    private(set) var state: LoadState<[Todo_V1_User]> = .loading
    private(set) var statusFilter: Todo_V1_UserStatus?
    private(set) var totalCount = 0
    private var query = ""

    init(backend: TodoBackend) {
        self.backend = backend
    }

    func filter(by status: Todo_V1_UserStatus?) async {
        statusFilter = status
        await load()
    }

    func search(_ text: String) async {
        guard text != query else { return }
        query = text
        await load()
    }

    func load() async {
        let request = Todo_V1_ListUsersRequest.with {
            $0.page = .with { $0.limit = 50 }
            $0.query = query
            if let statusFilter { $0.statuses = [statusFilter] }
            $0.sortField = .createdAt
            $0.sortDirection = .desc
        }
        let result = unwrap(await backend.users.listUsers(request: request)) { $0 }
        if case let .success(message) = result { totalCount = Int(message.page.totalCount) }
        state = result.map(\.users).listState
    }
}
