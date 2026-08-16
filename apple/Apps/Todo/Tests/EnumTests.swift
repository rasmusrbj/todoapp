import Foundation
import SwiftProtobuf
import Testing

@testable import Todoapp

/// The enum layer: names that go on the wire, sets that gate the UI, and the
/// declaration order the server depends on.
@Suite("Enums")
struct EnumTests {
    // MARK: Proto names

    /// `protoName` is derived from the display key, and two places on the wire match
    /// on it — `status_counts` map keys and `ActivityChange` values. A wrong answer is
    /// silent: the count chip just shows nothing.
    ///
    /// So each is checked against the constant the server actually sends.
    @Test("Task status proto names match the wire")
    func taskStatusNames() {
        #expect(Todo_V1_TaskStatus.todo.protoName == "TASK_STATUS_TODO")
        #expect(Todo_V1_TaskStatus.inProgress.protoName == "TASK_STATUS_IN_PROGRESS")
        #expect(Todo_V1_TaskStatus.blocked.protoName == "TASK_STATUS_BLOCKED")
        #expect(Todo_V1_TaskStatus.done.protoName == "TASK_STATUS_DONE")
        #expect(Todo_V1_TaskStatus.cancelled.protoName == "TASK_STATUS_CANCELLED")
    }

    @Test("Multi-word enum names snake-case correctly")
    func multiWordNames() {
        #expect(Todo_V1_ActivityAction.statusChanged.protoName == "ACTIVITY_ACTION_STATUS_CHANGED")
        #expect(Todo_V1_ActivityAction.memberRoleChanged.protoName == "ACTIVITY_ACTION_MEMBER_ROLE_CHANGED")
        #expect(Todo_V1_UserStatus.pendingVerification.protoName == "USER_STATUS_PENDING_VERIFICATION")
        #expect(Todo_V1_RecurrenceFrequency.monthly.protoName == "RECURRENCE_FREQUENCY_MONTHLY")
    }

    @Test("Activity diff values resolve to display keys")
    func activityValueLookup() {
        // The server sends enum *names* in `ActivityChange`, never localized text.
        #expect(ActivityValueNames.displayKey(for: "TASK_STATUS_DONE") == "enum.taskStatus.done")
        #expect(ActivityValueNames.displayKey(for: "MEMBER_ROLE_EDITOR") == "enum.memberRole.editor")
        // Free text — a renamed title — passes straight through as itself.
        #expect(ActivityValueNames.displayKey(for: "Buy milk") == nil)
    }

    // MARK: Selectable values

    /// `UNSPECIFIED` and `UNRECOGNIZED` must never appear in a picker.
    @Test("Pickers offer only real values")
    func selectableExcludesPlaceholders() {
        #expect(Todo_V1_TaskStatus.selectable.count == 5)
        #expect(!Todo_V1_TaskStatus.selectable.contains(.unspecified))
        #expect(Todo_V1_TaskPriority.selectable.count == 5)
        #expect(Todo_V1_MemberRole.selectable.count == 4)
        #expect(Todo_V1_ListColor.selectable.count == 7)
        #expect(Todo_V1_Locale.selectable == [.da, .en])
    }

    /// A value this build has never seen must render *something* rather than crash or
    /// print a number — a server one deploy ahead is a normal state, not a bug.
    @Test("An unrecognised value falls back to a translated placeholder")
    func unrecognisedFallsBack() {
        let future = Todo_V1_TaskStatus(rawValue: 99) ?? .unspecified
        #expect(future.displayKey == "enum.unknown")
        #expect(future.isConcrete == false)
        #expect(!Todo_V1_TaskStatus.selectable.contains(future))
    }

    // MARK: Semantics

    @Test("Write roles match the server's set")
    func writeRoles() {
        #expect(Todo_V1_MemberRole.owner.canWrite)
        #expect(Todo_V1_MemberRole.editor.canWrite)
        #expect(!Todo_V1_MemberRole.commenter.canWrite)
        #expect(!Todo_V1_MemberRole.viewer.canWrite)
    }

    /// Commenting is a superset of writing: anyone who can edit can also comment.
    @Test("Comment permission is a superset of write permission")
    func commentRoles() {
        for role in Todo_V1_MemberRole.selectable where role.canWrite {
            #expect(role.canComment, "\(role) can write but supposedly not comment")
        }
        #expect(Todo_V1_MemberRole.commenter.canComment)
        #expect(!Todo_V1_MemberRole.viewer.canComment)
    }

