import SwiftUI

/// The rounded auth text field used by sign-in, register and password reset.
///
/// Placeholder-only, no floating caption: on an auth screen the three fields are
/// self-evident, and a label above each one doubles the vertical cost of the form for
/// no information. The other Happenings apps make the same trade.
///
/// Two details carry the interaction:
///
/// * the border strengthens while the field has focus, which is the only affordance
///   telling you where you are typing on a screen of identical rounded boxes;
/// * secure fields get a reveal toggle, because a password typed blind on a phone
///   keyboard is the single most common reason someone thinks their password is wrong.
///
/// Generic over the focus enum so each screen names its own fields.
struct AuthField<Field: Hashable>: View {
    private let placeholder: LocalizedStringKey
    @Binding private var text: String
    private let focus: FocusState<Field?>.Binding
    private let value: Field
    private let secure: Bool
    private let reveal: Binding<Bool>?

    init(
        _ placeholder: LocalizedStringKey,
        text: Binding<String>,
        focus: FocusState<Field?>.Binding,
        is value: Field,
        secure: Bool = false,
        reveal: Binding<Bool>? = nil
    ) {
        self.placeholder = placeholder
        self._text = text
        self.focus = focus
        self.value = value
        self.secure = secure
        self.reveal = reveal
    }

    private var isRevealed: Bool { reveal?.wrappedValue ?? false }
    private var isFocused: Bool { focus.wrappedValue == value }

    var body: some View {
        Group {
            if secure, !isRevealed {
                SecureField(placeholder, text: $text)
            } else {
                TextField(placeholder, text: $text)
            }
        }
        .focused(focus, equals: value)
        .frame(minHeight: 28)
        .padding(.horizontal, Theme.Space.md)
        .padding(.vertical, 16)
        // Room for the eye button, so a long password does not slide under it.
        .padding(.trailing, secure ? 40 : 0)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                .stroke(isFocused ? Theme.borderStrong : Theme.border, lineWidth: 1)
        )
        .animation(.easeOut(duration: 0.15), value: isFocused)
        .overlay(alignment: .trailing) {
            if secure, let reveal {
                Button {
                    reveal.wrappedValue.toggle()
                } label: {
                    Image(systemName: isRevealed ? "eye.slash" : "eye")
                        .font(.subheadline)
                        .foregroundStyle(Theme.textTertiary)
                        .padding(.trailing, Theme.Space.md)
                        .contentShape(Rectangle())
                }
                .pressable(0.9)
                .accessibilityLabel(isRevealed ? "a11y.hidePassword" : "a11y.showPassword")
            }
        }
    }
}

/// A full-width bordered row — the quiet alternative to `PrimaryButton`, for the
/// secondary way off a screen ("create account"). Flat surface, border, icon + label.
///
/// A label rather than a button so it composes with `NavigationLink` as well as with
/// `Button`; the caller supplies the interaction.
struct OutlineRowLabel: View {
    let title: LocalizedStringKey
    let symbol: String

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            Image(systemName: symbol)
            Text(title).font(.headline)
        }
        .foregroundStyle(Theme.textPrimary)
        .frame(maxWidth: .infinity)
        .padding(.vertical, 18)
        .background(Theme.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                .stroke(Theme.border, lineWidth: 1)
        )
    }
}

/// A hairline / label / hairline separator — "or" between the primary action and the
/// alternatives.
struct OrDivider: View {
    var label: LocalizedStringKey = "auth.or"

    var body: some View {
        HStack(spacing: Theme.Space.md) {
            Rectangle().fill(Theme.border).frame(height: 1)
            Text(label)
                .font(.footnote)
                .foregroundStyle(Theme.textTertiary)
            Rectangle().fill(Theme.border).frame(height: 1)
        }
        .accessibilityHidden(true)
    }
}
