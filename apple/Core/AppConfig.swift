import Foundation

/// Where the app talks to, and how it labels that environment.
///
/// There is no deployed backend for this project yet, so a debug build defaults
/// to the local dev server rather than to a host that does not answer. Release
/// builds are pinned to HTTPS production and cannot be redirected — the override
/// below is compiled out.
enum AppConfig {
    static let productionBaseURL = "https://api.todoapp.happenings.dk"

    #if DEBUG
    /// Where `make dev-backend` can be reached from *this* build.
    ///
    /// The simulator shares the Mac's loopback interface, so `127.0.0.1` reaches it.
    /// A phone does not: there, `127.0.0.1` is the phone itself, and the app would
    /// fail every call while looking like a server fault.
    ///
    /// For a device, `make ios-device` bakes the Mac's **Bonjour name** into
    /// `Info.plist` — a name rather than an IP address, because a DHCP lease changes
    /// and a Bonjour name does not. App Transport Security allows plain
    /// HTTP to it under `NSAllowsLocalNetworking`, already set for this target.
    ///
    /// Note the dev server has to be listening on the LAN for any of this to work:
    /// `make dev-backend` binds loopback only, `make dev-backend-lan` binds all
    /// interfaces.
    static var localBaseURL: String {
        #if targetEnvironment(simulator)
        return "http://127.0.0.1:8081"
        #else
        let host = Bundle.main.object(forInfoDictionaryKey: "TodoappDevHost") as? String ?? ""
        guard !host.isEmpty else {
            // Built without a dev host. Loopback will fail, and Settings → Developer
            // is where to point it — which is better than silently inventing a host.
            return "http://127.0.0.1:8081"
        }
        return "http://\(host):8081"
        #endif
    }

    private static let overrideKey = "api_base_url_override"
    #endif

    /// Backend host. Debug resolves, in order: an in-app override (Settings →
    /// Developer), the `TODOAPP_API_BASE_URL` launch variable, then the local
    /// dev server.
    static var apiBaseURL: URL {
        #if DEBUG
        if let raw = UserDefaults.standard.string(forKey: overrideKey),
           !raw.isEmpty, let url = URL(string: raw) {
            return url
        }
        if let raw = ProcessInfo.processInfo.environment["TODOAPP_API_BASE_URL"],
           let url = URL(string: raw) {
            return url
        }
        return URL(string: localBaseURL)!
        #else
        return URL(string: productionBaseURL)!
        #endif
    }

    #if DEBUG
    /// The persisted override, or "" when following the default.
    static var baseURLOverride: String {
        UserDefaults.standard.string(forKey: overrideKey) ?? ""
    }

    /// Persists or clears the host override. Empty resets to the default.
    static func setBaseURLOverride(_ raw: String?) {
        let trimmed = raw?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if trimmed.isEmpty {
            UserDefaults.standard.removeObject(forKey: overrideKey)
        } else {
            UserDefaults.standard.set(trimmed, forKey: overrideKey)
        }
    }
    #endif

    /// Coarse environment label. Keychain scoping uses this so switching hosts
    /// in a debug build does not carry one environment's session into another.
    static var environmentName: String {
        let base = apiBaseURL.absoluteString
        if base == productionBaseURL { return "production" }
        #if DEBUG
        if base == localBaseURL { return "development" }
        return "custom"
        #else
        return "production"
        #endif
    }

    /// Marketing version + build, for the settings footer.
    static var displayVersion: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "0"
        let build = info?["CFBundleVersion"] as? String ?? "0"
        return "\(version) (\(build))"
    }
}
