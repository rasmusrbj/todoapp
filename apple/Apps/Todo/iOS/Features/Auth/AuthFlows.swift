import SwiftUI

/// Creating an account.
///
/// Pushed from the sign-in screen, so the back button is the way out and the sign-in
/// form is still there when you return with a typo to fix.
///
/// This backend signs you in immediately and marks the address unverified, rather than
/// holding you at a "check your email" wall — so there is no confirmation alert here.
/// The nudge to confirm lives on the dashboard, where it does not block anything.
struct RegisterView: View {
    @Environment(TodoSession.self) private var session
    @Environment(AppSettings.self) private var settings
    @Environment(\.locale) private var locale

    @State private var displayName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var revealPassword = false
    @FocusState private var focus: Field?

    private enum Field { case name, email, password }

    private var canSubmit: Bool {
        !displayName.trimmingCharacters(in: .whitespaces).isEmpty
            && email.contains("@") && email.contains(".")
            && password.count >= 8
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Space.md) {
                header

                AuthField("auth.namePlaceholder", text: $displayName, focus: $focus, is: .name)
                    .textContentType(.name)
                    .textInputAutocapitalization(.words)
                    .submitLabel(.next)
                    .onSubmit { focus = .email }
                    .accessibilityIdentifier("auth.name")

                AuthField("auth.emailPlaceholder", text: $email, focus: $focus, is: .email)
                    .keyboardType(.emailAddress)
                    .textContentType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.next)
                    .onSubmit { focus = .password }
                    .accessibilityIdentifier("auth.email")

                AuthField(
                    "auth.passwordPlaceholder",
                    text: $password,
                    focus: $focus,
                    is: .password,
                    secure: true,
                    reveal: $revealPassword
                )
                // `.newPassword` is what makes the keychain offer to generate and save a
                // strong one; `.password` would offer to fill an existing one.
                .textContentType(.newPassword)
                .submitLabel(.go)
                .onSubmit(submit)
                .accessibilityIdentifier("auth.password")

                Text("auth.passwordHint")
                    .font(.footnote)
                    .foregroundStyle(Theme.textTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if let failure = session.failure {
                    Text(failure.message(locale: locale))
                        .font(.footnote)
                        .foregroundStyle(Theme.danger)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityIdentifier("error.inline")
                }

                PrimaryButton(
                    "auth.createAccount",
                    isLoading: session.isWorking,
                    large: true,
                    action: submit
                )
                .padding(.top, Theme.Space.xs)
                .disabled(!canSubmit)
                .accessibilityIdentifier("auth.submit")
            }
            .padding(Theme.Space.xl)
            .frame(maxWidth: 460)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.background)
        .navigationTitle("auth.createAccount")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("auth.joinTitle")
                .font(.title2.weight(.bold))
                .foregroundStyle(Theme.textPrimary)
            Text("auth.joinSubtitle")
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.bottom, Theme.Space.sm)
    }

    private func submit() {
        guard canSubmit else { return }
        focus = nil
        let name = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
        let email = email.trimmingCharacters(in: .whitespaces)
        let password = password
        Task {
            await session.register(
                email: email,
                password: password,
                displayName: name,
                // Register in the language the app is showing, so the welcome email
                // matches what they just read.
                locale: settings.locale
            )
            if session.phase == .signedIn { Haptics.success() }
        }
    }
}

/// Asking for a password-reset link.
///
/// Always reports success, because the server does: telling someone an address is
/// unknown tells them which addresses *are* registered.
struct ForgotPasswordView: View {
    @Environment(TodoSession.self) private var session
    @Environment(AppSettings.self) private var settings
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    @State private var email = ""
    @State private var sent = false
    @FocusState private var focused: Bool?

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Space.md) {
                VStack(spacing: 6) {
                    Text("auth.resetTitle")
                        .font(.title2.weight(.bold))
                        .foregroundStyle(Theme.textPrimary)
                    Text("auth.resetIntro")
                        .font(.subheadline)
                        .foregroundStyle(Theme.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.bottom, Theme.Space.sm)

                AuthField("auth.emailPlaceholder", text: $email, focus: $focused, is: true)
                    .keyboardType(.emailAddress)
                    .textContentType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.go)
                    .onSubmit(submit)
                    .accessibilityIdentifier("auth.email")

                if let failure = session.failure {
                    Text(failure.message(locale: locale))
                        .font(.footnote)
                        .foregroundStyle(Theme.danger)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityIdentifier("error.inline")
                }

                PrimaryButton(
                    "auth.sendResetLink",
                    isLoading: session.isWorking,
                    large: true,
                    action: submit
                )
                .padding(.top, Theme.Space.xs)
                .disabled(!(email.contains("@") && email.contains(".")))
            }
            .padding(Theme.Space.xl)
            .frame(maxWidth: 460)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.background)
        .navigationTitle("auth.forgotPassword")
        .navigationBarTitleDisplayMode(.inline)
        .alert("auth.resetSentTitle", isPresented: $sent) {
            Button("action.ok") { dismiss() }
        } message: {
            Text("auth.resetSentBody")
        }
    }

    private func submit() {
        focused = false
        let email = email.trimmingCharacters(in: .whitespaces)
        Task {
            if await session.requestPasswordReset(email: email, locale: settings.locale) {
                sent = true
            }
        }
    }
}
