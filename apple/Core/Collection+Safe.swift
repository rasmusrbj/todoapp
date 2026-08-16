import Foundation

extension Collection {
    /// The element at `index`, or `nil` when it is out of bounds.
    ///
    /// Exists for parsing launch arguments, where `arguments[index + 1]` traps if the
    /// flag is the last thing on the command line.
    subscript(safe index: Index) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
