import Observation
import SwiftUI

/// Where the account is signed in, and how to end any of them.
struct SessionsScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: SessionsModel?

    var body: some View {
        ScreenScaffold(refresh: { await model?.load() }) {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let model {
                    StateView(
                        state: model.state,
                        emptySymbol: "laptopcomputer.and.iphone",
                        emptyTitle: "settings.noSessionsTitle",
                        retry: { await model.load() }
                    ) { sessions in
                        VStack(spacing: 0) {
                            ForEach(Array(sessions.enumerated()), id: \.element.id) { index, entry in
                                if index > 0 { InsetDivider(leading: Theme.Space.xxl + Theme.Space.md) }
                                SessionRow(session: entry)
                            }
                        }
                        .cardSurface()
                    }

                    Text("settings.sessionsFooter")
                        .font(.caption)
                        .foregroundStyle(Theme.textTertiary)
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle("settings.sessions")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            if model == nil { model = SessionsModel(backend: session.backend) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
    }
}

private struct SessionRow: View {
    let session: Todo_V1_Session

    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.md) {
            Image(systemName: session.client.symbol)
                .font(.system(size: 15))
                .foregroundStyle(Theme.textSecondary)
                .frame(width: 28, height: 28)
                .background(Theme.surfaceInset, in: Circle())

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: Theme.Space.sm) {
                    Text(session.client.displayName)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Theme.textPrimary)
                    if session.isCurrent {
                        Badge(text: "settings.thisDevice", tint: Theme.success)
                    }
                }

                if !session.userAgent.isEmpty {
                    Text(session.userAgent)
                        .font(.caption)
                        .foregroundStyle(Theme.textSecondary)
                        .lineLimit(2)
                }

                Text("settings.sessionLastUsed \(Format.relative(session.lastUsedAt.date, locale: locale))")
                    .font(.caption2)
                    .foregroundStyle(Theme.textTertiary)

                if session.hasExpiresAt {
                    Text("settings.sessionExpires \(Format.date(session.expiresAt.date, locale: locale))")
                        .font(.caption2)
                        .foregroundStyle(Theme.textTertiary)
                }
            }

            Spacer(minLength: 0)

            // The current session is not revocable here — that is what "sign out"
            // is, and offering both would be two names for one action with different
            // consequences for the UI state.
            if !session.isCurrent {
                Button {
                    Task { await actions.revokeSession(id: session.id) }
                } label: {
                    Text("settings.revoke")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.danger)
                }
                .pressable()
                .disabled(actions.isPending(session.id))
            }
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
    }
}

// MARK: - Model

@MainActor
@Observable
final class SessionsModel {
    private let backend: TodoBackend
    private(set) var state: LoadState<[Todo_V1_Session]> = .loading

    init(backend: TodoBackend) {
        self.backend = backend
    }

    func load() async {
        let result = unwrap(await backend.auth.listSessions(request: Todo_V1_ListSessionsRequest())) {
            // Current device first, then most recently used — the order someone scans
            // when looking for a session they do not recognise.
            $0.sessions.sorted {
                if $0.isCurrent != $1.isCurrent { return $0.isCurrent }
                return $0.lastUsedAt.date > $1.lastUsedAt.date
            }
        }
        state = result.listState
    }
}
