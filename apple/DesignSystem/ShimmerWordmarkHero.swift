import SwiftUI

/// The login hero the Happenings apps share: the mark and the wordmark under a single
/// left-to-right shimmer, with a subtitle cycling through rotating taglines.
///
/// The shimmer travels across mark *and* name as one band — that is the point of
/// masking the whole `HStack` rather than each piece, which would read as two separate
/// glints. It brightens dark glyphs in light mode and darkens light glyphs in dark mode,
/// so the effect survives both appearances.
///
/// Takes the mark as a view rather than an image name (the other apps pass
/// `Image("BrandMark")`); this app draws its mark from an SF Symbol, and the animation
/// should not care which.
struct ShimmerWordmarkHero<Mark: View>: View {
    let wordmark: String
    let taglines: [LocalizedStringKey]
    @ViewBuilder var mark: Mark

    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let shimmerPeriod: Double = 3.5
    private let taglineInterval: Double = 4

    @State private var taglineIndex = 0

    var body: some View {
        VStack(spacing: Theme.Space.md) {
            mark

            // The shimmer masks the **wordmark only**, not the mark.
            //
            // The consumer app sweeps one band across mark and name together, and that
            // works because its mark is a thin template glyph — the band reads as a
            // glint along a stroke. This app's mark is a solid filled tile, and the same
            // band turns half of it white: it looks like a rendering fault, not a shine.
            // So the tile keeps its own weight and the name gets the glint.
            if reduceMotion {
                // A band sweeping forever is exactly what Reduce Motion asks us not to
                // do. The wordmark is the content; the shimmer never was.
                wordmarkText
            } else {
                TimelineView(.animation) { timeline in
                    let phase = timeline.date.timeIntervalSinceReferenceDate
                        .truncatingRemainder(dividingBy: shimmerPeriod) / shimmerPeriod
                    wordmarkText
                        .overlay { shimmerBand(phase: phase).mask(wordmarkText) }
                        .compositingGroup()
                }
            }

            // All taglines stacked and cross-faded by opacity, so the hero's height is
            // fixed by the tallest and nothing below it shifts as they rotate.
            ZStack {
                ForEach(Array(taglines.enumerated()), id: \.offset) { index, line in
                    Text(line)
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.textSecondary)
                        .multilineTextAlignment(.center)
                        .opacity(taglineIndex == index ? 1 : 0)
                }
            }
            .frame(height: 22)
            .animation(.easeInOut(duration: 0.6), value: taglineIndex)
        }
        .task {
            guard taglines.count > 1, !reduceMotion else { return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(taglineInterval))
                taglineIndex = (taglineIndex + 1) % taglines.count
            }
        }
        // One element to VoiceOver: the wordmark plus whichever tagline is showing is a
        // single piece of branding, not four things to swipe through.
        .accessibilityElement(children: .combine)
    }

    private var wordmarkText: some View {
        Text(verbatim: wordmark)
            .font(.system(size: 32, weight: .bold))
            .tracking(-0.5)
            .foregroundStyle(Theme.textPrimary)
    }

    /// A highlight band travelling the full width of the hero.
    private func shimmerBand(phase: Double) -> some View {
        let bandColor = scheme == .dark ? Color.black.opacity(0.28) : Color.white.opacity(0.62)
        return GeometryReader { geometry in
            let width = geometry.size.width
            let band = max(width * 0.45, 40)
            LinearGradient(
                colors: [.clear, bandColor, .clear],
                startPoint: .leading,
                endPoint: .trailing
            )
            .frame(width: band)
            .offset(x: -band + phase * (width + band))
        }
    }
}

/// This app's mark: the checklist glyph on an accent tile.
///
/// A drawn mark rather than a bitmap, so it inverts with the appearance like every other
/// accent surface and needs no asset at any scale.
struct TodoBrandMark: View {
    var size: CGFloat = 76

    var body: some View {
        Image(systemName: "checklist")
            .font(.system(size: size * 0.5, weight: .medium))
            .foregroundStyle(Theme.onAccent)
            .frame(width: size, height: size)
            .background(
                Theme.accent,
                in: RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
            )
            .accessibilityHidden(true)
    }
}
