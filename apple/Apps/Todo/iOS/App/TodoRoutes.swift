import SwiftUI

/// Everything that can be pushed onto a navigation stack.
///
/// Values rather than views, so any screen can link to a task or a list without
/// importing the destination — and so one `.todoDestinations()` per stack resolves
/// them all. Ids, not whole messages: a route survives the object being refetched,
/// and a stale copy pushed from a week-old feed row would otherwise render stale.
enum TodoRoute: Hashable {
    case task(String)
    case list(String)
    case listMembers(String)
    case listLabels(String)
    case settings
    case sessions
    case adminUsers
    case profile
}

extension View {
    /// Registers every destination for the enclosing `NavigationStack`.
    func todoDestinations() -> some View {
        navigationDestination(for: TodoRoute.self) { route in
            switch route {
            case let .task(id): TaskDetailScreen(taskId: id)
            case let .list(id): ListDetailScreen(listId: id)
            case let .listMembers(id): ListMembersScreen(listId: id)
            case let .listLabels(id): ListLabelsScreen(listId: id)
            case .settings: SettingsScreen()
            case .sessions: SessionsScreen()
            case .adminUsers: AdminUsersScreen()
            case .profile: ProfileScreen()
            }
        }
    }
}

/// What the task composer was opened for.
///
/// `Identifiable` so it can drive `.sheet(item:)`, which is the presentation that
/// cannot get out of step with its data — unlike a separate `isPresented` flag and
/// draft, where dismissing without clearing the draft reopens the old one.
struct ComposerRequest: Identifiable {
    enum Mode {
        case create(TaskDraft)
        case edit(Todo_V1_Task)
    }

    let id = UUID()
    let mode: Mode

    static func create(listId: String) -> ComposerRequest {
        ComposerRequest(mode: .create(TaskDraft(listId: listId)))
    }

    static func edit(_ task: Todo_V1_Task) -> ComposerRequest {
        ComposerRequest(mode: .edit(task))
    }
}
