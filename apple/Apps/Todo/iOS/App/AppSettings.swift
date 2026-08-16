import Foundation
import Observation
import SwiftUI

/// Language and appearance, as the app actually renders them.
///
/// The account is the source of truth — `User.locale` and `User.theme` are stored
/// server-side so the web and the phone agree. But the app has to draw its first
/// frame before `GetCurrentUser` returns, so the last known values are mirrored
/// into `UserDefaults` and adopted at launch. Signed out, the device language wins.
@MainActor
@Observable
final class AppSettings {
    private static let localeKey = "preferred_locale"
    private static let themeKey = "preferred_theme"

    /// `nil` means "follow the device", which is the right default until an
    /// account says otherwise.
    private(set) var locale: Todo_V1_Locale
    private(set) var theme: Todo_V1_ThemePreference

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        let storedLocale = defaults.integer(forKey: Self.localeKey)
        self.locale = Todo_V1_Locale(rawValue: storedLocale).flatMap { $0.isConcrete ? $0 : nil }
            ?? .matching(.autoupdatingCurrent)
        let storedTheme = defaults.integer(forKey: Self.themeKey)
        self.theme = Todo_V1_ThemePreference(rawValue: storedTheme).flatMap { $0.isConcrete ? $0 : nil }
            ?? .system
    }

    /// The `Locale` to put in the environment. SwiftUI resolves every
    /// `LocalizedStringKey` against it, which is what makes the in-app language
    /// switch take effect without relaunching.
    var resolvedLocale: Locale { Locale(identifier: locale.languageCode) }

    var colorScheme: ColorScheme? { theme.colorScheme }

    /// Adopts what the account says. Called after the viewer loads, and after any
    /// edit elsewhere.
    func adopt(from user: Todo_V1_User) {
        if user.locale.isConcrete { apply(locale: user.locale) }
        if user.theme.isConcrete { apply(theme: user.theme) }
    }

    func apply(locale: Todo_V1_Locale) {
        guard locale.isConcrete else { return }
        self.locale = locale
        defaults.set(locale.rawValue, forKey: Self.localeKey)
    }

    func apply(theme: Todo_V1_ThemePreference) {
        guard theme.isConcrete else { return }
        self.theme = theme
        defaults.set(theme.rawValue, forKey: Self.themeKey)
    }
}