    @Test("Only the owner is the owner")
    func ownership() {
        #expect(Todo_V1_MemberRole.owner.isOwner)
        for role in Todo_V1_MemberRole.selectable where role != .owner {
            #expect(!role.isOwner)
        }
    }

    @Test("Terminal statuses mirror the server's")
    func terminalStatuses() {
        #expect(Todo_V1_TaskStatus.terminal == [.done, .cancelled])
        #expect(Todo_V1_TaskStatus.todo.isOpen)
        #expect(Todo_V1_TaskStatus.inProgress.isOpen)
        #expect(Todo_V1_TaskStatus.blocked.isOpen)
        #expect(!Todo_V1_TaskStatus.done.isOpen)
        #expect(!Todo_V1_TaskStatus.cancelled.isOpen)
        // An unspecified status is not "open" — it is not a status at all.
        #expect(!Todo_V1_TaskStatus.unspecified.isOpen)
    }

    @Test("The check control toggles between todo and done")
    func statusToggle() {
        #expect(Todo_V1_TaskStatus.todo.toggled == .done)
        #expect(Todo_V1_TaskStatus.done.toggled == .todo)
        // Anything mid-flight completes rather than reverting to todo, which is what
        // tapping the circle on an in-progress task should mean.
        #expect(Todo_V1_TaskStatus.inProgress.toggled == .done)
        #expect(Todo_V1_TaskStatus.blocked.toggled == .done)
    }

    // MARK: Declaration order

    /// Priority is declared least-to-most urgent so the server's `ORDER BY priority
    /// DESC` puts urgent first. Reordering the proto would silently invert every
    /// sorted list, so the raw values are pinned.
    @Test("Priority ordering is least to most urgent")
    func priorityOrder() {
        #expect(Todo_V1_TaskPriority.none.rawValue < Todo_V1_TaskPriority.low.rawValue)
        #expect(Todo_V1_TaskPriority.low.rawValue < Todo_V1_TaskPriority.medium.rawValue)
        #expect(Todo_V1_TaskPriority.medium.rawValue < Todo_V1_TaskPriority.high.rawValue)
        #expect(Todo_V1_TaskPriority.high.rawValue < Todo_V1_TaskPriority.urgent.rawValue)
    }

    /// Roles are declared most-to-least privileged.
    @Test("Role ordering is most to least privileged")
    func roleOrder() {
        #expect(Todo_V1_MemberRole.owner.rawValue < Todo_V1_MemberRole.editor.rawValue)
        #expect(Todo_V1_MemberRole.editor.rawValue < Todo_V1_MemberRole.commenter.rawValue)
        #expect(Todo_V1_MemberRole.commenter.rawValue < Todo_V1_MemberRole.viewer.rawValue)
    }

    /// The bar indicator only paints the top three, and `isWorthShowing` decides
    /// whether a row spends space on it at all.
    @Test("Priority indicator only fires above medium")
    func priorityIndicator() {
        #expect(Todo_V1_TaskPriority.urgent.bars == 3)
        #expect(Todo_V1_TaskPriority.high.bars == 2)
        #expect(Todo_V1_TaskPriority.medium.bars == 1)
        #expect(Todo_V1_TaskPriority.low.bars == 0)
        #expect(Todo_V1_TaskPriority.none.bars == 0)
        #expect(!Todo_V1_TaskPriority.low.isWorthShowing)
        #expect(Todo_V1_TaskPriority.urgent.isWorthShowing)
    }

    // MARK: Locale mapping

    @Test("Device languages map onto the two we ship")
    func localeMapping() {
        #expect(Todo_V1_Locale.matching(Locale(identifier: "da_DK")) == .da)
        #expect(Todo_V1_Locale.matching(Locale(identifier: "da")) == .da)
        #expect(Todo_V1_Locale.matching(Locale(identifier: "en_GB")) == .en)
        // Anything else reads English, the development language — not a raw fallback.
        #expect(Todo_V1_Locale.matching(Locale(identifier: "de_DE")) == .en)
        #expect(Todo_V1_Locale.matching(Locale(identifier: "ja_JP")) == .en)
    }

    @Test("Theme maps to a colour scheme, with system meaning nil")
    func themeMapping() {
        #expect(Todo_V1_ThemePreference.light.colorScheme == .light)
        #expect(Todo_V1_ThemePreference.dark.colorScheme == .dark)
        // `nil` is what SwiftUI wants for "follow the system".
        #expect(Todo_V1_ThemePreference.system.colorScheme == nil)
        #expect(Todo_V1_ThemePreference.unspecified.colorScheme == nil)
    }
}
