import Connect
import Foundation

/// The four Connect service clients, over one shared `ProtocolClient` so the auth
/// interceptor puts a current token on every call.
///
/// `Sendable`, so view models on any actor can hold it.
struct TodoBackend: Sendable {
    let auth: Todo_V1_AuthServiceClient
    let users: Todo_V1_UserServiceClient
    let lists: Todo_V1_ListServiceClient
    let tasks: Todo_V1_TaskServiceClient

    /// Production path: an authenticated client. Delegates to `init(client:)`.
    init(tokens: TokenProvider, baseURL: URL = AppConfig.apiBaseURL) {
        self.init(client: ConnectClient.authenticated(baseURL: baseURL, tokens: tokens))
    }

    /// Wraps a pre-built client. An additive seam: tests inject a fake transport
    /// and drive the view models with no live server and no change to the
    /// authenticated path above.
    init(client: any ProtocolClientInterface) {
        self.auth = .init(client: client)
        self.users = .init(client: client)
        self.lists = .init(client: client)
        self.tasks = .init(client: client)
    }
}
