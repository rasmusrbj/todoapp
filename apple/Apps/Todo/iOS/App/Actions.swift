import Connect
import Foundation
import Observation
import SwiftUI

/// Every write the app makes, in one place.
///
/// The mirror of the web's `app/actions/` modules, and it exists for the same
/// reason: mutations need consistent error handling and consistent invalidation,
/// and scattering them across twenty views guarantees neither.
///
/// Screens observe `revision`. Any successful write bumps it, and a screen that
/// does `.task(id: actions.revision) { await reload() }` refetches — so completing
/// a task on the Today screen updates the list's counters and the activity feed
/// without either screen knowing the other exists.
///
/// `failure` is the shared error sink. A view puts it in a toast; it is cleared at
/// the start of the next write.
@MainActor
@Observable
final class Actions {
    private let backend: TodoBackend

    private(set) var revision = 0
    var failure: AppFailure?
    /// Catalog key of a confirmation the UI should say out loud.
    ///
    /// A `String` rather than a `LocalizedStringKey` because the toast needs to
    /// resolve it against the app's chosen language, and `LocalizedStringKey`
    /// offers no way to read its key back out.
    var confirmation: String?

    /// Ids of tasks with a write in flight, so a row can show it is busy without
    /// the whole screen going into a loading state.
    private(set) var pending: Set<String> = []

    init(backend: TodoBackend) {
        self.backend = backend
    }

    func isPending(_ id: String) -> Bool { pending.contains(id) }

    // MARK: - Tasks

    func setStatus(taskId: String, status: Todo_V1_TaskStatus) async {
        await write(taskId) {
            let request = Todo_V1_SetTaskStatusRequest.with {
                $0.id = taskId
                $0.status = status
            }
            let result = unwrap(await self.backend.tasks.setTaskStatus(request: request))
            // Completing a repeating task spawns the next occurrence server-side.
            // Saying so matters: otherwise a task the user just ticked appears to
            // come straight back, which reads as a bug rather than as the point of
            // a recurring task.
            if case let .success(message) = result, message.hasNextOccurrence {
                self.confirmation = "tasks.recurrenceSpawned"
            }
            return result.map { _ in () }
        }
    }

    func toggleDone(_ task: Todo_V1_Task) async {
        await setStatus(taskId: task.id, status: task.status.toggled)
    }

    func create(_ draft: TaskDraft) async -> Todo_V1_Task? {
        await writeReturning {
            unwrap(await self.backend.tasks.createTask(request: draft.createRequest)) {
                $0.hasTask ? $0.task : nil
            }
        }
    }

    func update(_ draft: TaskDraft, id: String) async -> Bool {
        await write(id) {
            unwrap(await self.backend.tasks.updateTask(request: draft.updateRequest(id: id)))
                .map { _ in () }
        }
    }

    func assign(taskId: String, to userId: String?) async {
        await write(taskId) {
            let request = Todo_V1_AssignTaskRequest.with {
                $0.id = taskId
                // Leaving the optional unset is what clears the assignee; sending
                // an empty string would be a lookup for a user with no id.
                if let userId, !userId.isEmpty { $0.assigneeID = userId }
            }
            return unwrap(await self.backend.tasks.assignTask(request: request)).map { _ in () }
        }
    }

    func setLabels(taskId: String, labelIds: [String]) async {
        await write(taskId) {
            let request = Todo_V1_SetTaskLabelsRequest.with {
                $0.taskID = taskId
                $0.labelIds = labelIds
            }
            return unwrap(await self.backend.tasks.setTaskLabels(request: request)).map { _ in () }
        }
    }

    func move(taskId: String, toList listId: String?, position: Int) async {
        await write(taskId) {
            let request = Todo_V1_MoveTaskRequest.with {
                $0.id = taskId
                if let listId { $0.listID = listId }
                $0.position = Int32(position)
            }
            let result = unwrap(await self.backend.tasks.moveTask(request: request))
            if case .success = result, listId != nil { self.confirmation = "tasks.moved" }
            return result.map { _ in () }
        }
    }

    func delete(taskId: String) async {
        await write(taskId) {
            let request = Todo_V1_DeleteTaskRequest.with { $0.id = taskId }
            let result = unwrap(await self.backend.tasks.deleteTask(request: request))
            if case .success = result { self.confirmation = "tasks.deleted" }
            return result.map { _ in () }
        }
    }

    /// One change applied to many tasks. `change` is a oneof, so exactly one may be
    /// set — the enum here makes it impossible to set two.
    ///
    /// (`clearAssignee_p` below carries the `_p` suffix for the same reason
    /// `clear_due_at` does: SwiftProtobuf already uses `clearAssignee()` to unset
    /// the oneof, so the field with that name gets renamed.)
    enum BulkChange {
        case status(Todo_V1_TaskStatus)
        case priority(Todo_V1_TaskPriority)
        case list(String)
        case assignee(String)
        case clearAssignee
    }

