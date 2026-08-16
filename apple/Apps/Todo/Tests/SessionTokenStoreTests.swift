import Foundation
import Testing

@testable import Todoapp

/// The session token's renewal rules.
///
/// Worth testing directly rather than through the UI, because every case here is a
/// way to get someone signed out who should not be — the failure mode users notice
/// and nobody reproduces on demand.
///
/// The store persists to the Keychain, so each test clears it first: a leftover token
/// from a previous run would make a "signed out" assertion pass for the wrong reason.
@Suite("Session token store", .serialized)
struct SessionTokenStoreTests {
    /// Fresh state for a test. The Keychain is process-wide, so this is not optional.
    private func clearKeychain() {
        Keychain.remove("session_token")
        Keychain.remove("session_expires_at")
    }

    private func store(
        renew: @escaping @Sendable (String) async -> SessionTokenStore.RenewalOutcome = { _ in .transient }
    ) -> SessionTokenStore {
        clearKeychain()
        return SessionTokenStore(renew: renew)
    }

    @Test("A fresh install has no token")
    func emptyStore() async {
        let store = store()
        #expect(await store.isSignedOut)
        #expect(await store.currentToken() == nil)
    }

    @Test("A token far from expiry is returned untouched")
    func noRenewalWhenFresh() async {
        // A `Counter` actor rather than a captured `var`: the renewal closure is
        // `@Sendable` and runs off this test's isolation, so mutating a local from it
        // is a data race Swift 6 rejects outright.
        let renewals = Counter()
        let store = store(renew: { _ in
            await renewals.increment()
            return .transient
        })
        await store.store(.init(token: "fresh", expiresAt: .now.addingTimeInterval(30 * 24 * 3600)))

        #expect(await store.currentToken() == "fresh")
        let count = await renewals.value
        #expect(count == 0, "a token with 30 days left must not be rotated")
    }

    @Test("A token inside the renewal window is rotated")
    func renewsNearExpiry() async {
        let store = store(renew: { current in
            #expect(current == "old", "renewal must present the token it is replacing")
            return .renewed(.init(token: "new", expiresAt: .now.addingTimeInterval(30 * 24 * 3600)))
        })
        // Three days left — inside the seven-day window.
        await store.store(.init(token: "old", expiresAt: .now.addingTimeInterval(3 * 24 * 3600)))

        #expect(await store.currentToken() == "new")
        // The rotated token has to be persisted, or the next launch presents the old
        // one, which the server has already invalidated.
        #expect(Keychain.get("session_token") == "new")
    }

    /// The behaviour that keeps someone signed in on a bad connection.
    @Test("A transient renewal failure keeps the existing token")
    func transientFailureKeepsToken() async {
        let store = store(renew: { _ in .transient })
        await store.store(.init(token: "still-valid", expiresAt: .now.addingTimeInterval(3 * 24 * 3600)))

        // Still inside its validity window, so it is the right thing to send. Only an
        // outright rejection is a sign-out.
        #expect(await store.currentToken() == "still-valid")
        #expect(await store.isSignedOut == false)
    }

    @Test("A rejected token signs the session out")
    func rejectionClearsToken() async {
        let store = store(renew: { _ in .rejected })
        await store.store(.init(token: "revoked", expiresAt: .now.addingTimeInterval(3600)))

        #expect(await store.currentToken() == nil)
        #expect(await store.isSignedOut)
        #expect(Keychain.get("session_token") == nil, "a rejected token must not survive in the Keychain")
    }

    /// Rotation invalidates the old token server-side, so two concurrent renewals
    /// would race and one would store a token the server has already replaced.
    @Test("Concurrent callers share one renewal")
    func renewalIsDeduplicated() async {
        let counter = Counter()
        let store = store(renew: { _ in
            await counter.increment()
            // Long enough that every caller below arrives while it is in flight.
            try? await Task.sleep(for: .milliseconds(120))
            return .renewed(.init(token: "rotated", expiresAt: .now.addingTimeInterval(30 * 24 * 3600)))
        })
        await store.store(.init(token: "old", expiresAt: .now.addingTimeInterval(3600)))

        let tokens = await withTaskGroup(of: String?.self) { group in
            for _ in 0..<8 {
                group.addTask { await store.currentToken() }
            }
            var results: [String?] = []
            for await token in group { results.append(token) }
            return results
        }

        #expect(tokens.allSatisfy { $0 == "rotated" })
        // Read once into a local: `#expect` wraps its message in a non-async
        // autoclosure, so an `await` cannot appear inside it.
        let renewals = await counter.value
        #expect(renewals == 1, "8 concurrent reads triggered \(renewals) renewals")
    }

    @Test("An unknown expiry is not treated as expiring")
    func missingExpiryDoesNotRenew() async {
        let renewals = Counter()
        let store = store(renew: { _ in
            await renewals.increment()
            return .rejected
        })
        // The server did not say when it expires. Rotating on every single request
        // would be worse than trusting it.
        await store.store(.init(token: "no-expiry", expiresAt: nil))

        #expect(await store.currentToken() == "no-expiry")
        let count = await renewals.value
        #expect(count == 0)
    }

    @Test("A stored token survives a new store instance")
    func persistsAcrossLaunches() async {
        let first = store()
        let expiry = Date.now.addingTimeInterval(30 * 24 * 3600)
        await first.store(.init(token: "persisted", expiresAt: expiry))

        // Simulates the next launch: a brand-new store reading the Keychain.
        let second = SessionTokenStore(renew: { _ in .transient })
        #expect(await second.currentToken() == "persisted")
        #expect(SessionTokenStore.hasStoredToken(), "the synchronous launch hint must agree")

        let restored = try? #require(await second.expiresAt)
        // Persisted as an ISO 8601 string, so sub-second precision is lost — that is
        // fine for a 30-day window, but the assertion has to allow for it.
        #expect(abs((restored ?? .distantPast).timeIntervalSince(expiry)) < 1)
    }

    @Test("Clearing removes both the token and its expiry")
    func clearRemovesEverything() async {
        let store = store()
        await store.store(.init(token: "gone", expiresAt: .now.addingTimeInterval(3600)))
        await store.clear()

        #expect(Keychain.get("session_token") == nil)
        #expect(Keychain.get("session_expires_at") == nil)
        #expect(SessionTokenStore.hasStoredToken() == false)
    }
}

/// A counter safe to bump from the renewal closure, which runs off the test's actor.
private actor Counter {
    private(set) var value = 0
    func increment() { value += 1 }
}
