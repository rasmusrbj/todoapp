import Observation
import SwiftUI

/// The landing screen: what needs doing, soonest first.
///
/// Three buckets — overdue, today, next seven days — because that is the decision
/// a person is actually making when they open a todo app. Everything else (all
/// tasks, per-list views, search) is a tab away.
struct TodayScreen: View {
    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions
    @Environment(\.locale) private var locale

    @State private var model: TodayModel?
    @State private var composing: ComposerRequest?

    var body: some View {
        NavigationStack {
            ScreenScaffold(refresh: { await model?.load() }) {
                VStack(alignment: .leading, spacing: Theme.Space.xl) {
                    greeting
                    if let viewer = session.viewer {
                        StatsRow(stats: viewer.stats)
                        if !viewer.emailVerified {
                            VerifyEmailNotice()
                        }
                    }
                    QuickAddBar(lists: model?.writableLists ?? []) { listId in
                        composing = .create(listId: listId)
                    }
                    buckets
                }
                .padding(.top, Theme.Space.sm)
            }
            .navigationTitle("nav.today")
            // Locale-independent handle for the UI tests: the visible title is
            // translated, and the app follows the *account's* language, so
            // asserting on "Today" fails for a Danish account.
            .accessibilityIdentifier("screen.today")
            .todoDestinations()
            .toolbar { AccountToolbarItem() }
        }
        .task {
            if model == nil { model = TodayModel(backend: session.backend) }
            await model?.load()
        }
        // Any successful write anywhere in the app refreshes these buckets — a task
        // completed in a list should stop being "due today" here too.
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(item: $composing) { request in
            TaskComposerSheet(request: request, lists: model?.writableLists ?? [])
        }
    }

    private var greeting: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(greetingKey)
                .font(.title2.weight(.semibold))
                .foregroundStyle(Theme.textPrimary)
            Text(Format.date(.now, locale: locale))
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Time-of-day greeting. Boundaries at 5/12/18, which is where Danish and
    /// English both agree the words change.
    private var greetingKey: LocalizedStringKey {
        let hour = Calendar.current.component(.hour, from: .now)
        let name = session.viewer?.displayName.split(separator: " ").first.map(String.init) ?? ""
        switch hour {
        case 5..<12: return "today.greetingMorning \(name)"
        case 12..<18: return "today.greetingAfternoon \(name)"
        default: return "today.greetingEvening \(name)"
        }
    }

    @ViewBuilder
    private var buckets: some View {
        if let model {
            if model.isEmptyEverywhere {
                StateMessage(
                    symbol: "checkmark.circle",
                    title: "today.allClearTitle",
                    message: "today.allClearBody"
                )
                .padding(.vertical, Theme.Space.xl)
            } else {
                if !model.overdue.isEmpty {
                    ScreenSection("today.overdue") {
                        TaskCardGroup(tasks: model.overdue) { task in
                            TaskLink(task: task)
                        }
                    }
                }
                if !model.dueToday.isEmpty {
                    ScreenSection("today.dueToday") {
                        TaskCardGroup(tasks: model.dueToday) { task in
                            TaskLink(task: task)
                        }
                    }
                }
                if !model.upcoming.isEmpty {
                    ScreenSection("today.upcoming") {
                        TaskCardGroup(tasks: model.upcoming) { task in
                            TaskLink(task: task)
                        }
                    }
                }
                if model.state.isLoading {
                    Skeleton(height: 64, cornerRadius: Theme.Radius.card)
                }
                if let failure = model.state.failure {
                    InlineError(message: failure.message(locale: locale)) {
                        Task { await model.load() }
                    }
                }
            }
        }
    }
}

/// A task row that pushes its detail screen.
///
/// Its own view so the `NavigationLink` wraps the row *without* swallowing the
/// check button's taps — a link around a row with a button inside works because
/// each is its own control, and this keeps that arrangement in one place.
struct TaskLink: View {
    let task: Todo_V1_Task
    var canEdit: Bool = true
    var showsList: Bool = true

