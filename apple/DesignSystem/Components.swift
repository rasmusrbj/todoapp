import SwiftUI

/// App-agnostic building blocks on top of `Theme`. Flat surfaces, borders instead
/// of shadows, 4px rhythm, scale-down press.
///
/// Nothing here knows about tasks, lists or the backend — anything proto-aware
/// lives in the app layer, so this file stays reusable.

// MARK: - Structure

/// A small, restrained section header. Muted caption, not a bold title.
struct SectionHeader: View {
    private let title: LocalizedStringKey
    private let action: AnyView?

    init(_ title: LocalizedStringKey) {
        self.title = title
        self.action = nil
    }

    init<Action: View>(_ title: LocalizedStringKey, @ViewBuilder action: () -> Action) {
        self.title = title
        self.action = AnyView(action())
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(Theme.textTertiary)
                .textCase(.uppercase)
                .kerning(0.4)
            Spacer(minLength: Theme.Space.sm)
            action
        }
    }
}

/// The canonical bordered container.
struct Card<Content: View>: View {
    private let padding: CGFloat
    private let content: Content

    init(padding: CGFloat = Theme.Space.lg, @ViewBuilder content: () -> Content) {
        self.padding = padding
        self.content = content()
    }

    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .cardSurface()
    }
}

/// A grouped card holding rows separated by `InsetDivider` — the settings idiom.
struct GroupedCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) { content }
            .cardSurface()
    }
}

/// Hairline between grouped rows, inset from the leading edge so it reads as a
/// separator rather than a full-width rule.
struct InsetDivider: View {
    var leading: CGFloat = Theme.Space.lg

    var body: some View {
        Divider()
            .overlay(Theme.border)
            .padding(.leading, leading)
    }
}

/// A tappable row inside a `GroupedCard`: icon, title, optional value, chevron.
struct SettingsRow<Trailing: View>: View {
    let symbol: String
    let title: LocalizedStringKey
    var tint: Color = Theme.textSecondary
    var showsChevron = false
    @ViewBuilder var trailing: Trailing
    var action: (() -> Void)?

    init(
        symbol: String,
        title: LocalizedStringKey,
        tint: Color = Theme.textSecondary,
        showsChevron: Bool = false,
        @ViewBuilder trailing: () -> Trailing = { EmptyView() },
        action: (() -> Void)? = nil
    ) {
        self.symbol = symbol
        self.title = title
        self.tint = tint
        self.showsChevron = showsChevron
        self.trailing = trailing()
        self.action = action
    }

    var body: some View {
        if let action {
            Button(action: action) { content }
                .pressable(0.98)
        } else {
            content
        }
    }

    private var content: some View {
        HStack(spacing: Theme.Space.md) {
            Image(systemName: symbol)
                .font(.system(size: 15))
                .foregroundStyle(tint)
                .frame(width: 22)
            Text(title)
                .font(.subheadline)
                .foregroundStyle(action == nil ? Theme.textPrimary : tint == Theme.danger ? Theme.danger : Theme.textPrimary)
            Spacer(minLength: Theme.Space.sm)
            trailing
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
            if showsChevron {
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.textTertiary)
            }
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
        .contentShape(Rectangle())
    }
}

// MARK: - Identity

/// Avatar with an initials fallback. Loads `url` when there is one.
struct AvatarView: View {
    let name: String
    var url: String = ""
    var size: CGFloat = 36

    private var initials: String {
        let parts = name.split(separator: " ").prefix(2)
        let joined = parts.compactMap(\.first).map(String.init).joined().uppercased()
        return joined.isEmpty ? "?" : joined
    }

