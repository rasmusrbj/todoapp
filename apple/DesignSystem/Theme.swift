import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

/// Happenings design tokens, native edition — zinc neutrals, a single accent,
/// flat surfaces with borders instead of shadows, a 4px spatial rhythm.
///
/// Mirrors the web token layer in `web/src/app/globals.css`. Views resolve colors
/// through here rather than hardcoding hex, so light and dark are handled once.
enum Theme {
    // Zinc scale (Tailwind zinc, sRGB) — the neutral spine of the system.
    static let zinc50 = Color(hex: 0xFAFAFA)
    static let zinc100 = Color(hex: 0xF4F4F5)
    static let zinc200 = Color(hex: 0xE4E4E7)
    static let zinc300 = Color(hex: 0xD4D4D8)
    static let zinc400 = Color(hex: 0xA1A1AA)
    static let zinc500 = Color(hex: 0x71717A)
    static let zinc700 = Color(hex: 0x3F3F46)
    static let zinc800 = Color(hex: 0x27272A)
    static let zinc900 = Color(hex: 0x18181B)
    static let zinc950 = Color(hex: 0x09090B)

    /// The one action color. It inverts with appearance so a filled button always
    /// contrasts with the surface behind it: near-black on light, near-white on
    /// dark. `onAccent` is what sits on top of it.
    static let accent = dyn(light: 0x18181B, dark: 0xFAFAFA)
    static let onAccent = dyn(light: 0xFAFAFA, dark: 0x09090B)

    // Surfaces, layered background → surface → inset.
    static let background = dyn(light: 0xFAFAFA, dark: 0x09090B)
    static let surface = dyn(light: 0xFFFFFF, dark: 0x18181B)
    static let surfaceInset = dyn(light: 0xF4F4F5, dark: 0x27272A)

    /// Depth comes from these, not from shadows.
    static let border = dynAlpha(light: 0x000000, lightAlpha: 0.10, dark: 0xFFFFFF, darkAlpha: 0.08)
    static let borderStrong = dynAlpha(light: 0x000000, lightAlpha: 0.16, dark: 0xFFFFFF, darkAlpha: 0.14)

    static let textPrimary = dyn(light: 0x09090B, dark: 0xFAFAFA)
    static let textSecondary = dyn(light: 0x71717A, dark: 0xA1A1AA)
    static let textTertiary = dyn(light: 0xA1A1AA, dark: 0x71717A)

    // Status colors. Semantic only — never decoration, and never a second accent.
    static let danger = dyn(light: 0xDC2626, dark: 0xF87171)
    static let success = dyn(light: 0x16A34A, dark: 0x4ADE80)
    static let warning = dyn(light: 0xD97706, dark: 0xFBBF24)
    static let info = dyn(light: 0x2563EB, dark: 0x60A5FA)

    /// A color that resolves per appearance.
    static func dyn(light: UInt32, dark: UInt32) -> Color {
        #if canImport(UIKit)
        let lightColor = UIColor(hex: light)
        let darkColor = UIColor(hex: dark)
        return Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark ? darkColor : lightColor
        })
        #else
        return Color(hex: light)
        #endif
    }

    static func dynAlpha(light: UInt32, lightAlpha: CGFloat, dark: UInt32, darkAlpha: CGFloat) -> Color {
        #if canImport(UIKit)
        let lightColor = UIColor(hex: light).withAlphaComponent(lightAlpha)
        let darkColor = UIColor(hex: dark).withAlphaComponent(darkAlpha)
        return Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark ? darkColor : lightColor
        })
        #else
        return Color(hex: light).opacity(lightAlpha)
        #endif
    }

    /// 4px spatial rhythm. Everything spaces on these; no magic numbers in views.
    enum Space {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let xl: CGFloat = 20
        static let xxl: CGFloat = 24
    }

    enum Radius {
        static let card: CGFloat = 16
        static let control: CGFloat = 12
        static let pill: CGFloat = 999
    }

    /// Long-form text stops being readable past roughly this width. Detail panes
    /// cap to it and center rather than stretching across an iPad.
    static let readingWidth: CGFloat = 700
}

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: 1
        )
    }
}

#if canImport(UIKit)
extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}
#endif

// MARK: - Press feedback

/// Light haptics paired with a press. Kept behind one type so the whole app taps
/// with the same weight.
enum Haptics {
    enum Impact { case light, medium, rigid }

    @MainActor
    static func impact(_ style: Impact = .light) {
        #if canImport(UIKit)
        let feedback: UIImpactFeedbackGenerator.FeedbackStyle =
            switch style {
            case .light: .light
            case .medium: .medium
            case .rigid: .rigid
            }
        UIImpactFeedbackGenerator(style: feedback).impactOccurred()
        #endif
    }

    @MainActor
    static func success() {
        #if canImport(UIKit)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        #endif
    }
}

/// Scale-down press feedback — the house tactile interaction. Every tappable
/// thing in the app gets this, so nothing feels dead under a finger.
struct PressableStyle: ButtonStyle {
    var scale: CGFloat = 0.96
    var haptic: Haptics.Impact? = .light

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? scale : 1)
            .animation(.easeInOut(duration: 0.12), value: configuration.isPressed)
            .onChange(of: configuration.isPressed) { _, pressed in
                if pressed, let haptic { Haptics.impact(haptic) }
            }
    }
}

extension View {
    /// A button that scales down on press. `scale` follows the size of the target:
    /// 0.97 for buttons, 0.98 for cards, 0.95 for small icons.
    func pressable(_ scale: CGFloat = 0.96, haptic: Haptics.Impact? = .light) -> some View {
        buttonStyle(PressableStyle(scale: scale, haptic: haptic))
    }

    /// A bordered surface — the canonical container. No shadow, by rule.
    func cardSurface(radius: CGFloat = Theme.Radius.card) -> some View {
        background(Theme.surface, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .stroke(Theme.border, lineWidth: 1)
            )
    }

    /// Caps long-form content to a readable measure and centers it, so a detail
    /// pane does not run the full width of an iPad.
    func readableWidth(_ width: CGFloat = Theme.readingWidth) -> some View {
        frame(maxWidth: width)
            .frame(maxWidth: .infinity)
    }
}
