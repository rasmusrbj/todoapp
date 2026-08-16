import SwiftUI

/// The gate: sign-in when signed out, the app shell when signed in.
struct RootView: View {
    @Environment(TodoSession.self) private var session
    @Environment(AppSettings.self) private var settings

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()

            switch session.phase {
            case .restoring:
                // A stored token exists, so the app is almost certainly about to
                // appear. Showing the sign-in form for a beat and then replacing
                // it would read as a glitch, so hold on a quiet placeholder.
                LaunchPlaceholder()
            case .signedOut:
                LoginView()
            case .signedIn:
                AppShell()
            }
        }
        .animation(.easeInOut(duration: 0.25), value: session.phase)
        .task {
            await session.restore()
        }
        // Keep language and appearance in step with the account, in both
        // directions: the account decides at launch, the picker writes back.
        .task(id: session.viewer?.id) {
            guard let viewer = session.viewer else { return }
            settings.adopt(from: viewer)
        }
    }
}

/// Launch placeholder while the stored session is validated. Deliberately plain —
/// it is on screen for a few hundred milliseconds and a spinner would draw the eye
/// to a wait that is usually already over.
private struct LaunchPlaceholder: View {
    var body: some View {
        VStack(spacing: Theme.Space.md) {
            Image(systemName: "checklist")
                .font(.system(size: 40, weight: .light))
                .foregroundStyle(Theme.textTertiary)
            Text("app.name")
                .font(.headline)
                .foregroundStyle(Theme.textSecondary)
        }
        .accessibilityElement(children: .combine)
    }
}
