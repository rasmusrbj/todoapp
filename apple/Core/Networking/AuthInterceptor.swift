import Connect
import Foundation

/// Attaches `Authorization: Bearer <token>` to every outbound call, asking the
/// `TokenProvider` for a token first so a renewal happens inline rather than
/// being threaded through call sites.
///
/// Connect's interceptor chain resumes through `proceed`, which is what makes the
/// `await` here possible at all — the request is held while the token is
/// resolved.
final class AuthInterceptor: Interceptor, UnaryInterceptor {
    private let tokens: TokenProvider

    init(tokens: TokenProvider) {
        self.tokens = tokens
    }

    @Sendable
    func handleUnaryRequest<Message: ProtobufMessage>(
        _ request: HTTPRequest<Message>,
        proceed: @escaping @Sendable (Result<HTTPRequest<Message>, ConnectError>) -> Void
    ) {
        Task {
            let token = await tokens.currentToken()
            proceed(.success(request.authorized(with: token)))
        }
    }
}

extension HTTPRequest {
    /// A copy carrying the bearer token. A no-op when signed out, so the public
    /// procedures (login, register, password reset) still work.
    func authorized(with token: String?) -> HTTPRequest<Input> {
        guard let token, !token.isEmpty else { return self }
        var headers = self.headers
        headers["Authorization"] = ["Bearer \(token)"]
        return HTTPRequest(
            url: url,
            headers: headers,
            message: message,
            method: method,
            trailers: trailers,
            idempotencyLevel: idempotencyLevel
        )
    }
}
