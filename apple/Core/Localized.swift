import Foundation

/// Runtime string lookup against a specific language.
///
/// Almost everything on screen is a `Text(LocalizedStringKey)`, which SwiftUI
/// resolves through `\.locale` in the environment — so the in-app language switch
/// works without help. This exists for the handful of strings the app has to
/// build itself rather than hand to `Text`: error messages that need a number
/// substituted, and values passed to `accessibilityLabel(_: String)`.
///
/// `NSLocalizedString` cannot serve that purpose here, because it resolves against
/// the *device* language and would keep answering in Danish after the user picked
/// English inside the app.
enum Localized {
    /// Looks `key` up in `locale`'s language, substituting one `%@` when given.
    ///
    /// Falls back through: the requested language → the development language
    /// (English) → the key itself. A key echoed on screen is a bug, and
    /// `EnumDisplayTests` fails the build rather than letting one ship.
    static func string(_ key: String, locale: Locale, argument: String? = nil) -> String {
        let format = lookup(key, languageCode: locale.language.languageCode?.identifier)
        guard let argument else { return format }
        return String(format: format, argument)
    }

    private static func lookup(_ key: String, languageCode: String?) -> String {
        if let languageCode, let bundle = languageBundle(languageCode) {
            let value = bundle.localizedString(forKey: key, value: missing, table: nil)
            if value != missing { return value }
        }
        // Main bundle honours the device language, and its own fallback chain
        // ends at the development language.
        let value = Bundle.main.localizedString(forKey: key, value: missing, table: nil)
        return value == missing ? key : value
    }

    /// A sentinel that cannot collide with real copy, so "not found" is
    /// distinguishable from a translation that happens to equal the key.
    private static let missing = "\u{0}__missing__"

    /// `.lproj` bundles, resolved once each — `Bundle(path:)` hits the file system.
    private static let cache = LanguageBundleCache()

    private static func languageBundle(_ languageCode: String) -> Bundle? {
        cache.bundle(for: languageCode)
    }
}

/// Caches the per-language bundles behind a lock, since string lookup happens on
/// whatever actor the caller is on.
private final class LanguageBundleCache: @unchecked Sendable {
    private var bundles: [String: Bundle?] = [:]
    private let lock = NSLock()

    func bundle(for languageCode: String) -> Bundle? {
        lock.lock()
        defer { lock.unlock() }
        if let cached = bundles[languageCode] { return cached }
        let resolved = Bundle.main.path(forResource: languageCode, ofType: "lproj").flatMap(Bundle.init(path:))
        bundles[languageCode] = resolved
        return resolved
    }
}
