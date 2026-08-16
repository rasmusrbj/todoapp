import Observation
import SwiftUI

/// Who can reach a list, and at what level.
struct ListMembersScreen: View {
    let listId: String

    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: MembersModel?
    @State private var inviting = false

    var body: some View {
        ScreenScaffold(refresh: { await model?.load() }) {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let model {
                    StateView(
                        state: model.state,
                        emptySymbol: "person.2",
                        emptyTitle: "lists.noMembersTitle",
                        retry: { await model.load() }
                    ) { members in
                        VStack(spacing: 0) {
                            ForEach(Array(members.enumerated()), id: \.element.id) { index, member in
                                if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.lg) }
                                MemberRow(
                                    listId: listId,
                                    member: member,
                                    viewerId: session.viewer?.id ?? "",
                                    canManage: model.canManage
                                )
                            }
                        }
                        .cardSurface()
                    }

                    RoleLegend()
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle("lists.members")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if model?.canManage == true {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { inviting = true } label: {
                        Image(systemName: "person.badge.plus")
                    }
                    .accessibilityLabel("lists.invite")
                }
            }
        }
        .task {
            if model == nil { model = MembersModel(backend: session.backend, listId: listId) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(isPresented: $inviting) {
            InviteMemberSheet(listId: listId)
        }
    }
}

private struct MemberRow: View {
    let listId: String
    let member: Todo_V1_ListMember
    let viewerId: String
    let canManage: Bool

    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    private var isSelf: Bool { member.user.id == viewerId }

    /// The owner's role cannot be changed and they cannot be removed — the server
    /// enforces both (`CANNOT_REMOVE_OWNER`), and a list with no owner has nobody
    /// who can share or delete it. So the controls are simply absent.
    private var isMutable: Bool { canManage && !member.role.isOwner }

    var body: some View {
        HStack(spacing: Theme.Space.md) {
            AvatarView(name: member.user.displayName, url: member.user.avatarURL, size: 36)

            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: Theme.Space.sm) {
                    Text(member.user.displayName)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Theme.textPrimary)
                    if isSelf {
                        Badge(text: "lists.memberIsYou", tint: Theme.textTertiary)
                    }
                }
                Text(member.user.email)
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
                    .lineLimit(1)
                if member.hasInvitedBy, !member.invitedBy.displayName.isEmpty {
                    Text("lists.invitedBy \(member.invitedBy.displayName)")
                        .font(.caption2)
                        .foregroundStyle(Theme.textTertiary)
                }
            }

            Spacer(minLength: Theme.Space.sm)

            if isMutable {
                Menu {
                    ForEach(Todo_V1_MemberRole.selectable.filter { !$0.isOwner }, id: \.self) { role in
                        Button {
                            Task {
                                await actions.setMemberRole(
                                    listId: listId,
                                    userId: member.user.id,
                                    role: role
                                )
                            }
                        } label: {
                            if role == member.role {
                                Label(role.displayName, systemImage: "checkmark")
                            } else {
                                Text(role.displayName)
                            }
                        }
                    }
                    Divider()
                    Button(role: .destructive) {
                        Task {
                            await actions.removeMember(listId: listId, userId: member.user.id)
                        }
                    } label: {
                        Label("lists.removeMember", systemImage: "person.badge.minus")
                    }
                } label: {
                    HStack(spacing: 4) {
                        RoleBadge(role: member.role)
                        Image(systemName: "chevron.up.chevron.down")
                            .font(.system(size: 8, weight: .semibold))
                            .foregroundStyle(Theme.textTertiary)
                    }
                }
                .pressable(0.95)
            } else {
                RoleBadge(role: member.role)
            }
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
    }
}

/// What each role can actually do — the four words mean nothing without this.
private struct RoleLegend: View {
    var body: some View {
        ScreenSection("lists.roleLegend") {
            GroupedCard {
                ForEach(Array(Todo_V1_MemberRole.selectable.enumerated()), id: \.element) { index, role in
                    if index > 0 { InsetDivider() }
                    HStack(alignment: .top, spacing: Theme.Space.md) {
                        Text(role.displayName)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Theme.textPrimary)
                            .frame(width: 84, alignment: .leading)
                        Text(explanation(role))
                            .font(.caption)
                            .foregroundStyle(Theme.textSecondary)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, Theme.Space.lg)
                    .padding(.vertical, Theme.Space.md)
                }
            }
        }
    }

    private func explanation(_ role: Todo_V1_MemberRole) -> LocalizedStringKey {
        switch role {
        case .owner: "lists.roleOwnerHint"
        case .editor: "lists.roleEditorHint"
        case .commenter: "lists.roleCommenterHint"
        case .viewer: "lists.roleViewerHint"
        case .unspecified, .UNRECOGNIZED: ""
        }
    }
}

/// Invites someone by email address.
private struct InviteMemberSheet: View {
    let listId: String

    @Environment(Actions.self) private var actions
    @Environment(\.dismiss) private var dismiss

    @State private var email = ""
    @State private var role: Todo_V1_MemberRole = .editor
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("auth.email", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } footer: {
                    // The server only adds people who already have an account, so
                    // saying so up front avoids the "I invited them and nothing
                    // happened" confusion.
                    Text("lists.inviteFooter")
                }

                Section {
                    EnumPicker(
                        title: "lists.role",
                        selection: $role,
                        // The owner role is not grantable: ownership transfer is a
                        // different operation with different consequences.
                        allowed: Todo_V1_MemberRole.selectable.filter { !$0.isOwner }
                    )
                    .pickerStyle(.inline)
                    .labelsHidden()
                } header: {
                    Text("lists.role")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle("lists.invite")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("action.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("lists.sendInvite") {
                        Task {
                            isSaving = true
                            let added = await actions.addMember(
                                listId: listId,
                                email: email.trimmingCharacters(in: .whitespaces),
                                role: role
                            )
                            isSaving = false
                            if added { dismiss() }
                        }
                    }
                    .fontWeight(.semibold)
                    .disabled(!email.contains("@") || isSaving)
                }
            }
        }
        .presentationDetents([.medium])
    }
}

// MARK: - Model

@MainActor
@Observable
final class MembersModel {
    private let backend: TodoBackend
    private let listId: String

    private(set) var state: LoadState<[Todo_V1_ListMember]> = .loading
    private(set) var canManage = false

    init(backend: TodoBackend, listId: String) {
        self.backend = backend
        self.listId = listId
    }

    func load() async {
        // `GetList` already embeds the members *and* the caller's role, so one call
        // answers both questions. `ListMembers` exists for paging a very large list;
        // using it here would need a second call just to learn the viewer's role.
        let request = Todo_V1_GetListRequest.with { $0.id = listId }
        let result = unwrap(await backend.lists.getList(request: request)) { $0.hasList ? $0.list : nil }
        switch result {
        case let .success(list):
            canManage = list.viewerRole.isOwner
            state = list.members.isEmpty ? .empty : .loaded(list.members)
        case let .failure(failure):
            state = .failed(failure)
        }
    }
}
