import SwiftUI

/// What the enums *mean* — permissions, ordering, and the colors they resolve to.
///
/// Mirrors `web/src/lib/enums.ts`, including which sets are authoritative: the
/// permission and terminal-status sets exist on the server too, and these are the
/// client's copy for enabling controls. The server is still the one that enforces
/// them — a wrong answer here shows the wrong button, it does not grant access.

// MARK: - Permissions

extension Todo_V1_MemberRole {
    /// Roles allowed to change a list's content.
    static let writeRoles: Set<Todo_V1_MemberRole> = [.owner, .editor]

    /// May create and edit tasks on this list.
    var canWrite: Bool { Self.writeRoles.contains(self) }

    /// May comment. Commenters can talk but not touch.
    var canComment: Bool { canWrite || self == .commenter }

    /// Owns the list, so may share, rename or delete it.
    var isOwner: Bool { self == .owner }
}

// MARK: - Task status

extension Todo_V1_TaskStatus {
    /// Statuses meaning the task is finished. Mirrors the server's terminal set.
    static let terminal: Set<Todo_V1_TaskStatus> = [.done, .cancelled]

    /// Still outstanding.
    var isOpen: Bool { isConcrete && !Self.terminal.contains(self) }

    /// The statuses a filter should offer as "not finished".
    static var open: [Todo_V1_TaskStatus] { selectable.filter(\.isOpen) }

    /// Tapping the leading circle moves between exactly these two, which is the
    /// 95% interaction. Anything else is an explicit pick from the status menu.
    var toggled: Todo_V1_TaskStatus { self == .done ? .todo : .done }

    /// The check control's symbol.
    var symbol: String {
        switch self {
        case .done: "checkmark.circle.fill"
        case .cancelled: "xmark.circle.fill"
        case .inProgress: "circle.lefthalf.filled"
        case .blocked: "exclamationmark.circle"
        case .todo: "circle"
        case .unspecified, .UNRECOGNIZED: "circle.dashed"
        }
    }

    /// Foreground for the badge and the check control.
    var tint: Color {
        switch self {
        case .done: Theme.success
        case .inProgress: Theme.info
        case .blocked: Theme.warning
        case .todo, .cancelled, .unspecified, .UNRECOGNIZED: Theme.textSecondary
        }
    }
}

// MARK: - Priority

extension Todo_V1_TaskPriority {
    /// Only the top two get a color, so that "urgent" still means something in a
    /// list where everything is at least medium.
    var tint: Color {
        switch self {
        case .urgent: Theme.danger
        case .high: Theme.warning
        case .medium: Theme.textSecondary
        case .low, .none, .unspecified, .UNRECOGNIZED: Theme.textTertiary
        }
    }

    /// Whether the badge is worth the space at all. `none` and `low` are noise on
    /// a row — their absence says the same thing.
    var isWorthShowing: Bool {
        switch self {
        case .urgent, .high, .medium: true
        default: false
        }
    }

    /// A filled bar count, 0–3, for the compact indicator.
    var bars: Int {
        switch self {
        case .urgent: 3
        case .high: 2
        case .medium: 1
        default: 0
        }
    }
}

// MARK: - Colors

extension Todo_V1_ListColor {
    /// The accent a list paints its dot, chips and progress bar with.
    ///
    /// This is the one place the single-accent rule bends, and it bends for the
    /// same reason the map pins do: the color *is* the content here — it is how a
    /// person tells their lists apart at a glance, chosen by them, stored on the
    /// row. Everything else in the app stays on `Theme.accent`.
    var tint: Color {
        switch self {
        case .zinc: Theme.zinc400
        case .red: Theme.dyn(light: 0xDC2626, dark: 0xF87171)
        case .amber: Theme.dyn(light: 0xD97706, dark: 0xFBBF24)
        case .green: Theme.dyn(light: 0x16A34A, dark: 0x4ADE80)
        case .blue: Theme.dyn(light: 0x2563EB, dark: 0x60A5FA)
        case .violet: Theme.dyn(light: 0x7C3AED, dark: 0xA78BFA)
        case .pink: Theme.dyn(light: 0xDB2777, dark: 0xF472B6)
        case .unspecified, .UNRECOGNIZED: Theme.zinc400
        }
    }

    /// A faint wash of the same hue, for label chips and list headers.
    var wash: Color { tint.opacity(0.14) }
}

// MARK: - Visibility

extension Todo_V1_ListVisibility {
    var symbol: String {
        switch self {
        case .private: "lock"
        case .shared: "person.2"
        case .public: "globe"
        case .unspecified, .UNRECOGNIZED: "questionmark"
        }
    }
}

extension Todo_V1_SessionClient {
    var symbol: String {
        switch self {
        case .web: "safari"
        case .mobile: "iphone"
        case .cli: "terminal"
        case .unspecified, .UNRECOGNIZED: "questionmark.circle"
        }
    }
}

extension Todo_V1_UserStatus {
    var tint: Color {
        switch self {
        case .active: Theme.success
        case .pendingVerification: Theme.warning
        case .suspended: Theme.danger
        case .deactivated, .unspecified, .UNRECOGNIZED: Theme.textSecondary
        }
    }
}

// MARK: - Locale and appearance

extension Todo_V1_Locale {
    /// The BCP 47 tag this locale resolves to on the device.
    var languageCode: String {
        switch self {
        case .da: "da"
        case .en: "en"
        // The account has no stored preference, so follow the device.
        case .unspecified, .UNRECOGNIZED: Locale.autoupdatingCurrent.language.languageCode?.identifier ?? "en"
        }
    }

    /// Maps a device language onto the two the app ships. Anything else reads
    /// English, which is the development language.
    static func matching(_ locale: Locale) -> Todo_V1_Locale {
        locale.language.languageCode?.identifier == "da" ? .da : .en
    }
}

extension Todo_V1_ThemePreference {
    /// `nil` means "follow the system", which is what SwiftUI wants for
    /// `preferredColorScheme`.
    var colorScheme: ColorScheme? {
        switch self {
        case .light: .light
        case .dark: .dark
        case .system, .unspecified, .UNRECOGNIZED: nil
        }
    }

    var symbol: String {
        switch self {
        case .light: "sun.max"
        case .dark: "moon"
        case .system, .unspecified, .UNRECOGNIZED: "circle.lefthalf.filled"
        }
    }
}
