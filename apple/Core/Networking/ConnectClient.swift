import Connect
import Foundation

/// Builds ConnectRPC `ProtocolClient`s against the todo backend.
///
/// Both variants speak the Connect protocol with the binary codec. The server
/// accepts Connect, gRPC and gRPC-Web on the same handler, so this is a choice
/// about the client only — `ProtoCodec` over `JSONCodec` because nothing here
/// needs a human-readable body and the binary encoding is smaller and faster.
enum ConnectClient {
    /// The app's client: the auth interceptor puts a current token on every call.
    static func authenticated(
        baseURL: URL = AppConfig.apiBaseURL,
        tokens: TokenProvider
    ) -> ProtocolClient {
        ProtocolClient(
            httpClient: URLSessionHTTPClient(),
            config: ProtocolClientConfig(
                host: baseURL.absoluteString,
                networkProtocol: .connect,
                codec: ProtoCodec(),
                interceptors: [InterceptorFactory { _ in AuthInterceptor(tokens: tokens) }]
            )
        )
    }

    /// A client with no auth interceptor.
    ///
    /// Two callers need this. Sign-in and password reset carry their credential
    /// in the request body, so there is no token to attach. Session renewal *does*
    /// need a token — but it needs the current one passed explicitly via
    /// `headers:`, because routing it through the interceptor would call back into
    /// the token store that is waiting on the renewal.
    static func bare(baseURL: URL = AppConfig.apiBaseURL) -> ProtocolClient {
        ProtocolClient(
            httpClient: URLSessionHTTPClient(),
            config: ProtocolClientConfig(
                host: baseURL.absoluteString,
                networkProtocol: .connect,
                codec: ProtoCodec()
            )
        )
    }

    /// Headers carrying an explicit bearer token, for calls made on the `bare`
    /// client that still need to authenticate.
    static func bearer(_ token: String) -> Headers {
        ["Authorization": ["Bearer \(token)"]]
    }
}