    var body: some View {
        NavigationLink(value: TodoRoute.task(task.id)) {
            TaskRow(task: task, canEdit: canEdit, showsList: showsList)
        }
        .buttonStyle(RowButtonStyle())
    }
}

/// A row press: a background wash rather than a scale, because scaling a row
/// inside a card makes the card's border visibly detach.
struct RowButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(configuration.isPressed ? Theme.surfaceInset : .clear)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
            .contentShape(Rectangle())
    }
}

/// The four numbers worth putting above the fold.
private struct StatsRow: View {
    let stats: Todo_V1_UserStats

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            StatTile(
                value: Int(stats.openTaskCount),
                label: "today.statOpen",
                tint: Theme.textPrimary
            )
            StatTile(
                value: Int(stats.overdueTaskCount),
                label: "today.statOverdue",
                tint: stats.overdueTaskCount > 0 ? Theme.danger : Theme.textPrimary
            )
            StatTile(
                value: Int(stats.completedTaskCount),
                label: "today.statDone",
                tint: Theme.success
            )
            StatTile(
                value: Int(stats.ownedListCount + stats.sharedListCount),
                label: "today.statLists",
                tint: Theme.textPrimary
            )
        }
    }
}

private struct StatTile: View {
    let value: Int
    let label: LocalizedStringKey
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(verbatim: "\(value)")
                .font(.title3.weight(.semibold))
                .foregroundStyle(tint)
                .monospacedDigit()
                .contentTransition(.numericText())
            Text(label)
                .font(.caption2.weight(.medium))
                .foregroundStyle(Theme.textSecondary)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Space.md)
        .cardSurface(radius: Theme.Radius.control)
        .accessibilityElement(children: .combine)
    }
}

/// The composer entry point: a pill that opens the full sheet.
///
/// A tap target rather than an inline field, which is the phone idiom — an inline
/// field on a scrolling screen fights the keyboard for the space the rest of the
/// form needs. The list picker only appears when there is more than one to pick.
private struct QuickAddBar: View {
    let lists: [Todo_V1_TodoList]
    let onCompose: (String) -> Void

    @Environment(TodoSession.self) private var session
    @State private var selectedListId: String?

    private var targetList: Todo_V1_TodoList? {
        lists.first { $0.id == selectedListId } ?? lists.first
    }

    var body: some View {
        if let target = targetList {
            HStack(spacing: Theme.Space.sm) {
                AvatarView(
                    name: session.viewer?.displayName ?? "",
                    url: session.viewer?.avatarURL ?? "",
                    size: 32
                )

                Button {
                    onCompose(target.id)
                } label: {
                    HStack {
                        Text("today.quickAddPrompt")
                            .font(.subheadline)
                            .foregroundStyle(Theme.textSecondary)
                        Spacer(minLength: 0)
                        Image(systemName: "plus")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Theme.accent)
                    }
                    .padding(.horizontal, Theme.Space.lg)
                    .padding(.vertical, Theme.Space.md)
                    .background(Theme.surfaceInset, in: Capsule())
                }
                .pressable(0.98)

                if lists.count > 1 {
                    Menu {
                        Picker("today.quickAddList", selection: Binding(
                            get: { selectedListId ?? target.id },
                            set: { selectedListId = $0 }
                        )) {
                            ForEach(lists, id: \.id) { list in
                                Label(list.name, systemImage: "circle.fill")
                                    .tag(list.id)
                            }
                        }
                    } label: {
                        ColorDot(color: target.color.tint, size: 12)
                            .frame(width: 36, height: 36)
                            .background(Theme.surfaceInset, in: Circle())
                    }
                    .accessibilityLabel("today.quickAddList")
                }
            }
        }
    }
}

