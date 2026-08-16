import XCTest

/// End-to-end against a **running** dev backend.
///
/// Separate from `LaunchTests` and skipped unless opted into, because it needs
/// `make dev-backend` and a seeded database. Keeping it out of the default run means
/// `make ios-test` stays hermetic; running it is how the Connect wiring, the session
/// token and the real screens get verified together, which no unit test can do.
///
///     make ios-test-live
///
/// The opt-in is `TEST_RUNNER_TODOAPP_LIVE_TESTS=1`, not a bare env var: a UI test
/// runs in its own process, and xcodebuild forwards only variables carrying the
/// `TEST_RUNNER_` prefix (stripping it) into that process. A plain
/// `TODOAPP_LIVE_TESTS=1` reaches xcodebuild and stops there, so the tests silently
/// skip — which looks exactly like passing.
final class LiveFlowTests: XCTestCase {
    override var continueAfterFailure: Bool {
        get { false }
        set {}
    }

    /// The account `make seed` created, passed in by `make ios-test-live`.
    ///
    /// Not a constant in the source: this repository is public, and a real address
    /// beside a password is the one thing it should not carry. The `TEST_RUNNER_`
    /// prefix is how xcodebuild forwards a variable into the UI-test runner process.
    private static var email: String {
        ProcessInfo.processInfo.environment["TODOAPP_DEMO_EMAIL"] ?? ""
    }

    private static var password: String {
        ProcessInfo.processInfo.environment["TODOAPP_DEMO_PASSWORD"] ?? ""
    }

