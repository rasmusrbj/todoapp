import Connect
import Foundation
import SwiftProtobuf

@testable import Todoapp

/// A `ProtocolClient` backed by canned responses, so view models can be driven
/// without a server.
///
/// This works because `TodoBackend` has an additive `init(client:)` seam — the
/// authenticated path delegates to it — so nothing in production changes to make the
/// models testable.
///
/// Responses are keyed by RPC method name (the last path component of the request
/// URL), which is what a Connect request carries: `POST /todo.v1.TaskService/ListTasks`.
extension TodoBackend {
    /// Unary responses per method name. An unmapped method returns an empty message
    /// of the expected type, which is a valid response and keeps a model from
    /// crashing on a call the test did not care about.
    static func fake(_ responses: [String: any Message]) -> TodoBackend {
        TodoBackend(client: ProtocolClient(
            httpClient: FakeHTTPClient(responses: responses, failure: nil),
            config: ProtocolClientConfig(
                host: "https://fake.invalid",
                networkProtocol: .connect,
                codec: ProtoCodec()
            )
        ))
    }

    /// Fails every call with one code — for testing the error and retry paths.
    static func fake(failWith code: Code) -> TodoBackend {
        TodoBackend(client: ProtocolClient(
            httpClient: FakeHTTPClient(responses: [:], failure: code),
            config: ProtocolClientConfig(
                host: "https://fake.invalid",
                networkProtocol: .connect,
                codec: ProtoCodec()
            )
        ))
    }

    /// Fails every call with a real `ErrorDetail`, the way the server does.
    static func fake(failWith reason: Todo_V1_ErrorReason, code: Code = .invalidArgument) -> TodoBackend {
        let detail = Todo_V1_ErrorDetail.with { $0.reason = reason }
        return TodoBackend(client: ProtocolClient(
            httpClient: FakeHTTPClient(
                responses: [:],
                failure: code,
                errorDetail: try? detail.serializedData()
            ),
            config: ProtocolClientConfig(
                host: "https://fake.invalid",
                networkProtocol: .connect,
                codec: ProtoCodec()
            )
        ))
    }
}

/// Answers Connect unary requests from a dictionary, in the Connect wire format.
///
/// A envelope-free body with `Content-Type: application/proto` is what the Connect
/// protocol uses for unary, so the response only needs the serialized message and the
/// right header for `ProtocolClient` to decode it.
private final class FakeHTTPClient: HTTPClientInterface, @unchecked Sendable {
    private let responses: [String: any Message]
    private let failure: Code?
    private let errorDetail: Data?

    init(responses: [String: any Message], failure: Code?, errorDetail: Data? = nil) {
        self.responses = responses
        self.failure = failure
        self.errorDetail = errorDetail
    }

    func unary(
        request: HTTPRequest<Data?>,
        onMetrics: @escaping @Sendable (HTTPMetrics) -> Void,
        onResponse: @escaping @Sendable (HTTPResponse) -> Void
    ) -> Cancelable {
        let method = request.url.lastPathComponent

        if let failure {
            var body: [String: Any] = ["code": Self.wireCode(failure), "message": "fake failure"]
            if let errorDetail {
                body["details"] = [[
                    "type": Todo_V1_ErrorDetail.protoMessageName,
                    "value": errorDetail.base64EncodedString(),
                ]]
            }
            let data = try? JSONSerialization.data(withJSONObject: body)
            onResponse(HTTPResponse(
                code: failure,
                headers: ["content-type": ["application/json"]],
                message: data,
                trailers: [:],
                error: nil,
                tracingInfo: nil
            ))
            return Cancelable {}
        }

        // An unmapped method answers with an empty body, which decodes to a
        // default-valued message of whatever type the caller expects.
        let payload = responses[method].flatMap { try? $0.serializedData() } ?? Data()
        onResponse(HTTPResponse(
            code: .ok,
            headers: ["content-type": ["application/proto"]],
            message: payload,
            trailers: [:],
            error: nil,
            tracingInfo: nil
        ))
        return Cancelable {}
    }

    func stream(
        request: HTTPRequest<Data?>,
        responseCallbacks: ResponseCallbacks
    ) -> RequestCallbacks<Data> {
        // No RPC in this app streams; a test that reaches here is testing something
        // that does not exist yet.
        responseCallbacks.receiveClose(.unimplemented, [:], nil)
        return RequestCallbacks(cancel: {}, sendData: { _ in }, sendClose: {})
    }

    /// The Connect protocol's JSON error body names the code, not its number.
    private static func wireCode(_ code: Code) -> String {
        switch code {
        case .unauthenticated: "unauthenticated"
        case .permissionDenied: "permission_denied"
        case .notFound: "not_found"
        case .invalidArgument: "invalid_argument"
        case .unavailable: "unavailable"
        case .alreadyExists: "already_exists"
        case .resourceExhausted: "resource_exhausted"
        case .failedPrecondition: "failed_precondition"
        default: "unknown"
        }
    }
}
