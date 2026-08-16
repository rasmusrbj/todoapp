import XCTest

/// Captures every screen as a PNG, for reviewing the design without a device in hand.
///
/// Not an assertion suite — it writes files and checks only that something rendered.
/// It exists because the iOS 26 floating tab bar reports `isHittable == false`, so tabs
/// cannot be driven through the element API; tapping the window at the tab's position
/// works, which is fine for producing screenshots even though it is too brittle to
/// hang assertions on.
///
///     make ios-screenshots
final class ScreenshotTests: XCTestCase {
    /// The seeded account, from the runner environment — see `LiveFlowTests`.
    private static var email: String {
        ProcessInfo.processInfo.environment["TODOAPP_DEMO_EMAIL"] ?? ""
    }

    private static var password: String {
        ProcessInfo.processInfo.environment["TODOAPP_DEMO_PASSWORD"] ?? ""
    }

    /// Where the PNGs go. The test process writes them directly, because an XCTest
    /// attachment is buried inside the `.xcresult` bundle.
    private var outputDirectory: URL {
        let path = ProcessInfo.processInfo.environment["TODOAPP_SCREENSHOT_DIR"]
            ?? NSTemporaryDirectory() + "todoapp-screenshots"
        return URL(fileURLWithPath: path, isDirectory: true)
    }

    @MainActor
    func testCaptureEveryScreen() throws {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["TODOAPP_SCREENSHOTS"] == "1",
            "Run `make ios-screenshots` with the backend up."
        )
        try XCTSkipUnless(
            !Self.email.isEmpty && !Self.password.isEmpty,
            "No demo credentials. Run `make seed` first."
        )
        try FileManager.default.createDirectory(
            at: outputDirectory,
            withIntermediateDirectories: true
        )

        // Sign in once, then relaunch onto each tab. Relaunching is what makes this
        // reliable: the iOS 26 tab bar cannot be tapped from XCUITest, so `--initial-tab`
        // (a DEBUG-only launch argument) is the only way to reach the other four screens.
        // The session persists in the Keychain, so each relaunch is already signed in.
        let app = launch(tab: nil)

        if app.buttons["auth.submit"].waitForExistence(timeout: 20) {
            capture(named: "01-signin")
            app.textFields["auth.email"].tap()
            app.textFields["auth.email"].typeText(Self.email)
            app.secureTextFields["auth.password"].tap()
            app.secureTextFields["auth.password"].typeText(Self.password)
            app.buttons["auth.submit"].tap()
            app.tap()
        }

        XCTAssertTrue(
            app.descendants(matching: .any)["screen.today"].firstMatch.waitForExistence(timeout: 25),
            "never reached the dashboard"
        )
        settle()
        capture(named: "02-today")

        for (tab, name, identifier) in [
            ("lists", "03-lists", "screen.lists"),
            ("tasks", "04-tasks", "screen.tasks"),
            ("activity", "05-activity", "screen.activity"),
            ("search", "08-search", "screen.search"),
        ] {
            let app = launch(tab: tab)
            XCTAssertTrue(
                app.descendants(matching: .any)[identifier].firstMatch.waitForExistence(timeout: 25),
                "\(identifier) did not load"
            )
            settle()
            capture(named: name)
        }

        // A list, then a task inside it.
        //
        // Tapping a *named* element, not `buttons.firstMatch`: the first button in the
        // scroll view is the "Archived" filter chip, so the naive query captured the
        // reorder panel instead of a list.
        let listsApp = launch(tab: "lists")
        _ = listsApp.descendants(matching: .any)["screen.lists"].firstMatch.waitForExistence(timeout: 25)
        settle()
        let listName = listsApp.staticTexts["Product launch"]
        if listName.waitForExistence(timeout: 10) {
            listName.tap()
            settle()
            capture(named: "06-list-detail")

            // The seeded list has tasks; tapping one reaches the detail screen and its
            // four fanned-out reads.
            let taskTitle = listsApp.staticTexts["Fix the mobile nav"]
            if taskTitle.waitForExistence(timeout: 10) {
                taskTitle.tap()
                settle()
                capture(named: "07-task-detail")
            }
        }

        // Settings, via the account avatar.
        let todayApp = launch(tab: "today")
        if todayApp.buttons["nav.account"].firstMatch.waitForExistence(timeout: 20) {
            todayApp.buttons["nav.account"].firstMatch.tap()
            settle()
            capture(named: "09-settings")
        }

        // Dark mode — the design system requires both appearances to work, and this is
        // the cheapest way to see that no colour was hardcoded.
        XCUIDevice.shared.appearance = .dark
        let darkApp = launch(tab: "today")
        _ = darkApp.descendants(matching: .any)["screen.today"].firstMatch.waitForExistence(timeout: 25)
        settle()
        capture(named: "10-dark")
        XCUIDevice.shared.appearance = .light
    }

    /// Launches (or relaunches) the app, optionally straight onto a tab.
    @MainActor
    private func launch(tab: String?) -> XCUIApplication {
        let app = XCUIApplication()
        addUIInterruptionMonitor(withDescription: "Save password prompt") { alert in
            for label in ["Not Now", "Ikke nu", "Cancel"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
        app.launchEnvironment["TODOAPP_API_BASE_URL"] = "http://127.0.0.1:8081"
        app.launchArguments = tab.map { ["--initial-tab", $0] } ?? []
        app.launch()
        return app
    }

    /// A beat for the animation and the network to finish, so a screenshot is not of a
    /// half-drawn screen.
    private func settle() {
        Thread.sleep(forTimeInterval: 2.2)
    }

    @MainActor
    private func capture(named name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let url = outputDirectory.appendingPathComponent("\(name).png")
        try? screenshot.pngRepresentation.write(to: url)
    }
}
