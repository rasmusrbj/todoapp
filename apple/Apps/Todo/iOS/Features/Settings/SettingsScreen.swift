import SwiftUI

/// Account, appearance, language, security — and the admin door for those who have one.
struct SettingsScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(AppSettings.self) private var settings
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var changingPassword = false
    @State private var confirmingSignOut = false

    var body: some View {
        // No `NavigationStack` of its own: Settings is pushed from whichever tab the
        // account button was tapped in, so it inherits that stack — and its own
        // destinations are already registered there by `todoDestinations()`.
        ScreenScaffold {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let viewer = session.viewer {
                    profileCard(viewer)
                    appearance
                    account(viewer)
                    if viewer.role == .admin { administration }
                    about
                } else {
                    Skeleton(height: 96, cornerRadius: Theme.Radius.card)
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle("nav.settings")
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.settings")
        .sheet(isPresented: $changingPassword) {
            ChangePasswordSheet()
        }
        .confirmationDialog(
            "settings.confirmSignOutTitle",
            isPresented: $confirmingSignOut,
            titleVisibility: .visible
        ) {
            Button("settings.signOut", role: .destructive) {
                Task { await session.signOut() }
            }
            Button("action.cancel", role: .cancel) {}
        }
    }

    // MARK: Cards

    private func profileCard(_ viewer: Todo_V1_User) -> some View {
        NavigationLink(value: TodoRoute.profile) {
            HStack(spacing: Theme.Space.md) {
                AvatarView(name: viewer.displayName, url: viewer.avatarURL, size: 52)
                VStack(alignment: .leading, spacing: 2) {
                    Text(viewer.displayName)
                        .font(.headline)
                        .foregroundStyle(Theme.textPrimary)
                    Text(viewer.email)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                        .lineLimit(1)
                    HStack(spacing: Theme.Space.xs + 2) {
                        UserStatusBadge(status: viewer.status)
                        if viewer.role == .admin {
                            Badge(text: viewer.role.displayName, tint: Theme.accent)
                        }
                        if !viewer.emailVerified {
                            Badge(text: "settings.unverified", tint: Theme.warning, symbol: "envelope.badge")
                        }
                    }
                    .padding(.top, 2)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.textTertiary)
            }
            .padding(Theme.Space.lg)
            .frame(maxWidth: .infinity, alignment: .leading)
            .cardSurface()
        }
        .pressable(0.98)
    }

    private var appearance: some View {
        ScreenSection("settings.appearance") {
            GroupedCard {
                // Language and theme are stored on the account, so the change is
                // written to the server *and* applied locally at once. Applying it
                // locally first is what makes the switch feel instant rather than
                // waiting on a round-trip.
                SettingsRow(symbol: "globe", title: "settings.language") {
                    Menu {
                        ForEach(Todo_V1_Locale.selectable, id: \.self) { option in
                            Button {
                                settings.apply(locale: option)
                                Task { await persistPreferences() }
                            } label: {
                                if option == settings.locale {
                                    Label(option.displayName, systemImage: "checkmark")
                                } else {
                                    Text(option.displayName)
                                }
                            }
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Text(settings.locale.displayName)
                            Image(systemName: "chevron.up.chevron.down")
                                .font(.system(size: 8, weight: .semibold))
                        }
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                    }
                }

                InsetDivider()

                SettingsRow(symbol: settings.theme.symbol, title: "settings.theme") {
                    Menu {
                        ForEach(Todo_V1_ThemePreference.selectable, id: \.self) { option in
                            Button {
                                settings.apply(theme: option)
                                Task { await persistPreferences() }
                            } label: {
                                if option == settings.theme {
                                    Label(option.displayName, systemImage: "checkmark")
                                } else {
                                    Label(option.displayName, systemImage: option.symbol)
                                }
                            }
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Text(settings.theme.displayName)
                            Image(systemName: "chevron.up.chevron.down")
                                .font(.system(size: 8, weight: .semibold))
                        }
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                    }
                }
            }
        }
    }

    private func account(_ viewer: Todo_V1_User) -> some View {
        ScreenSection("settings.account") {
            GroupedCard {
                if !viewer.emailVerified {
                    // `action:` spelled out rather than passed as a trailing closure:
                    // `SettingsRow` also takes a @ViewBuilder `trailing`, and a bare
                    // trailing closure binds to that one instead.
                    SettingsRow(
                        symbol: "envelope.badge",
                        title: "settings.resendVerification",
                        tint: Theme.warning,
                        action: { Task { await actions.resendVerificationEmail() } }
                    )
                    InsetDivider()
                }

                SettingsRow(
                    symbol: "key",
                    title: "settings.changePassword",
                    showsChevron: true,
                    action: { changingPassword = true }
                )

                InsetDivider()

                NavigationLink(value: TodoRoute.sessions) {
                    SettingsRow(symbol: "laptopcomputer.and.iphone", title: "settings.sessions", showsChevron: true)
                }
                .pressable(0.98)

                InsetDivider()

                SettingsRow(
                    symbol: "rectangle.portrait.and.arrow.right",
                    title: "settings.signOut",
                    tint: Theme.danger,
                    action: { confirmingSignOut = true }
                )
                // The row and the confirmation dialog's button share a label, so the
                // row carries an identifier for the UI test to aim at.
                .accessibilityIdentifier("settings.signOut")
            }
        }
    }

    private var administration: some View {
        ScreenSection("settings.administration") {
            GroupedCard {
                NavigationLink(value: TodoRoute.adminUsers) {
                    SettingsRow(symbol: "person.3", title: "admin.users", showsChevron: true)
                }
                .pressable(0.98)
            }
        }
    }

    private var about: some View {
        ScreenSection("settings.about") {
            GroupedCard {
                SettingsRow(symbol: "info.circle", title: "settings.version") {
                    Text(verbatim: AppConfig.displayVersion)
                        .monospacedDigit()
                }
                #if DEBUG
                InsetDivider()
                // Debug only, and compiled out of a release build entirely: a shipped
                // app that can be pointed at another backend is a liability, not a
                // convenience.
                NavigationLink {
                    DeveloperScreen()
                } label: {
                    SettingsRow(symbol: "hammer", title: "settings.developer", showsChevron: true)
                }
                .pressable(0.98)
                #endif
            }
        }
    }

    /// Writes language and appearance back to the account so the web agrees.
    private func persistPreferences() async {
        if let updated = await actions.updateProfile(
            displayName: nil,
            bio: nil,
            timeZone: nil,
            locale: settings.locale,
            theme: settings.theme
        ) {
            settings.adopt(from: updated)
            await session.reloadViewer()
        }
    }
}

/// Editing the profile.
struct ProfileScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    @State private var displayName = ""
    @State private var bio = ""
    @State private var timeZone = TimeZone.current.identifier
    @State private var isSaving = false
    @State private var loaded = false

    var body: some View {
        Form {
            Section {
                LabeledContent("settings.email") {
                    Text(session.viewer?.email ?? "")
                        .foregroundStyle(Theme.textSecondary)
                }
            } footer: {
                // Changing an address means re-verifying it, which the API does not
                // expose yet. Saying so beats a field that silently does nothing.
                Text("settings.emailImmutable")
            }

            Section {
                TextField("auth.name", text: $displayName)
                    .textContentType(.name)
                TextField("settings.bioPlaceholder", text: $bio, axis: .vertical)
                    .lineLimit(3...6)
            } header: {
                Text("settings.profile")
            }

            Section {
                Picker("settings.timeZone", selection: $timeZone) {
                    ForEach(Self.commonTimeZones, id: \.self) { identifier in
                        Text(identifier).tag(identifier)
                    }
                }
            } header: {
                Text("settings.timeZone")
            } footer: {
                // The server resolves "today" for due dates in this zone, so it is not
                // cosmetic — it decides what counts as overdue.
                Text("settings.timeZoneFooter")
            }

            if let stats = session.viewer?.stats {
                Section {
                    LabeledContent("today.statOpen") { Text(verbatim: "\(stats.openTaskCount)") }
                    LabeledContent("today.statDone") { Text(verbatim: "\(stats.completedTaskCount)") }
                    LabeledContent("settings.ownedLists") { Text(verbatim: "\(stats.ownedListCount)") }
                    LabeledContent("settings.sharedLists") { Text(verbatim: "\(stats.sharedListCount)") }
                } header: {
                    Text("settings.statistics")
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.background)
        .navigationTitle("settings.profile")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("action.save") {
                    Task { await save() }
                }
                .fontWeight(.semibold)
                .disabled(!hasChanges || isSaving)
            }
        }
        .task {
            guard !loaded, let viewer = session.viewer else { return }
            displayName = viewer.displayName
            bio = viewer.bio
            timeZone = viewer.timeZone.isEmpty ? TimeZone.current.identifier : viewer.timeZone
            loaded = true
        }
    }

    private var hasChanges: Bool {
        guard let viewer = session.viewer else { return false }
        return displayName != viewer.displayName
            || bio != viewer.bio
            || timeZone != viewer.timeZone
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        let updated = await actions.updateProfile(
            displayName: displayName.trimmingCharacters(in: .whitespacesAndNewlines),
            bio: bio,
            timeZone: timeZone,
            locale: nil,
            theme: nil
        )
        if updated != nil {
            await session.reloadViewer()
            Haptics.success()
            dismiss()
        }
    }

    /// A short list rather than all ~600 zones: this app's users are in a handful of
    /// them, and a 600-row picker is not a control anyone enjoys. The device's own
    /// zone is always first, so the common case is one tap.
    private static var commonTimeZones: [String] {
        var zones = [
            "Europe/Copenhagen", "Europe/London", "Europe/Berlin", "Europe/Madrid",
            "Europe/Stockholm", "Europe/Oslo", "UTC",
            "America/New_York", "America/Los_Angeles", "Asia/Tokyo", "Australia/Sydney",
        ]
        let current = TimeZone.current.identifier
        if let index = zones.firstIndex(of: current) {
            zones.remove(at: index)
        }
        zones.insert(current, at: 0)
        return zones
    }
}

