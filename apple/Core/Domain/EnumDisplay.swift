import SwiftUI

/// Localized display names for every proto enum the UI renders.
///
/// A raw enum name must never reach the screen. The web derives its translation
/// keys at runtime from the proto descriptor because TypeScript cannot switch
/// exhaustively over a generated enum for free; Swift can, so this file maps each
/// value explicitly instead. That trade is deliberate: adding a value to
/// `enums.proto` breaks these switches at **compile time**, which is a stronger
/// guarantee than a runtime lookup that would quietly fall back to a placeholder.
///
/// Every key here has a Danish and an English entry in `Localizable.xcstrings`,
/// enforced by `EnumDisplayTests`.
///
/// `UNRECOGNIZED` is a real case, not paranoia: a server one deploy ahead can send
/// a value this build has never heard of, and the app has to render something
/// rather than crash.

/// A proto enum that knows how to name itself for a person.
protocol DisplayableEnum: CaseIterable, Hashable, Sendable {
    /// Key into the String Catalog.
    var displayKey: String { get }
    /// True for `UNSPECIFIED` and `UNRECOGNIZED` — values a picker must not offer.
    var isConcrete: Bool { get }
    /// The proto constant prefix, e.g. `TASK_STATUS`.
    static var protoPrefix: String { get }
}

extension DisplayableEnum {
    var displayName: LocalizedStringKey { LocalizedStringKey(displayKey) }

    /// The values worth showing in a picker: real choices only.
    static var selectable: [Self] { Array(allCases).filter(\.isConcrete) }

    /// The proto constant name, e.g. `TASK_STATUS_IN_PROGRESS`.
    ///
    /// Needed because two places on the wire carry enum *names* rather than typed
    /// values, and both have to be matched exactly:
    ///
    /// * `ListTasksResponse.status_counts` is keyed by name (a proto map cannot be
    ///   keyed by an enum), so the chip counts look up by name.
    /// * `ActivityChange.from_value` / `to_value` are strings, because the same
    ///   field carries a status on one row and a renamed title on the next.
    ///
    /// Derived from `displayKey`'s last component rather than listed a second time,
    /// so the two cannot drift apart. `EnumNameTests` pins every conversion against
    /// the generated descriptors.
    var protoName: String {
        let suffix = displayKey.split(separator: ".").last.map(String.init) ?? ""
        return "\(Self.protoPrefix)_\(Self.screamingSnake(suffix))"
    }

    /// `inProgress` → `IN_PROGRESS`.
    static func screamingSnake(_ camel: String) -> String {
        var result = ""
        for character in camel {
            if character.isUppercase, !result.isEmpty { result.append("_") }
            result.append(character.uppercased())
        }
        return result
    }
}

private let unknownKey = "enum.unknown"

// MARK: - Task

extension Todo_V1_TaskStatus: DisplayableEnum {
    static var protoPrefix: String { "TASK_STATUS" }

