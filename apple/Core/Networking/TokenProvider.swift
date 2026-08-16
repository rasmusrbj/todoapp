import Foundation

/// Supplies the bearer token to the network layer, renewing it when it is close
/// to expiring. Implementations must be callable from any isolation domain
/// (hence `Sendable`) — the auth interceptor awaits this on every request.
protocol TokenProvider: Sendable {
    /// The current session token, or `nil` when signed out. A `nil` return sends
    /// the request unauthenticated, which is correct for the public procedures
    /// (login, register, password reset).
    func currentToken() async -> String?
}
