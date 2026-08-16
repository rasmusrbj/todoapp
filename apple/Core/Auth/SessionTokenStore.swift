import Foundation

/// Owner of the opaque session token and the moment it expires.
///
/// An `actor`, because the token is mutable state reached from two directions:
/// the auth interceptor (any thread, on every request) and the UI (`@MainActor`).
///
/// This is deliberately **not** the JWT access/refresh pair the rest of the
/// Happenings apps use. The todo backend issues one opaque token, stores only its
/// hash, and rotates it through `RefreshSession` — which authenticates with the
/// *current* token. Three consequences shape this type:
///
/// * There is no claim to decode, so expiry has to be remembered alongside the
///   token (`Session.expires_at`, handed back at sign-in and on every rotation).
/// * The renewal call needs the current token in its header, so the refresher is
///   injected and must use a client **without** the auth interceptor — going
///   through the interceptor would re-enter `currentToken()` and deadlock.
/// * A token near expiry is still valid *right now*. So when renewal fails for a
///   transient reason, the existing token is returned rather than discarded: the
///   app keeps working on a flaky connection instead of appearing signed out.
actor SessionTokenStore: TokenProvider {
    /// A token and the moment the server says it stops working.
    struct Credential: Sendable, Equatable {
        let token: String
        let expiresAt: Date?

        init(token: String, expiresAt: Date?) {
            self.token = token
            self.expiresAt = expiresAt
        }
    }

    /// Outcome of a rotation attempt. Separating `rejected` from `transient` is
    /// what keeps a user signed in through a tunnel: only the former is a real
    /// sign-out.
    enum RenewalOutcome: Sendable {
        case renewed(Credential)
        /// The server refused the token — it is revoked or expired. Sign out.
        case rejected
        /// Network or server trouble. Keep what we have and try again later.
        case transient
    }

    /// Sessions last 30 days server-side. Renewing inside the last week means a
    /// user who opens the app even monthly stays signed in, while a token that
    /// has been sitting unused is not rotated on every single launch.
    static let renewalWindow: TimeInterval = 7 * 24 * 60 * 60

    private static let tokenKey = "session_token"
    private static let expiryKey = "session_expires_at"

    private var credential: Credential?
    private var inFlight: Task<String?, Never>?
    private let renew: @Sendable (_ current: String) async -> RenewalOutcome

    init(renew: @escaping @Sendable (_ current: String) async -> RenewalOutcome) {
        self.renew = renew
        self.credential = Self.load()
    }

    /// True when nothing is stored — used to tell a fresh install from a session
    /// the server has rejected.
    var isSignedOut: Bool { credential == nil }

    /// What the UI shows in the session list without a round-trip.
    var expiresAt: Date? { credential?.expiresAt }

    func store(_ credential: Credential) {
        self.credential = credential
        Keychain.set(credential.token, for: Self.tokenKey)
        if let expiresAt = credential.expiresAt {
            Keychain.set(expiresAt.formatted(Self.iso8601), for: Self.expiryKey)
        } else {
            Keychain.remove(Self.expiryKey)
        }
    }

    func clear() {
        credential = nil
        inFlight?.cancel()
        inFlight = nil
        Keychain.remove(Self.tokenKey)
        Keychain.remove(Self.expiryKey)
    }

    // MARK: TokenProvider

    func currentToken() async -> String? {
        guard let credential else { return nil }
        guard needsRenewal(credential) else { return credential.token }

        // Concurrent callers that arrive during a rotation await the same task,
        // so a screen firing five parallel reads renews once. Rotation
        // invalidates the old token server-side, so overlapping renewals would
        // race to store the winner and leave the loser's token in the Keychain.
        if let inFlight { return await inFlight.value }
        let task = Task { await self.performRenewal(from: credential) }
        inFlight = task
        let token = await task.value
        inFlight = nil
        return token
    }

    private func performRenewal(from credential: Credential) async -> String? {
        switch await renew(credential.token) {
        case let .renewed(fresh):
            store(fresh)
            return fresh.token
        case .rejected:
            clear()
            return nil
        case .transient:
            // Still inside its validity window — send it and let the call
            // succeed. Only an outright rejection signs the user out.
            return credential.token
        }
    }

    private func needsRenewal(_ credential: Credential) -> Bool {
        // An unknown expiry means the server did not say; treat it as fine
        // rather than rotating on every request.
        guard let expiresAt = credential.expiresAt else { return false }
        return expiresAt.timeIntervalSinceNow < Self.renewalWindow
    }

    // MARK: Persistence

    /// `Date.ISO8601FormatStyle` is a `Sendable` value type, unlike
    /// `ISO8601DateFormatter` — which cannot be a shared `static` under strict
    /// concurrency because it carries mutable state.
    private static let iso8601 = Date.ISO8601FormatStyle()

    private static func load() -> Credential? {
        guard let token = Keychain.get(tokenKey), !token.isEmpty else { return nil }
        let expiry = Keychain.get(expiryKey).flatMap { try? Date($0, strategy: iso8601) }
        return Credential(token: token, expiresAt: expiry)
    }

    /// A synchronous launch hint. Reading the actor is `async`, but the root view
    /// has to decide between the sign-in screen and the app shell before the
    /// first `await` or the UI flashes the wrong one.
    static func hasStoredToken() -> Bool {
        Keychain.get(tokenKey)?.isEmpty == false
    }
}