    /// Launches signed out, pointed at the local backend and in English so the
    /// assertions below can name buttons.
    @MainActor
    private func launchApp() throws -> XCUIApplication {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["TODOAPP_LIVE_TESTS"] == "1",
            "Run `make ios-test-live` with the backend up to exercise the live flow."
        )
        try XCTSkipUnless(
            !Self.email.isEmpty && !Self.password.isEmpty,
            "No demo credentials. Run `make seed`, then `make ios-test-live`."
        )
        let app = XCUIApplication()
        ignorePasswordSavePrompt(app)
        // Loopback only works in the simulator, which shares the Mac's network stack.
        // On a real phone 127.0.0.1 is the phone, so the runner passes the Mac's Bonjour
        // name through `TEST_RUNNER_TODOAPP_API_BASE_URL` (see `make ios-test-live-device`).
        app.launchEnvironment["TODOAPP_API_BASE_URL"] =
            ProcessInfo.processInfo.environment["TODOAPP_API_BASE_URL"] ?? "http://127.0.0.1:8081"
        // English *before* sign-in only. After it, the app adopts the account's
        // language from the server — which is the point of storing it there — so the
        // signed-in assertions below go through accessibility identifiers rather than
        // visible text. Forcing the simulator language cannot override an account.
        app.launchArguments += ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        try signOutIfSignedIn(app)
        return app
    }

    /// Handles iOS's "Save this password?" prompt for the rest of the test.
    ///
    /// It appears over the app after a successful sign-in. Being a *system* dialog it
    /// swallows every tap aimed at the shell behind it, so without this the next
    /// assertion fails as "the Lists tab did not load" — pointing at entirely the wrong
    /// thing. A monitor rather than a one-off poll, because the dialog can arrive at any
    /// point after the credential is submitted, including mid-tap.
    @MainActor
    private func ignorePasswordSavePrompt(_ app: XCUIApplication) {
        addUIInterruptionMonitor(withDescription: "Save password prompt") { alert in
            for label in ["Not Now", "Ikke nu", "Cancel"] {
                let button = alert.buttons[label]
                if button.exists {
                    button.tap()
                    return true
                }
            }
            return false
        }
    }

    /// Leaves the app on the sign-in screen, whichever state it launched in.
    ///
    /// Necessary because the simulator does **not** clear Keychain items when an app is
    /// uninstalled — so `simctl uninstall` leaves a perfectly valid session token behind
    /// and the next launch restores it. A test that assumed a signed-out start failed
    /// with "sign-in screen never appeared", which reads like a rendering bug rather
    /// than leftover state.
    @MainActor
    private func signOutIfSignedIn(_ app: XCUIApplication) throws {
        let signIn = app.buttons["auth.submit"]
        let account = app.buttons["nav.account"]

        // Whichever appears first tells us which state we are in.
        let deadline = Date().addingTimeInterval(25)
        while Date() < deadline {
            if signIn.exists { return }
            if account.exists { break }
            usleep(200_000)
        }
        guard account.exists else {
            XCTFail("app reached neither the sign-in screen nor the signed-in shell")
            return
        }

        account.tap()
        XCTAssertTrue(app.descendants(matching: .any)["screen.settings"].firstMatch.waitForExistence(timeout: 15))
        app.buttons.matching(identifier: "settings.signOut").firstMatch.tap()
        let confirm = app.sheets.buttons.firstMatch
        if confirm.waitForExistence(timeout: 5) { confirm.tap() }
        XCTAssertTrue(signIn.waitForExistence(timeout: 15), "sign-out did not return to sign-in")
    }

    @MainActor
    func testSignInLoadsTheDashboardAndSettings() throws {
        let app = try launchApp()

        // --- Sign in ------------------------------------------------------
        let emailField = app.textFields["auth.email"]
        XCTAssertTrue(emailField.waitForExistence(timeout: 20), "sign-in screen never appeared")
        emailField.tap()
        emailField.typeText(Self.email)

        let passwordField = app.secureTextFields["auth.password"]
        XCTAssertTrue(passwordField.exists, "password field missing")
        passwordField.tap()
        passwordField.typeText(Self.password)

        app.buttons["auth.submit"].tap()
        // A tap on the app is what gives the interruption monitor a chance to run.
        app.tap()

        // --- Today --------------------------------------------------------
        // Reaching this screen means the token was stored, the auth interceptor
        // attached it, and `GetCurrentUser` came back — the whole Connect path.
        XCTAssertTrue(
            app.descendants(matching: .any)["screen.today"].firstMatch.waitForExistence(timeout: 20),
            "did not reach the Today screen"
        )

        // --- Content actually loaded --------------------------------------
        // The seeded database has tasks, so rows must be present and tappable. Opening
        // one proves `GetTask` plus the four reads its screen fans out into.
        let firstRow = app.scrollViews.buttons.firstMatch
        XCTAssertTrue(firstRow.waitForExistence(timeout: 15), "the dashboard rendered no task rows")
        firstRow.tap()

        // Back to the dashboard.
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(
            app.descendants(matching: .any)["screen.today"].firstMatch.waitForExistence(timeout: 15),
            "did not return to the dashboard"
        )

        // --- Settings, reached through the account avatar ------------------
        app.buttons["nav.account"].firstMatch.tap()
        XCTAssertTrue(
            app.descendants(matching: .any)["screen.settings"].firstMatch.waitForExistence(timeout: 15),
            "the account button did not open Settings"
        )

        // Switching tabs is deliberately NOT asserted here. On iOS 26 a
        // `.sidebarAdaptable` TabView renders no `TabBar` element and its tab buttons
        // report `isHittable == false`, so XCUITest cannot drive them — verified by
        // dumping the hierarchy, not assumed. The other four screens are covered by the
        // unit suite (their models, over a fake transport) and by
        // `make ios-screenshots`, rather than by a test that would have to fake a tap
        // the platform does not expose.

        // --- Sign out, so the next run starts from the sign-in screen ------
        // The sign-out row and its confirmation share a label; the confirmation dialog
        // is a sheet, so scoping to it avoids tapping the row twice.
        app.buttons.matching(identifier: "settings.signOut").firstMatch.tap()
        let confirm = app.sheets.buttons.firstMatch
        if confirm.waitForExistence(timeout: 5) { confirm.tap() }

        XCTAssertTrue(
            app.buttons["auth.submit"].waitForExistence(timeout: 15),
            "did not return to the sign-in screen"
        )
    }

    /// The failure path: wrong credentials must produce the translated message, not a
    /// developer string and not a blank screen.
    @MainActor
    func testWrongPasswordShowsATranslatedMessage() throws {
        let app = try launchApp()

        let emailField = app.textFields["auth.email"]
        XCTAssertTrue(emailField.waitForExistence(timeout: 20))
        emailField.tap()
        emailField.typeText(Self.email)

        let passwordField = app.secureTextFields["auth.password"]
        passwordField.tap()
        passwordField.typeText("definitely-not-the-password")

        app.buttons["auth.submit"].tap()

        let banner = app.descendants(matching: .any)["error.inline"].firstMatch
        XCTAssertTrue(banner.waitForExistence(timeout: 15), "no error was shown")

        // The wording depends on the language the app is currently in — which persists
        // from the last signed-in account — so this checks that the message is real
        // prose rather than a leaked key, in whichever language it landed.
        let text = banner.label
        XCTAssertFalse(text.isEmpty, "the error banner is empty")
        XCTAssertFalse(
            text.hasPrefix("error."),
            "the error rendered its own key instead of a translation: \(text)"
        )
        // And it must still be the sign-in screen, not a half-authenticated shell.
        XCTAssertTrue(app.buttons["auth.submit"].exists)
    }
}
