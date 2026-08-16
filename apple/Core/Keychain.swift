import Foundation
import Security

/// Minimal Keychain wrapper. The session token never touches `UserDefaults` —
/// it lives only here.
enum Keychain {
    private static let service = "com.happenings.todoapp.session"

    /// Scopes an account name to the active backend in debug builds.
    ///
    /// Without this, pointing the debug build at a different host leaves the
    /// previous host's token in place, so the app looks signed in and then fails
    /// the first authenticated call in a way that reads like a server fault
    /// rather than a stale token.
    ///
    /// Release builds keep the bare name: adding a suffix there would orphan
    /// every existing install's token on update and sign everyone out.
    static func scopedAccount(_ key: String) -> String {
        #if DEBUG
        let environment = AppConfig.environmentName
        return environment == "production" ? key : "\(key)@\(environment)"
        #else
        return key
        #endif
    }

    static func set(_ value: String, for key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: scopedAccount(key),
        ]
        SecItemDelete(query as CFDictionary)
        var insert = query
        insert[kSecValueData as String] = Data(value.utf8)
        // The app needs the token on a background refresh after a reboot, before
        // the user has unlocked — but not before first unlock.
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(insert as CFDictionary, nil)
    }

    static func get(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: scopedAccount(key),
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    static func remove(_ key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: scopedAccount(key),
        ]
        SecItemDelete(query as CFDictionary)
    }
}