    func bulkUpdate(taskIds: [String], change: BulkChange) async -> Int {
        guard !taskIds.isEmpty else { return 0 }
        let result: Int? = await writeReturning {
            let request = Todo_V1_BulkUpdateTasksRequest.with {
                $0.taskIds = taskIds
                switch change {
                case let .status(value): $0.status = value
                case let .priority(value): $0.priority = value
                case let .list(value): $0.listID = value
                case let .assignee(value): $0.assigneeID = value
                case .clearAssignee: $0.clearAssignee_p = true
                }
            }
            return unwrap(await self.backend.tasks.bulkUpdateTasks(request: request)) {
                Int($0.updatedCount)
            }
        }
        return result ?? 0
    }

    // MARK: - Subtasks

    func addSubtask(taskId: String, title: String) async {
        await write(taskId) {
            let request = Todo_V1_CreateSubtaskRequest.with {
                $0.taskID = taskId
                $0.title = title
            }
            return unwrap(await self.backend.tasks.createSubtask(request: request)).map { _ in () }
        }
    }

    func setSubtaskCompleted(subtaskId: String, completed: Bool) async {
        await write(subtaskId) {
            let request = Todo_V1_UpdateSubtaskRequest.with {
                $0.id = subtaskId
                $0.completed = completed
            }
            return unwrap(await self.backend.tasks.updateSubtask(request: request)).map { _ in () }
        }
    }

    func renameSubtask(subtaskId: String, title: String) async {
        await write(subtaskId) {
            let request = Todo_V1_UpdateSubtaskRequest.with {
                $0.id = subtaskId
                $0.title = title
            }
            return unwrap(await self.backend.tasks.updateSubtask(request: request)).map { _ in () }
        }
    }

    func deleteSubtask(subtaskId: String) async {
        await write(subtaskId) {
            let request = Todo_V1_DeleteSubtaskRequest.with { $0.id = subtaskId }
            return unwrap(await self.backend.tasks.deleteSubtask(request: request)).map { _ in () }
        }
    }

    // MARK: - Comments

    func comment(taskId: String, body: String) async {
        await write(taskId) {
            let request = Todo_V1_CreateCommentRequest.with {
                $0.taskID = taskId
                $0.body = body
            }
            return unwrap(await self.backend.tasks.createComment(request: request)).map { _ in () }
        }
    }

    func editComment(id: String, body: String) async {
        await write(id) {
            let request = Todo_V1_UpdateCommentRequest.with {
                $0.id = id
                $0.body = body
            }
            return unwrap(await self.backend.tasks.updateComment(request: request)).map { _ in () }
        }
    }

    func deleteComment(id: String) async {
        await write(id) {
            let request = Todo_V1_DeleteCommentRequest.with { $0.id = id }
            return unwrap(await self.backend.tasks.deleteComment(request: request)).map { _ in () }
        }
    }

    // MARK: - Lists

    func createList(_ draft: ListDraft) async -> Todo_V1_TodoList? {
        await writeReturning {
            unwrap(await self.backend.lists.createList(request: draft.createRequest)) {
                $0.hasList ? $0.list : nil
            }
        }
    }

    func updateList(_ draft: ListDraft, id: String) async -> Bool {
        await write(id) {
            unwrap(await self.backend.lists.updateList(request: draft.updateRequest(id: id)))
                .map { _ in () }
        }
    }

    func setListArchived(id: String, archived: Bool) async {
        await write(id) {
            let request = Todo_V1_SetListArchivedRequest.with {
                $0.id = id
                $0.archived = archived
            }
            let result = unwrap(await self.backend.lists.setListArchived(request: request))
            if case .success = result {
                self.confirmation = archived ? "lists.archived" : "lists.restored"
            }
            return result.map { _ in () }
        }
    }

    func deleteList(id: String) async {
        await write(id) {
            let request = Todo_V1_DeleteListRequest.with { $0.id = id }
            let result = unwrap(await self.backend.lists.deleteList(request: request))
            if case .success = result { self.confirmation = "lists.deleted" }
            return result.map { _ in () }
        }
    }

    func reorderLists(ids: [String]) async {
        await write(nil) {
            let request = Todo_V1_ReorderListsRequest.with { $0.listIds = ids }
            return unwrap(await self.backend.lists.reorderLists(request: request)).map { _ in () }
        }
    }

    // MARK: - Members

    func addMember(listId: String, email: String, role: Todo_V1_MemberRole) async -> Bool {
        await write(listId) {
            let request = Todo_V1_AddMemberRequest.with {
                $0.listID = listId
                $0.email = email
                $0.role = role
            }
            let result = unwrap(await self.backend.lists.addMember(request: request))
            if case .success = result { self.confirmation = "lists.memberAdded" }
            return result.map { _ in () }
        }
    }