    var body: some View {
        ZStack {
            Circle().fill(Theme.surfaceInset)
            Text(initials)
                .font(.system(size: size * 0.38, weight: .semibold))
                .foregroundStyle(Theme.textSecondary)
            if let resolved = URL(string: url), !url.isEmpty {
                AsyncImage(url: resolved) { phase in
                    if case let .success(image) = phase {
                        image.resizable().scaledToFill()
                    }
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(Circle().stroke(Theme.border, lineWidth: 1))
        // The name is already in the row next to it; announcing it twice is noise.
        .accessibilityHidden(true)
    }
}

// MARK: - Badges

/// A bordered pill. Border rather than a filled background, so a row of these
/// stays quiet.
struct Badge: View {
    let text: LocalizedStringKey
    var tint: Color = Theme.textSecondary
    var symbol: String?
    var filled = false

    var body: some View {
        HStack(spacing: 4) {
            if let symbol {
                Image(systemName: symbol).font(.system(size: 9, weight: .bold))
            }
            Text(text)
        }
        .font(.caption2.weight(.semibold))
        .foregroundStyle(filled ? Theme.onAccent : tint)
        .padding(.horizontal, Theme.Space.sm)
        .padding(.vertical, 3)
        .background(filled ? tint : .clear, in: Capsule())
        .overlay(filled ? nil : Capsule().stroke(tint.opacity(0.35), lineWidth: 1))
    }
}

/// A dot in a content color — how a list identifies itself in a dense row.
struct ColorDot: View {
    let color: Color
    var size: CGFloat = 8

    var body: some View {
        Circle()
            .fill(color)
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}

/// A thin completion bar. No label — the number lives next to it in the row.
struct ProgressBar: View {
    /// 0–100.
    let percent: Int
    var tint: Color = Theme.accent
    var height: CGFloat = 4

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.surfaceInset)
                Capsule()
                    .fill(tint)
                    .frame(width: geometry.size.width * min(max(Double(percent) / 100, 0), 1))
            }
        }
        .frame(height: height)
        .accessibilityHidden(true)
    }
}

// MARK: - Controls

/// Primary filled button. Accent background, inverted label, so it contrasts in
/// both appearances.
struct PrimaryButton: View {
    private let title: LocalizedStringKey
    private let isLoading: Bool
    /// `large` is the auth-screen size — 18pt of vertical padding rather than 14. The
    /// primary action on a screen with nothing else on it should not be the same height
    /// as a button in a toolbar.
    private let large: Bool
    private let action: () -> Void
    @Environment(\.isEnabled) private var isEnabled

    init(
        _ title: LocalizedStringKey,
        isLoading: Bool = false,
        large: Bool = false,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.isLoading = isLoading
        self.large = large
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            ZStack {
                Text(title).opacity(isLoading ? 0 : 1)
                if isLoading {
                    ProgressView().tint(Theme.onAccent).controlSize(.small)
                }
            }
            .font(large ? .headline.weight(.semibold) : .headline)
            .foregroundStyle(isEnabled ? Theme.onAccent : Theme.textTertiary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, large ? 18 : Theme.Space.md + 2)
            .background(
                isEnabled ? Theme.accent : Theme.surfaceInset,
                in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
            )
        }
        .pressable(0.97)
        .disabled(isLoading || !isEnabled)
    }
}

/// Bordered secondary button — same geometry as `PrimaryButton`, quieter.
struct SecondaryButton: View {
    private let title: LocalizedStringKey
    private let action: () -> Void

    init(_ title: LocalizedStringKey, action: @escaping () -> Void) {
        self.title = title
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Space.md)
                .background(
                    Theme.surface,
                    in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                        .stroke(Theme.border, lineWidth: 1)
                )
        }
        .pressable(0.97)
    }
}

/// A bordered text field with a floating caption, matching the web's form rows.
struct LabeledField<Field: View>: View {
    let label: LocalizedStringKey
    var caption: LocalizedStringKey?
    var isInvalid = false
    @ViewBuilder var field: Field

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs + 2) {
            Text(label)
                .font(.caption.weight(.medium))
                .foregroundStyle(Theme.textSecondary)
            field
                .font(.body)
                .padding(.horizontal, Theme.Space.md)
                .padding(.vertical, Theme.Space.md - 2)
                .background(
                    Theme.surface,
                    in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                        .stroke(isInvalid ? Theme.danger : Theme.border, lineWidth: 1)
                )
            if let caption {
                Text(caption)
                    .font(.caption)
                    .foregroundStyle(isInvalid ? Theme.danger : Theme.textTertiary)
            }
        }
    }
}

/// A themed segmented control — inset track, accent pill for the selection.
struct ThemedSegmentedControl<Value: Hashable>: View {
    @Binding var selection: Value
    let options: [(value: Value, label: LocalizedStringKey)]

