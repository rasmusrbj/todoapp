import Connect
import Foundation
import Observation
import SwiftUI

/// Owns the signed-in session: sign-in, registration, sign-out, launch restore,
/// and the shared `TodoBackend`.
///
/// The token plumbing lives in `SessionTokenStore` (an actor); this is the
/// `@MainActor` facade the views talk to.
@MainActor
@Observable
final class TodoSession {
    enum Phase: Equatable {
        /// Deciding, on launch, whether a stored token still works.
        case restoring
        case signedOut
        case signedIn
    }

    private(set) var phase: Phase
    /// The signed-in account. The whole `User` — it carries the locale, theme,
    /// role and stats the UI needs, so there is no reason to project it down.
    private(set) var viewer: Todo_V1_User?

    var isWorking = false
    /// Set by an auth screen when a call fails; cleared on the next attempt.
    var failure: AppFailure?

    let tokens: SessionTokenStore
    let backend: TodoBackend

    init() {
        // Renewal has to authenticate with the token it is replacing, so it goes
        // out on a client with **no** auth interceptor and an explicit header.
        // Routing it through the interceptor would call back into the token store
        // that is awaiting this very renewal.
        let renewalClient = Todo_V1_AuthServiceClient(client: ConnectClient.bare())
        let store = SessionTokenStore(renew: { current in
            let response = await renewalClient.refreshSession(
                request: Todo_V1_RefreshSessionRequest(),
                headers: ConnectClient.bearer(current)
            )
            if let error = response.error {
                // Only an outright refusal is a sign-out. Anything else — no
                // network, a 502, a captive portal — leaves the existing token in
                // place, because it has not actually expired yet.
                let reason = AppFailure.from(error)
                return reason.requiresSignIn || error.code == .unauthenticated ? .rejected : .transient
            }
            guard let message = response.message, !message.token.isEmpty else { return .transient }
            return .renewed(.init(
                token: message.token,
                expiresAt: message.session.hasExpiresAt ? message.session.expiresAt.date : nil
            ))
        })
        self.tokens = store
        self.backend = TodoBackend(tokens: store)

        // A synchronous Keychain peek, because the first frame has to show either
        // the sign-in screen or the app — not flash one and then the other.
        self.phase = SessionTokenStore.hasStoredToken() ? .restoring : .signedOut
    }

    /// Test seam: a session wired to an injected backend, already signed in.
    init(backend: TodoBackend, viewer: Todo_V1_User) {
        self.tokens = SessionTokenStore(renew: { _ in .transient })
        self.backend = backend
        self.viewer = viewer
        self.phase = .signedIn
    }

    // MARK: Lifecycle

    /// Validates the stored token on launch and loads the account behind it.
    func restore() async {
        guard phase == .restoring else { return }
        switch await load() {
        case .success:
            phase = .signedIn
        case let .failure(failure):
            // Distinguish "your session is gone" from "the server is not
            // answering". Only the first should throw the user out — signing
            // someone out because their train went into a tunnel is worse than
            // showing them a stale screen.
            //
            // The second check is a separate statement because `await` cannot sit
            // to the right of `||`, and it is only reached when the first is
            // false, which keeps the short-circuit intact.
            let sessionIsGone = failure.requiresSignIn ? true : await tokens.isSignedOut
            if sessionIsGone {
                await signOut()
            } else {
                // Keep the token; show the app and let individual screens report
                // that they could not load.
                phase = .signedIn
            }
        }
    }

    /// Re-reads the account — after editing the profile, or changing language.
    func reloadViewer() async {
        _ = await load()
    }

    private func load() async -> Result<Todo_V1_User, AppFailure> {
        let response = await backend.users.getCurrentUser(request: Todo_V1_GetCurrentUserRequest())
        let result = unwrap(response) { $0.hasUser ? $0.user : nil }
        if case let .success(user) = result { viewer = user }
        return result
    }

    // MARK: Credentials

    func signIn(email: String, password: String) async {
        await perform {
            let request = Todo_V1_LoginRequest.with {
                $0.credentials = .with {
                    $0.email = email
                    $0.password = password
                }
                $0.client = .mobile
            }
            return await self.establish(unwrap(self.backend.auth.login(request: request)) { $0 })
        }
    }

    func register(email: String, password: String, displayName: String, locale: Todo_V1_Locale) async {
        await perform {
            let request = Todo_V1_RegisterRequest.with {
                $0.credentials = .with {
                    $0.email = email
                    $0.password = password
                }
                $0.displayName = displayName
                $0.locale = locale
                $0.timeZone = TimeZone.current.identifier
                $0.client = .mobile
            }
            return await self.establish(unwrap(self.backend.auth.register(request: request)) { $0 })
        }
    }

    /// Starts the forgot-password flow. The server always reports success, so a
    /// stranger cannot learn whether an address is registered from the response.
    func requestPasswordReset(email: String, locale: Todo_V1_Locale) async -> Bool {
        await perform {
            let request = Todo_V1_RequestPasswordResetRequest.with {
                $0.email = email
                $0.locale = locale
            }
            switch unwrap(await self.backend.auth.requestPasswordReset(request: request)) {
            case .success: return true
            case let .failure(failure): self.failure = failure; return false
            }
        }
    }

    /// Changes the password. The server revokes every other session and hands back
    /// a fresh token for this one, which has to replace what is in the Keychain or
    /// the very next call fails.
    func changePassword(current: String, new: String) async -> Bool {
        await perform {
            let request = Todo_V1_ChangePasswordRequest.with {
                $0.currentPassword = current
                $0.newPassword = new
            }
            switch unwrap(await self.backend.auth.changePassword(request: request)) {
            case let .success(message):
                await self.tokens.store(.init(
                    token: message.token,
                    expiresAt: message.session.hasExpiresAt ? message.session.expiresAt.date : nil
                ))
                return true
            case let .failure(failure):
                self.failure = failure
                return false
            }
        }
    }

    func signOut() async {
        // Best effort: tell the server so the session disappears from the other
        // devices' session list. A failure here must not strand the user in a
        // signed-in state they asked to leave, so the local clear is unconditional.
        _ = await backend.auth.logout(request: Todo_V1_LogoutRequest())
        await tokens.clear()
        viewer = nil
        failure = nil
        phase = .signedOut
    }

    /// Called when any screen sees a failure that means the session is gone.
    func handleExpiredSession() async {
        guard phase == .signedIn else { return }
        await signOut()
    }

    // MARK: Helpers

    /// Stores the token and account from a login/register response.
    private func establish<T>(_ result: Result<T, AppFailure>) async -> Bool where T: SessionEstablishing {
        switch result {
        case let .success(message):
            await tokens.store(.init(
                token: message.token,
                expiresAt: message.session.hasExpiresAt ? message.session.expiresAt.date : nil
            ))
            viewer = message.user
            phase = .signedIn
            return true
        case let .failure(failure):
            self.failure = failure
            return false
        }
    }

    /// Wraps an auth action in the shared working/error lifecycle.
    @discardableResult
    private func perform(_ body: () async -> Bool) async -> Bool {
        isWorking = true
        failure = nil
        defer { isWorking = false }
        return await body()
    }
}

/// The two responses that hand back a brand-new session, so `establish` can take
/// either without a duplicate implementation.
protocol SessionEstablishing {
    var user: Todo_V1_User { get }
    var session: Todo_V1_Session { get }
    var token: String { get }
}

extension Todo_V1_LoginResponse: SessionEstablishing {}
extension Todo_V1_RegisterResponse: SessionEstablishing {}
