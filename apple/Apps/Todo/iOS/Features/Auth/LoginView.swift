import SwiftUI

/// Where the signed-out stack can go.
enum AuthRoute: Hashable {
    case register
    case forgotPassword
}

/// Email + password sign-in — the root of the signed-out stack.
///
/// Follows the pattern the other Happenings apps use, and the parts that look like
/// decoration are not:
///
/// * **Register and reset are pushed screens**, not a segmented switch on this one.
///   Creating an account needs a name field and a different primary action; putting both
///   modes behind a toggle means the form silently changes shape under the cursor, and
///   the button's label changes meaning without moving.
/// * **The hero is the only thing above the fold**, so the first impression is the app's
///   name rather than two empty boxes.
/// * **Focus chains** email → password → submit, which is what makes the keyboard's
///   return key do the obvious thing.
struct LoginView: View {
    @Environment(TodoSession.self) private var session
    @Environment(\.locale) private var locale

    @State private var email = ""
    @State private var password = ""
    @State private var revealPassword = false
    @FocusState private var focus: Field?

    private enum Field { case email, password }

    /// A local sanity check only, so the button is honest. The server remains the
    /// authority on what a valid credential is.
    private var canSignIn: Bool {
        email.contains("@") && email.contains(".") && !password.isEmpty
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.background.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: Theme.Space.xl) {
                        AuthHero()
                            .padding(.top, 72)

                        VStack(spacing: Theme.Space.md) {
                            AuthField(
                                "auth.emailPlaceholder",
                                text: $email,
                                focus: $focus,
                                is: .email
                            )
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
                            .textContentType(.password)
                            .submitLabel(.go)
                            .onSubmit(signIn)
                            .accessibilityIdentifier("auth.password")

                            if let failure = session.failure {
                                Text(failure.message(locale: locale))
                                    .font(.footnote)
                                    .foregroundStyle(Theme.danger)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .accessibilityIdentifier("error.inline")
                                    .transition(.opacity)
                            }

                            PrimaryButton(
                                "auth.signIn",
                                isLoading: session.isWorking,
                                large: true,
                                action: signIn
                            )
                            .padding(.top, Theme.Space.xs)
                            .disabled(!canSignIn)
                            // The create-account row below carries the other label, so
                            // the primary action gets a stable identifier for the UI
                            // tests — invisible to users, and nothing to translate.
                            .accessibilityIdentifier("auth.submit")

                            NavigationLink(value: AuthRoute.forgotPassword) {
                                Text("auth.forgotPassword")
                                    .font(.subheadline)
                                    .foregroundStyle(Theme.accent)
                            }
                            .pressable()
                            .frame(maxWidth: .infinity, alignment: .trailing)
                        }

                        secondaryActions
                    }
                    .padding(.horizontal, Theme.Space.xl)
                    .padding(.bottom, Theme.Space.xxl)
                    // A phone-width column on an iPad, where a form stretched across
                    // 1000pt reads as broken.
                    .frame(maxWidth: 460)
                    .frame(maxWidth: .infinity)
                }
                .scrollDismissesKeyboard(.interactively)
            }
            .navigationDestination(for: AuthRoute.self) { route in
                switch route {
                case .register: RegisterView()
                case .forgotPassword: ForgotPasswordView()
                }
            }
        }
    }

    private var secondaryActions: some View {
        VStack(spacing: Theme.Space.md) {
            OrDivider()
            NavigationLink(value: AuthRoute.register) {
                OutlineRowLabel(title: "auth.createAccount", symbol: "person.badge.plus")
            }
            .pressable(0.98)
        }
    }

    private func signIn() {
        guard canSignIn else { return }
        // Drop the keyboard first: the error, if there is one, appears where the
        // keyboard was.
        focus = nil
        let email = email.trimmingCharacters(in: .whitespaces)
        let password = password
        Task {
            await session.signIn(email: email, password: password)
            if session.phase == .signedIn { Haptics.success() }
        }
    }
}

/// The hero: mark, wordmark, and rotating taglines under one shimmer.
///
/// The consumer app floats event photos behind its login; that is content, and a todo
/// app has none worth showing pre-auth — so this keeps the shimmer and the taglines and
/// drops the bubbles rather than inventing decoration to fill the space.
struct AuthHero: View {
    var body: some View {
        ShimmerWordmarkHero(
            wordmark: "Todoapp",
            taglines: [
                "auth.taglineLists",
                "auth.taglineShare",
                "auth.taglineToday",
                "auth.taglineEverywhere",
            ]
        ) {
            TodoBrandMark()
        }
    }
}