    var body: some View {
        HStack(spacing: Theme.Space.xs) {
            ForEach(options, id: \.value) { option in
                let selected = selection == option.value
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) { selection = option.value }
                } label: {
                    Text(option.label)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(selected ? Theme.onAccent : Theme.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Space.sm)
                        .background(
                            selected ? Theme.accent : .clear,
                            in: RoundedRectangle(cornerRadius: Theme.Radius.control - 3, style: .continuous)
                        )
                }
                .pressable(0.97)
                // Announced as a selected/unselected option rather than a bare
                // button. Without this, a screen labelled "Sign in" on both the mode
                // switch and the submit button gives VoiceOver two identical buttons
                // with different effects.
                .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
            }
        }
        .padding(Theme.Space.xs)
        .background(
            Theme.surfaceInset,
            in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
        )
    }
}

/// A horizontally scrolling row of filter pills.
struct FilterChip: View {
    let title: LocalizedStringKey
    var count: Int?
    let isOn: Bool
    var tint: Color = Theme.accent
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Space.xs + 2) {
                Text(title)
                if let count, count > 0 {
                    Text(verbatim: "\(count)")
                        .monospacedDigit()
                        .opacity(0.7)
                }
            }
            .font(.subheadline.weight(.medium))
            .foregroundStyle(isOn ? Theme.onAccent : Theme.textSecondary)
            .padding(.horizontal, Theme.Space.md)
            .padding(.vertical, Theme.Space.sm - 1)
            .background(isOn ? tint : Theme.surface, in: Capsule())
            .overlay(isOn ? nil : Capsule().stroke(Theme.border, lineWidth: 1))
        }
        .pressable(0.95)
        .accessibilityAddTraits(isOn ? [.isButton, .isSelected] : .isButton)
    }
}

// MARK: - States

/// A shimmering placeholder block. Loading is never a full-screen spinner — the
/// skeleton keeps the page's shape so nothing jumps when content lands.
struct Skeleton: View {
    var height: CGFloat = 16
    var width: CGFloat?
    var cornerRadius: CGFloat = Theme.Radius.control
    @State private var animating = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .fill(Theme.surfaceInset)
            .frame(width: width, height: height)
            .opacity(animating ? 0.55 : 1)
            .onAppear {
                // A forever-repeating pulse is exactly what Reduce Motion asks us
                // not to do; the flat block still reads as a placeholder.
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.9).repeatForever()) { animating = true }
            }
            .accessibilityHidden(true)
    }
}

/// Centered empty, error or first-run state.
struct StateMessage: View {
    let symbol: String
    let title: LocalizedStringKey
    var message: LocalizedStringKey?
    var actionTitle: LocalizedStringKey?
    var action: (() -> Void)?

    var body: some View {
        VStack(spacing: Theme.Space.md) {
            Image(systemName: symbol)
                .font(.system(size: 34, weight: .light))
                .foregroundStyle(Theme.textTertiary)
            Text(title)
                .font(.headline)
                .foregroundStyle(Theme.textPrimary)
                .multilineTextAlignment(.center)
            if let message {
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textSecondary)
                    .multilineTextAlignment(.center)
            }
            if let action, let actionTitle {
                Button(action: action) {
                    Text(actionTitle)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Theme.accent)
                }
                .pressable()
                .padding(.top, Theme.Space.xs)
            }
        }
        .padding(Theme.Space.xl)
        .frame(maxWidth: .infinity)
    }
}

/// An inline failure notice — for a screen that has content but could not refresh,
/// where a full-page error state would throw away what is already there.
struct InlineError: View {
    let message: String
    var retry: (() -> Void)?

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.sm) {
            Image(systemName: "exclamationmark.triangle")
                .font(.caption)
                .foregroundStyle(Theme.danger)
            Text(message)
                .font(.caption)
                .foregroundStyle(Theme.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            if let retry {
                Button(action: retry) {
                    Image(systemName: "arrow.clockwise").font(.caption.weight(.semibold))
                }
                .pressable(0.9)
                .foregroundStyle(Theme.accent)
                .accessibilityLabel("action.retry")
            }
        }
        .padding(Theme.Space.md)
        .background(
            Theme.danger.opacity(0.08),
            in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
        )
        .accessibilityIdentifier("error.inline")
    }
}
