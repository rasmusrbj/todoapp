import Foundation

/// Where a screen's data has got to.
///
/// `empty` is separate from `loaded` on purpose: "no tasks yet" and "here are your
/// tasks" want completely different screens, and collapsing them into
/// `loaded([])` is how a blank page with no explanation ships.
enum LoadState<Value: Sendable>: Sendable {
    case loading
    case loaded(Value)
    case empty
    case failed(AppFailure)

    var value: Value? {
        if case let .loaded(value) = self { return value }
        return nil
    }

    var failure: AppFailure? {
        if case let .failed(failure) = self { return failure }
        return nil
    }

    var isLoading: Bool {
        if case .loading = self { return true }
        return false
    }

    /// True once there is something on screen, so a refresh can leave it in place
    /// instead of flashing skeletons over content the user is already reading.
    var hasContent: Bool {
        switch self {
        case .loaded, .empty: true
        case .loading, .failed: false
        }
    }
}

extension Result where Failure == AppFailure {
    /// The value, or `nil` when the call failed.
    ///
    /// For the secondary reads a screen can manage without: a task's comment list
    /// failing should not blank the task. The primary read of each screen goes
    /// through `loadState`/`listState` instead, so its failure is *shown*.
    var value: Success? { try? get() }

    /// The failure, or `nil` on success.
    ///
    /// A property rather than pattern-matching at each site so `\.failure` works as
    /// a key path — `results.compactMap(\.failure)` cannot reach the enum *case* of
    /// the same name.
    var failure: AppFailure? {
        guard case let .failure(failure) = self else { return nil }
        return failure
    }
}

extension Result where Success: Sendable, Failure == AppFailure {
    /// For a single value, which is never "empty".
    ///
    /// Deliberately a different name from `listState` rather than an overload:
    /// two `from`-style members differing only by a `Collection` constraint is
    /// ambiguous at the call site for anything that *is* a collection.
    var loadState: LoadState<Success> {
        switch self {
        case let .success(value): .loaded(value)
        case let .failure(failure): .failed(failure)
        }
    }
}

extension Result where Success: Collection & Sendable, Failure == AppFailure {
    /// For a collection, where no rows means `.empty`.
    var listState: LoadState<Success> {
        switch self {
        case let .success(collection): collection.isEmpty ? .empty : .loaded(collection)
        case let .failure(failure): .failed(failure)
        }
    }
}