    func setMemberRole(listId: String, userId: String, role: Todo_V1_MemberRole) async {
        await write(userId) {
            let request = Todo_V1_UpdateMemberRoleRequest.with {
                $0.listID = listId
                $0.userID = userId
                $0.role = role
            }
            return unwrap(await self.backend.lists.updateMemberRole(request: request)).map { _ in () }
        }
    }

    func removeMember(listId: String, userId: String) async {
        await write(userId) {
            let request = Todo_V1_RemoveMemberRequest.with {
                $0.listID = listId
                $0.userID = userId
            }
            return unwrap(await self.backend.lists.removeMember(request: request)).map { _ in () }
        }
    }

    // MARK: - Labels

    func createLabel(listId: String, name: String, color: Todo_V1_ListColor) async -> Bool {
        await write(listId) {
            let request = Todo_V1_CreateLabelRequest.with {
                $0.listID = listId
                $0.name = name
                $0.color = color
            }
            return unwrap(await self.backend.lists.createLabel(request: request)).map { _ in () }
        }
    }

    func updateLabel(id: String, name: String, color: Todo_V1_ListColor) async {
        await write(id) {
            let request = Todo_V1_UpdateLabelRequest.with {
                $0.id = id
                $0.name = name
                $0.color = color
            }
            return unwrap(await self.backend.lists.updateLabel(request: request)).map { _ in () }
        }
    }

    func deleteLabel(id: String) async {
        await write(id) {
            let request = Todo_V1_DeleteLabelRequest.with { $0.id = id }
            return unwrap(await self.backend.lists.deleteLabel(request: request)).map { _ in () }
        }
    }

    // MARK: - Account

    func updateProfile(
        displayName: String?,
        bio: String?,
        timeZone: String?,
        locale: Todo_V1_Locale?,
        theme: Todo_V1_ThemePreference?
    ) async -> Todo_V1_User? {
        await writeReturning {
            let request = Todo_V1_UpdateUserRequest.with {
                $0.id = ""  // Empty id means "me" server-side.
                if let displayName { $0.displayName = displayName }
                if let bio { $0.bio = bio }
                if let timeZone { $0.timeZone = timeZone }
                if let locale { $0.locale = locale }
                if let theme { $0.theme = theme }
            }
            return unwrap(await self.backend.users.updateUser(request: request)) {
                $0.hasUser ? $0.user : nil
            }
        }
    }

    func revokeSession(id: String) async {
        await write(id) {
            let request = Todo_V1_RevokeSessionRequest.with { $0.id = id }
            return unwrap(await self.backend.auth.revokeSession(request: request)).map { _ in () }
        }
    }

    func resendVerificationEmail() async -> Bool {
        await write(nil) {
            let result = unwrap(
                await self.backend.auth.resendVerificationEmail(
                    request: Todo_V1_ResendVerificationEmailRequest()
                )
            )
            if case .success = result { self.confirmation = "settings.verificationSent" }
            return result.map { _ in () }
        }
    }

    // MARK: - Admin

    func setUserStatus(userId: String, status: Todo_V1_UserStatus, reason: String) async {
        await write(userId) {
            let request = Todo_V1_UpdateUserStatusRequest.with {
                $0.id = userId
                $0.status = status
                $0.reason = reason
            }
            return unwrap(await self.backend.users.updateUserStatus(request: request)).map { _ in () }
        }
    }

    func setUserRole(userId: String, role: Todo_V1_UserRole) async {
        await write(userId) {
            let request = Todo_V1_UpdateUserRequest.with {
                $0.id = userId
                $0.role = role
            }
            return unwrap(await self.backend.users.updateUser(request: request)).map { _ in () }
        }
    }

    func deleteUser(id: String) async {
        await write(id) {
            let request = Todo_V1_DeleteUserRequest.with { $0.id = id }
            return unwrap(await self.backend.users.deleteUser(request: request)).map { _ in () }
        }
    }

    // MARK: - Plumbing

    /// Runs a write, tracking it as pending and bumping `revision` on success.
    @discardableResult
    private func write(_ pendingId: String?, _ body: () async -> Result<Void, AppFailure>) async -> Bool {
        failure = nil
        if let pendingId { pending.insert(pendingId) }
        defer { if let pendingId { pending.remove(pendingId) } }

        switch await body() {
        case .success:
            revision += 1
            return true
        case let .failure(error):
            failure = error
            return false
        }
    }

    /// The same, for a write whose result the caller needs.
    private func writeReturning<Value>(_ body: () async -> Result<Value, AppFailure>) async -> Value? {
        failure = nil
        switch await body() {
        case let .success(value):
            revision += 1
            return value
        case let .failure(error):
            failure = error
            return nil
        }
    }
}
