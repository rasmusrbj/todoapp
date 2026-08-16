import SwiftUI

/// Shared screen furniture: the background, the content measure, the toast, and
/// the loading/empty/error switch.
///
/// Every screen in the app goes through these, which is what keeps a failure on
/// Today looking like a failure on Lists.

/// Wraps a screen's scrolling content: themed background, an iPad-sane measure,
/// pull to refresh, and the shared feedback toast.
struct ScreenScaffold<Content: View>: View {
    var refresh: (() async -> Void)?
    @ViewBuilder var content: Content

    var body: some View {
        ScrollView {
            content
                .padding(.horizontal, Theme.Space.lg)
                .padding(.bottom, Theme.Space.xxl)
                // Content stops being readable when it runs the full width of an
                // iPad, so the column is capped and centred rather than stretched.
                .frame(maxWidth: Theme.readingWidth)
                .frame(maxWidth: .infinity)
        }
        .background(Theme.background)
        .scrollDismissesKeyboard(.immediately)
        .refreshable { await refresh?() }
        .actionFeedback()
    }
}

/// Renders the four states of a load in one place.
///
/// The point is that a screen cannot *forget* one. Writing `if let value = state.value`
/// and nothing else is how a failed request becomes a silent blank page.
struct StateView<Value: Sendable, Content: View>: View {
    let state: LoadState<Value>
    var emptySymbol: String = "tray"
    var emptyTitle: LocalizedStringKey = "state.emptyTitle"
    var emptyMessage: LocalizedStringKey?
    var emptyActionTitle: LocalizedStringKey?
    var emptyAction: (() -> Void)?
    /// The shape to show while loading, so nothing jumps when content lands.
    var skeletonRows: Int = 3
    var retry: (() async -> Void)?
    @ViewBuilder var content: (Value) -> Content

    @Environment(\.locale) private var locale

    var body: some View {
        switch state {
        case .loading:
            VStack(spacing: Theme.Space.sm) {
                ForEach(0..<skeletonRows, id: \.self) { _ in
                    Skeleton(height: 64, cornerRadius: Theme.Radius.card)
                }
            }
        case let .loaded(value):
            content(value)
        case .empty:
            StateMessage(
                symbol: emptySymbol,
                title: emptyTitle,
                message: emptyMessage,
                actionTitle: emptyActionTitle,
                action: emptyAction
            )
            .padding(.vertical, Theme.Space.xxl)
        case let .failed(failure):
            StateMessage(
                symbol: "exclamationmark.triangle",
                title: "state.failedTitle",
                message: LocalizedStringKey(failure.messageKey),
                actionTitle: retry == nil ? nil : "action.retry",
                action: retry == nil ? nil : { Task { await retry?() } }
            )
            .padding(.vertical, Theme.Space.xxl)
        }
    }
}

/// A section header plus content, the standard vertical rhythm between them.
///
/// Named `ScreenSection`, not `Section`: shadowing SwiftUI's own `Section` breaks
/// every `Form` and `List` in the target that relies on it.
struct ScreenSection<Content: View>: View {
    let title: LocalizedStringKey
    var accessory: AnyView?
    @ViewBuilder var content: Content

    init(_ title: LocalizedStringKey, @ViewBuilder content: () -> Content) {
        self.title = title
        self.accessory = nil
        self.content = content()
    }

    init<Accessory: View>(
        _ title: LocalizedStringKey,
        @ViewBuilder accessory: () -> Accessory,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.accessory = AnyView(accessory())
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            HStack(alignment: .firstTextBaseline) {
                SectionHeader(title)
                Spacer(minLength: Theme.Space.sm)
                accessory
            }
            content
        }
    }
}

// MARK: - Feedback

/// Shows whatever the last write had to say — an error, or a confirmation.
///
/// One modifier on each screen's scroll view rather than a banner per call site,
/// so a mutation triggered from a row, a menu or a sheet all report the same way.
private struct ActionFeedback: ViewModifier {
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .bottom) {
                Group {
                    if let failure = actions.failure {
                        toast(
                            text: failure.message(locale: locale),
                            symbol: "exclamationmark.triangle.fill",
                            tint: Theme.danger
                        )
                    } else if let confirmation = actions.confirmation {
                        toast(
                            text: Localized.string(confirmation, locale: locale),
                            symbol: "checkmark.circle.fill",
                            tint: Theme.success
                        )
                    }
                }
                .padding(.horizontal, Theme.Space.lg)
                .padding(.bottom, Theme.Space.sm)
                .animation(.snappy(duration: 0.25), value: actions.failure)
                .animation(.snappy(duration: 0.25), value: actions.confirmation == nil)
            }
            // Both clear themselves. A toast that needs dismissing is a dialog.
            .task(id: actions.failure) {
                guard actions.failure != nil else { return }
                try? await _Concurrency.Task.sleep(for: .seconds(4))
                actions.failure = nil
            }
            .task(id: actions.confirmation == nil) {
                guard actions.confirmation != nil else { return }
                try? await _Concurrency.Task.sleep(for: .seconds(2))
                actions.confirmation = nil
            }
    }

    private func toast(text: String, symbol: String, tint: Color) -> some View {
        HStack(spacing: Theme.Space.sm) {
            Image(systemName: symbol)
                .foregroundStyle(tint)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(Theme.textPrimary)
            Spacer(minLength: 0)
        }
        .padding(Theme.Space.md)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                .stroke(Theme.border, lineWidth: 1)
        )
        // A toast is the one place a shadow is doing real work: it explains that
        // this thing floats above the content rather than sitting in it.
        .shadow(color: .black.opacity(0.12), radius: 12, y: 4)
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .accessibilityAddTraits(.isStaticText)
    }

}

extension View {
    /// Attaches the shared write-feedback toast.
    func actionFeedback() -> some View { modifier(ActionFeedback()) }
}