    var displayKey: String {
        switch self {
        case .todo: "enum.taskStatus.todo"
        case .inProgress: "enum.taskStatus.inProgress"
        case .blocked: "enum.taskStatus.blocked"
        case .done: "enum.taskStatus.done"
        case .cancelled: "enum.taskStatus.cancelled"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_TaskPriority: DisplayableEnum {
    static var protoPrefix: String { "TASK_PRIORITY" }

    var displayKey: String {
        switch self {
        case .none: "enum.taskPriority.none"
        case .low: "enum.taskPriority.low"
        case .medium: "enum.taskPriority.medium"
        case .high: "enum.taskPriority.high"
        case .urgent: "enum.taskPriority.urgent"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_RecurrenceFrequency: DisplayableEnum {
    static var protoPrefix: String { "RECURRENCE_FREQUENCY" }

    var displayKey: String {
        switch self {
        case .none: "enum.recurrence.none"
        case .daily: "enum.recurrence.daily"
        case .weekly: "enum.recurrence.weekly"
        case .monthly: "enum.recurrence.monthly"
        case .yearly: "enum.recurrence.yearly"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

// MARK: - List

extension Todo_V1_ListColor: DisplayableEnum {
    static var protoPrefix: String { "LIST_COLOR" }

    var displayKey: String {
        switch self {
        case .zinc: "enum.listColor.zinc"
        case .red: "enum.listColor.red"
        case .amber: "enum.listColor.amber"
        case .green: "enum.listColor.green"
        case .blue: "enum.listColor.blue"
        case .violet: "enum.listColor.violet"
        case .pink: "enum.listColor.pink"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_ListVisibility: DisplayableEnum {
    static var protoPrefix: String { "LIST_VISIBILITY" }

    var displayKey: String {
        switch self {
        case .private: "enum.listVisibility.private"
        case .shared: "enum.listVisibility.shared"
        case .public: "enum.listVisibility.public"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_MemberRole: DisplayableEnum {
    static var protoPrefix: String { "MEMBER_ROLE" }

    var displayKey: String {
        switch self {
        case .owner: "enum.memberRole.owner"
        case .editor: "enum.memberRole.editor"
        case .commenter: "enum.memberRole.commenter"
        case .viewer: "enum.memberRole.viewer"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

// MARK: - User

extension Todo_V1_UserRole: DisplayableEnum {
    static var protoPrefix: String { "USER_ROLE" }

    var displayKey: String {
        switch self {
        case .member: "enum.userRole.member"
        case .admin: "enum.userRole.admin"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_UserStatus: DisplayableEnum {
    static var protoPrefix: String { "USER_STATUS" }

    var displayKey: String {
        switch self {
        case .pendingVerification: "enum.userStatus.pendingVerification"
        case .active: "enum.userStatus.active"
        case .suspended: "enum.userStatus.suspended"
        case .deactivated: "enum.userStatus.deactivated"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_Locale: DisplayableEnum {
    static var protoPrefix: String { "LOCALE" }

    var displayKey: String {
        switch self {
        case .da: "enum.locale.da"
        case .en: "enum.locale.en"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_ThemePreference: DisplayableEnum {
    static var protoPrefix: String { "THEME_PREFERENCE" }

    var displayKey: String {
        switch self {
        case .system: "enum.theme.system"
        case .light: "enum.theme.light"
        case .dark: "enum.theme.dark"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

extension Todo_V1_SessionClient: DisplayableEnum {
    static var protoPrefix: String { "SESSION_CLIENT" }

    var displayKey: String {
        switch self {
        case .web: "enum.sessionClient.web"
        case .mobile: "enum.sessionClient.mobile"
        case .cli: "enum.sessionClient.cli"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }
}

// MARK: - Activity

extension Todo_V1_ActivityAction: DisplayableEnum {
    static var protoPrefix: String { "ACTIVITY_ACTION" }

    var displayKey: String {
        switch self {
        case .created: "enum.activityAction.created"
        case .updated: "enum.activityAction.updated"
        case .statusChanged: "enum.activityAction.statusChanged"
        case .assigned: "enum.activityAction.assigned"
        case .unassigned: "enum.activityAction.unassigned"
        case .commented: "enum.activityAction.commented"
        case .archived: "enum.activityAction.archived"
        case .restored: "enum.activityAction.restored"
        case .deleted: "enum.activityAction.deleted"
        case .memberAdded: "enum.activityAction.memberAdded"
        case .memberRemoved: "enum.activityAction.memberRemoved"
        case .memberRoleChanged: "enum.activityAction.memberRoleChanged"
        case .unspecified, .UNRECOGNIZED: unknownKey
        }
    }

    var isConcrete: Bool {
        switch self {
        case .unspecified, .UNRECOGNIZED: false
        default: true
        }
    }

    /// SF Symbol for the feed row. Chosen to read at a glance in a dense list:
    /// the shape carries the meaning before the sentence is read.
    var symbol: String {
        switch self {
        case .created: "plus.circle"
        case .updated: "pencil"
        case .statusChanged: "arrow.triangle.2.circlepath"
        case .assigned: "person.crop.circle.badge.checkmark"
        case .unassigned: "person.crop.circle.badge.xmark"
        case .commented: "text.bubble"
        case .archived: "archivebox"
        case .restored: "arrow.uturn.backward"
        case .deleted: "trash"
        case .memberAdded: "person.badge.plus"
        case .memberRemoved: "person.badge.minus"
        case .memberRoleChanged: "person.crop.circle.badge.exclamationmark"
        case .unspecified, .UNRECOGNIZED: "circle"
        }
    }
}