/// A nudge to confirm the email address, with the resend action inline.
private struct VerifyEmailNotice: View {
    @Environment(Actions.self) private var actions

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.sm) {
            Image(systemName: "envelope.badge")
                .foregroundStyle(Theme.warning)
            VStack(alignment: .leading, spacing: 2) {
                Text("settings.emailUnverified")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.textPrimary)
                Text("settings.emailUnverifiedBody")
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
            }
            Spacer(minLength: 0)
            Button("settings.resendVerification") {
                Task { await actions.resendVerificationEmail() }
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(Theme.accent)
            .pressable()
        }
        .padding(Theme.Space.md)
        .background(
            Theme.warning.opacity(0.10),
            in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
        )
    }
}

// MARK: - Model

/// Loads the three buckets and the lists the composer can write to.
@MainActor
@Observable
final class TodayModel {
    private let backend: TodoBackend

    private(set) var state: LoadState<Bool> = .loading
    private(set) var overdue: [Todo_V1_Task] = []
    private(set) var dueToday: [Todo_V1_Task] = []
    private(set) var upcoming: [Todo_V1_Task] = []
    private(set) var writableLists: [Todo_V1_TodoList] = []

    init(backend: TodoBackend) {
        self.backend = backend
    }

    var isEmptyEverywhere: Bool {
        state.hasContent && overdue.isEmpty && dueToday.isEmpty && upcoming.isEmpty
    }

    func load() async {
        // Four independent reads, so they go out together rather than in series.
        async let overdueResult = fetch(.overdue)
        async let todayResult = fetch(.today)
        async let upcomingResult = fetch(.upcoming)
        async let listsResult = fetchLists()

        let (overdueTasks, todayTasks, upcomingTasks, lists) =
            await (overdueResult, todayResult, upcomingResult, listsResult)

        // A partial failure still shows what did load. Only a total failure — where
        // there is nothing to show at all — becomes the error state.
        let failures = [overdueTasks, todayTasks, upcomingTasks].compactMap(\.failure)
        overdue = overdueTasks.value ?? []
        dueToday = todayTasks.value ?? []
        upcoming = upcomingTasks.value ?? []
        writableLists = lists

        if failures.count == 3, let first = failures.first {
            state = .failed(first)
        } else {
            state = .loaded(true)
        }
    }

    private enum Bucket { case overdue, today, upcoming }

    private func fetch(_ bucket: Bucket) async -> Result<[Todo_V1_Task], AppFailure> {
        let calendar = Calendar.current
        let startOfToday = calendar.startOfDay(for: .now)
        let startOfTomorrow = calendar.date(byAdding: .day, value: 1, to: startOfToday) ?? .now
        let inAWeek = calendar.date(byAdding: .day, value: 8, to: startOfToday) ?? .now

        let request = Todo_V1_ListTasksRequest.with {
            $0.page = .with { $0.limit = 25 }
            $0.statuses = Todo_V1_TaskStatus.open
            $0.sortField = .dueAt
            $0.sortDirection = .asc
            switch bucket {
            case .overdue:
                $0.overdueOnly = true
            case .today:
                // Both bounds, not just the upper one. With only `due_before`,
                // everything overdue also matches "today" and the same task shows
                // up in two buckets — which is exactly the bug the web had.
                $0.dueAfter = .init(date: startOfToday)
                $0.dueBefore = .init(date: startOfTomorrow)
            case .upcoming:
                $0.dueAfter = .init(date: startOfTomorrow)
                $0.dueBefore = .init(date: inAWeek)
            }
        }
        return unwrap(await backend.tasks.listTasks(request: request)) { $0.tasks }
    }

    private func fetchLists() async -> [Todo_V1_TodoList] {
        let request = Todo_V1_ListListsRequest.with {
            $0.page = .with { $0.limit = 60 }
            $0.includeArchived = false
        }
        let result = unwrap(await backend.lists.listLists(request: request)) { $0.lists }
        return (result.value ?? []).filter { $0.viewerRole.canWrite }
    }
}