/// Changing the password.
struct ChangePasswordSheet: View {
    @Environment(TodoSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    @State private var current = ""
    @State private var new = ""
    @State private var confirmation = ""

    private var mismatch: Bool { !confirmation.isEmpty && new != confirmation }
    private var canSubmit: Bool {
        !current.isEmpty && new.count >= 8 && new == confirmation
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SecureField("settings.currentPassword", text: $current)
                        .textContentType(.password)
                }
                Section {
                    SecureField("settings.newPassword", text: $new)
                        .textContentType(.newPassword)
                    SecureField("settings.confirmPassword", text: $confirmation)
                        .textContentType(.newPassword)
                } footer: {
                    if mismatch {
                        Text("settings.passwordMismatch").foregroundStyle(Theme.danger)
                    } else {
                        // Every other session is revoked server-side, which is the
                        // right behaviour and a surprise if unannounced.
                        Text("settings.changePasswordFooter")
                    }
                }
                if let failure = session.failure {
                    Section {
                        Text(failure.message(locale: locale))
                            .font(.subheadline)
                            .foregroundStyle(Theme.danger)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle("settings.changePassword")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("action.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("action.save") {
                        Task {
                            if await session.changePassword(current: current, new: new) {
                                Haptics.success()
                                dismiss()
                            }
                        }
                    }
                    .fontWeight(.semibold)
                    .disabled(!canSubmit || session.isWorking)
                }
            }
        }
    }
}

#if DEBUG
/// Points a debug build at a different backend.
struct DeveloperScreen: View {
    @Environment(TodoSession.self) private var session
    @State private var host = AppConfig.baseURLOverride

    var body: some View {
        Form {
            Section {
                TextField("settings.apiHost", text: $host)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                Button("settings.applyHost") {
                    AppConfig.setBaseURLOverride(host)
                    // The clients were built against the old host and the Keychain
                    // entries are scoped per environment, so the session has to end
                    // here — carrying it over would look signed in and fail every call.
                    Task { await session.signOut() }
                }
            } header: {
                Text("settings.apiHost")
            } footer: {
                Text("settings.apiHostFooter")
            }

            Section {
                LabeledContent("settings.currentHost") {
                    Text(verbatim: AppConfig.apiBaseURL.absoluteString)
                        .font(.caption.monospaced())
                }
                LabeledContent("settings.environment") {
                    Text(verbatim: AppConfig.environmentName)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.background)
        .navigationTitle("settings.developer")
        .navigationBarTitleDisplayMode(.inline)
    }
}
#endif
