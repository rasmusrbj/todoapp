import XCTest

/// Launch smoke test.
///
/// Deliberately thin: it proves the app starts, draws, and does not crash on the
/// first frame — the class of failure a unit test cannot see because it never builds
/// a view hierarchy. Behaviour is covered by the unit suite, which is faster and
/// does not need a simulator to settle.
final class LaunchTests: XCTestCase {
    override var continueAfterFailure: Bool {
        get { false }
        set {}
    }

    @MainActor
    func testLaunchesAndShowsSomething() throws {
        let app = XCUIApplication()
        app.launch()

        // Signed out on a clean simulator, so the sign-in screen is what should
        // appear. Waiting on a real element rather than sleeping means this fails with
        // "no sign-in screen" instead of timing out mysteriously.
        let appeared = app.staticTexts.firstMatch.waitForExistence(timeout: 20)
        XCTAssertTrue(appeared, "nothing rendered within 20s of launch")
        XCTAssertFalse(app.staticTexts.allElementsBoundByIndex.isEmpty)
    }

    @MainActor
    func testNoUntranslatedKeysOnTheFirstScreen() throws {
        let app = XCUIApplication()
        app.launch()
        _ = app.staticTexts.firstMatch.waitForExistence(timeout: 20)

        // A missing catalog entry renders as its own key, and a dotted lowercase
        // identifier is unmistakable on screen. Cheap, and it catches the whole class.
        for element in app.staticTexts.allElementsBoundByIndex {
            let label = element.label
            guard label.contains("."), !label.contains(" ") else { continue }
            XCTFail("Untranslated key on screen: \(label)")
        }
    }
}
