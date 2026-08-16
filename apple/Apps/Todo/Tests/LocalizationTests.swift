import Connect
import Foundation
import SwiftProtobuf
import Testing

@testable import Todoapp

/// Localization parity, checked against the **compiled** catalog in the app bundle
/// rather than the `.xcstrings` source.
///
/// That distinction is the point. Reading the JSON would prove the file has two
/// entries; loading `da.lproj` proves Xcode compiled them, that the keys survived,
/// and that the values are reachable at runtime — which is what a user sees.
///
/// The iOS mirror of the web's `pnpm check:messages`.
@Suite("Localization")
struct LocalizationTests {
    static let languages = ["en", "da"]

    /// A sentinel that cannot collide with real copy, so "not found" is
    /// distinguishable from a translation that happens to equal its key.
    private static let missing = "\u{0}__missing__"

    private static func bundle(for language: String) throws -> Bundle {
        let path = try #require(
            Bundle.main.path(forResource: language, ofType: "lproj"),
            "No \(language).lproj in the app bundle — is \(language) in project.yml knownRegions?"
        )
        return try #require(Bundle(path: path))
    }

    private static func value(_ key: String, language: String) throws -> String? {
        let resolved = try bundle(for: language)
            .localizedString(forKey: key, value: missing, table: nil)
        return resolved == missing ? nil : resolved
    }

    /// Every key in a compiled language, from both files Xcode emits for a String
    /// Catalog: plain entries land in `Localizable.strings`, plural variations in
    /// `Localizable.stringsdict`. Reading only the first would silently skip every
    /// count key.
    private static func compiledKeys(language: String) throws -> Set<String> {
        let directory = try #require(Bundle.main.path(forResource: language, ofType: "lproj"))
        var keys: Set<String> = []
        for file in ["Localizable.strings", "Localizable.stringsdict"] {
            let path = "\(directory)/\(file)"
            guard FileManager.default.fileExists(atPath: path),
                  let table = NSDictionary(contentsOfFile: path) as? [String: Any] else {
                continue
            }
            keys.formUnion(table.keys)
        }
        return keys
    }

    // MARK: Parity

    @Test("Danish and English cover exactly the same keys")
    func parity() throws {
        let english = try Self.compiledKeys(language: "en")
        let danish = try Self.compiledKeys(language: "da")

        #expect(english.count > 300, "only \(english.count) English keys — did the catalog compile?")

        let missingDanish = english.subtracting(danish).sorted()
        let missingEnglish = danish.subtracting(english).sorted()
        #expect(missingDanish.isEmpty, "no Danish for: \(missingDanish.prefix(20))")
        #expect(missingEnglish.isEmpty, "no English for: \(missingEnglish.prefix(20))")
    }

    /// A key rendering as itself is what a missing entry looks like on screen.
    @Test("No translation is just its own key", arguments: languages)
    func noKeyLeaks(language: String) throws {
        for key in try Self.compiledKeys(language: language) where key.contains(".") {
            let resolved = try Self.value(key, language: language)
            #expect(resolved != key, "\(key) renders as its own key in \(language)")
            #expect(resolved?.isEmpty == false, "\(key) is empty in \(language)")
        }
    }

    // MARK: Enum display names

    /// Every enum value the UI can render resolves in both languages.
    ///
    /// The check that catches a raw `TASK_STATUS_DONE` reaching the screen. Display
    /// keys are built at runtime from the proto descriptor, so the compiler cannot
    /// verify them — nothing else does.
    @Test("Every enum value has a name in every language", arguments: languages)
    func enumDisplayNames(language: String) throws {
        let keys = Self.allEnumDisplayKeys
        // A silently empty key list would make every assertion below vacuous.
        #expect(keys.count >= 56, "expected the full enum surface, got \(keys.count)")

        for key in keys {
            let resolved = try Self.value(key, language: language)
            #expect(resolved != nil, "\(key) has no \(language) translation")
            #expect(resolved != key, "\(key) renders as its own key in \(language)")
        }
    }

    /// Collected through `DisplayableEnum`, so a value added to the proto lands here
    /// automatically and fails until it is translated.
    private static var allEnumDisplayKeys: [String] {
        var keys: [String] = ["enum.unknown"]
        keys += Todo_V1_TaskStatus.selectable.map(\.displayKey)
        keys += Todo_V1_TaskPriority.selectable.map(\.displayKey)
        keys += Todo_V1_RecurrenceFrequency.selectable.map(\.displayKey)
        keys += Todo_V1_ListColor.selectable.map(\.displayKey)
        keys += Todo_V1_ListVisibility.selectable.map(\.displayKey)
        keys += Todo_V1_MemberRole.selectable.map(\.displayKey)
        keys += Todo_V1_UserRole.selectable.map(\.displayKey)
        keys += Todo_V1_UserStatus.selectable.map(\.displayKey)
        keys += Todo_V1_Locale.selectable.map(\.displayKey)
        keys += Todo_V1_ThemePreference.selectable.map(\.displayKey)
        keys += Todo_V1_SessionClient.selectable.map(\.displayKey)
        keys += Todo_V1_ActivityAction.selectable.map(\.displayKey)
        return keys
    }

    // MARK: Error messages

    /// Every `ErrorReason` the server can send has a message in both languages.
    ///
    /// `allCases` comes from the generated descriptor, so a reason added to
    /// `errors.proto` fails here until it is translated — which is the whole point of
    /// using the reason as the translation key.
    @Test("Every error reason has a message in every language", arguments: languages)
    func errorMessages(language: String) throws {
        var checked = 0
        for reason in Todo_V1_ErrorReason.allCases where reason != .unspecified {
            // Goes through the real code path — build the wire error, let `AppFailure`
            // map it — rather than duplicating the mapping table in the test.
            let failure = AppFailure.from(Self.wireError(reason: reason))
            #expect(failure.reason == reason, "detail did not round-trip for \(reason)")
            let resolved = try Self.value(failure.messageKey, language: language)
            #expect(
                resolved != nil,
                "\(reason) → \(failure.messageKey) has no \(language) translation"
            )
            checked += 1
        }
        #expect(checked >= 40, "expected the full reason set, got \(checked)")
    }

    @Test("Transport-level failures have messages too", arguments: languages)
    func transportMessages(language: String) throws {
        for key in ["error.network", "error.cancelled", "error.unknown", "error.internalError"] {
            #expect(try Self.value(key, language: language) != nil, "\(key) missing in \(language)")
        }
    }

    /// A `ConnectError` carrying a real serialized `ErrorDetail`, the way the server
    /// sends one.
    static func wireError(
        reason: Todo_V1_ErrorReason,
        field: String = "",
        metadata: [String: String] = [:],
        code: Code = .invalidArgument
    ) -> ConnectError {
        let detail = Todo_V1_ErrorDetail.with {
            $0.reason = reason
            $0.field = field
            $0.metadata = metadata
        }
        return ConnectError(
            code: code,
            message: "developer-facing text that must never reach a person",
            details: [.init(
                type: Todo_V1_ErrorDetail.protoMessageName,
                payload: try? detail.serializedData()
            )]
        )
    }
}
