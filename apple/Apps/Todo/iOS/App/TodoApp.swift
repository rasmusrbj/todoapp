import SwiftUI

/// Entry point.
@main
struct TodoApp: App {
    @State private var session: TodoSession
    @State private var settings = AppSettings()
    @State private var actions: Actions

    init() {
        // `Actions` needs the session's backend, and the environment is not
        // readable from a `View.init`, so both are built here where the
        // dependency is in hand. The backend is immutable for the app's lifetime,
        // so there is nothing to keep in sync afterwards.
        let session = TodoSession()
        _session = State(initialValue: session)
        _actions = State(initialValue: Actions(backend: session.backend))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(session)
                .environment(settings)
                .environment(actions)
                // SwiftUI resolves every `LocalizedStringKey` against this, which
                // is what makes the in-app language switch take effect live.
                .environment(\.locale, settings.resolvedLocale)
                // Rebuild the tree when the language changes: views that captured
                // a formatted string in `@State` would otherwise keep the old one.
                .id(settings.locale.rawValue)
                .preferredColorScheme(settings.colorScheme)
                .tint(Theme.accent)
        }
    }
}
