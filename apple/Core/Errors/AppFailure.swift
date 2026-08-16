import Connect
import Foundation
import SwiftUI

/// A failure, ready to put in front of a person.
///
/// The server sends an English developer message plus a machine-readable
/// `todo.v1.ErrorReason` in a Protobuf detail. Only the reason is used — it picks
/// the translation, so the same failure reads natively in Danish and in English
/// and adding a language needs no server change. The developer message is never
/// shown; it goes to the log.
struct AppFailure: Error, Equatable, Sendable {
    /// Key into the String Catalog.
    let messageKey: String
    /// Single substitution for the message's `%@`, when it has one.
    let argument: String?
    /// Which request field was at fault, so a form can point at the right input.
    let field: String?
    /// The wire reason, when the server sent one.
    let reason: Todo_V1_ErrorReason?

    init(
        messageKey: String,
        argument: String? = nil,
        field: String? = nil,
        reason: Todo_V1_ErrorReason? = nil
    ) {
        self.messageKey = messageKey
        self.argument = argument
        self.field = field
        self.reason = reason
    }

    /// The session is gone and the only way forward is signing in again. The root
    /// view watches for this and drops to the sign-in screen.
    var requiresSignIn: Bool {
        reason == .notAuthenticated || reason == .sessionExpired
    }

    /// Resolved text in the app's current language.
    func message(locale: Locale) -> String {
        Localized.string(messageKey, locale: locale, argument: argument)
    }

    // MARK: Building

    /// Reads any error thrown or returned by a Connect call.
    static func from(_ error: ConnectError) -> AppFailure {
        // A detail is present on everything our own handlers raise.
        if let detail = (error.unpackedDetails() as [Todo_V1_ErrorDetail]).first {
            return AppFailure(
                messageKey: Self.key(for: detail.reason),
                argument: Self.argument(for: detail.reason, metadata: detail.metadata),
                field: detail.field.isEmpty ? nil : detail.field,
                reason: detail.reason
            )
        }

        // No detail means it did not come from a handler: a timeout, a
        // cancellation, or something between the app and the server.
        switch error.code {
        case .unauthenticated:
            return AppFailure(messageKey: "error.notAuthenticated", reason: .notAuthenticated)
        case .unavailable, .deadlineExceeded:
            return AppFailure(messageKey: "error.network")
        case .canceled:
            return AppFailure(messageKey: "error.cancelled")
        default:
            return AppFailure(messageKey: "error.unknown")
        }
    }

    /// The catch-all for a transport failure with no `ConnectError` at all.
    static let network = AppFailure(messageKey: "error.network")

    /// A locally-detected problem, e.g. a form field the app can reject without
    /// a round-trip.
    static func local(_ messageKey: String, field: String? = nil) -> AppFailure {
        AppFailure(messageKey: messageKey, field: field)
    }

    /// Reason → translation key.
    ///
    /// Exhaustive on purpose: a new `ErrorReason` in the proto stops this file
    /// compiling, which is when it is cheapest to write the Danish and English
    /// text. `ErrorMessageTests` checks every case resolves in both languages.
    private static func key(for reason: Todo_V1_ErrorReason) -> String {
        switch reason {
        // Authentication and accounts.
        case .invalidCredentials: "error.invalidCredentials"
        case .emailAlreadyRegistered: "error.emailAlreadyRegistered"
        case .passwordTooWeak: "error.passwordTooWeak"
        case .sessionExpired: "error.sessionExpired"
        case .notAuthenticated: "error.notAuthenticated"
        case .accountSuspended: "error.accountSuspended"
        case .accountDeactivated: "error.accountDeactivated"
        case .emailNotVerified: "error.emailNotVerified"
        case .tokenInvalid: "error.tokenInvalid"
        case .tokenExpired: "error.tokenExpired"
        case .tokenAlreadyUsed: "error.tokenAlreadyUsed"
        case .currentPasswordIncorrect: "error.currentPasswordIncorrect"

        // Authorization.
        case .permissionDenied: "error.permissionDenied"
        case .adminRequired: "error.adminRequired"
        case .ownerRequired: "error.ownerRequired"
        case .cannotRemoveOwner: "error.cannotRemoveOwner"
        case .cannotDemoteSelf: "error.cannotDemoteSelf"

        // Existence.
        case .userNotFound: "error.userNotFound"
        case .listNotFound: "error.listNotFound"
        case .taskNotFound: "error.taskNotFound"
        case .labelNotFound: "error.labelNotFound"
        case .commentNotFound: "error.commentNotFound"
        case .subtaskNotFound: "error.subtaskNotFound"
        case .memberNotFound: "error.memberNotFound"
        case .sessionNotFound: "error.sessionNotFound"

        // Validation.
        case .validationFailed: "error.validationFailed"
        case .fieldRequired: "error.fieldRequired"
        case .fieldTooLong: "error.fieldTooLong"
        case .invalidEmail: "error.invalidEmail"
        case .invalidEnumValue: "error.invalidEnumValue"
        case .invalidTimeZone: "error.invalidTimeZone"
        case .labelNameTaken: "error.labelNameTaken"
        case .memberAlreadyAdded: "error.memberAlreadyAdded"
        case .labelNotOnList: "error.labelNotOnList"
        case .assigneeNotAMember: "error.assigneeNotAMember"
        case .invalidDateRange: "error.invalidDateRange"
        case .noChangeRequested: "error.noChangeRequested"

        // Throttling and conflict.
        case .rateLimited: "error.rateLimited"
        case .conflict: "error.conflict"

        case .internal: "error.internalError"
        case .unspecified, .UNRECOGNIZED: "error.unknown"
        }
    }

    /// Which metadata entry fills a message's single `%@`.
    ///
    /// Only the reasons whose text is useless without a number appear here. The
    /// server sends more metadata than this uses; the rest is for the log.
    private static func argument(
        for reason: Todo_V1_ErrorReason,
        metadata: [String: String]
    ) -> String? {
        switch reason {
        case .fieldTooLong: metadata["max_length"]
        case .passwordTooWeak: metadata["min_length"]
        case .rateLimited: metadata["retry_after_seconds"]
        default: nil
        }
    }
}

// MARK: - Calling

/// Unwraps a Connect response into a value or an `AppFailure`.
///
/// connect-swift hands back a `ResponseMessage` carrying *either* a message or an
/// error rather than throwing, which is easy to half-check: reading `.message`
/// and ignoring `.error` turns a refusal into an empty screen. Funnelling every
/// call through here means that cannot happen.
func unwrap<Output: ProtobufMessage, Value>(
    _ response: ResponseMessage<Output>,
    _ extract: (Output) -> Value?
) -> Result<Value, AppFailure> {
    if let error = response.error {
        return .failure(.from(error))
    }
    guard let message = response.message, let value = extract(message) else {
        // A 200 with nothing in it. Not expected, but an empty screen with no
        // explanation is worse than saying so.
        return .failure(AppFailure(messageKey: "error.unknown"))
    }
    return .success(value)
}

/// The common case: the whole response message is the value.
func unwrap<Output: ProtobufMessage>(
    _ response: ResponseMessage<Output>
) -> Result<Output, AppFailure> {
    unwrap(response) { $0 }
}
