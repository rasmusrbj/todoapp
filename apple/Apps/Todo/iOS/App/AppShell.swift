import SwiftUI

/// The signed-in shell.
///
/// Four content tabs plus search — five slots, which is what iPhone shows before it
/// starts folding the rest into a "More" list. Settings is deliberately *not* a tab:
/// with six, iOS pushed both Settings and Search behind "More", and a "More" tab is
/// where features go to be forgotten. It lives behind the avatar in the Today
/// toolbar instead, which is also where people look for their account.
///
/// `.sidebarAdaptable` is what makes this a real sidebar on iPad rather than a
/// stretched phone tab bar — and the system, not us, owns the switch and the
/// customisation that comes with it.
struct AppShell: View {
    @Environment(TodoSession.self) private var session

    /// Which tab is showing. Held here so a deep link can switch tabs, not only push.
    @State private var selection: Section

    enum Section: Hashable, CaseIterable {
        case today, lists, tasks, activity, search

        /// Parsed from the launch argument below.
        init?(argument: String) {
            switch argument {
            case "today": self = .today
            case "lists": self = .lists
            case "tasks": self = .tasks
            case "activity": self = .activity
            case "search": self = .search
            default: return nil
            }
        }
    }

    init() {
        #if DEBUG
        // `--initial-tab lists` opens straight onto a tab.
        //
        // A debug-only seam for the screenshot pass, and it earns its place: on iOS 26
        // a `.sidebarAdaptable` tab bar exposes no `TabBar` element and its buttons
        // report `isHittable == false`, so a UI test cannot switch tabs at all. Without
        // this, four of the five screens could not be captured. It is compiled out of
        // release builds entirely.
        let arguments = ProcessInfo.processInfo.arguments
        if let index = arguments.firstIndex(of: "--initial-tab"),
           let raw = arguments[safe: index + 1],
           let section = Section(argument: raw) {
            _selection = State(initialValue: section)
            return
        }
        #endif
        _selection = State(initialValue: .today)
    }

    var body: some View {
        TabView(selection: $selection) {
            Tab("nav.today", systemImage: "sun.max", value: Section.today) {
                TodayScreen()
            }
            Tab("nav.lists", systemImage: "square.stack.3d.up", value: Section.lists) {
                ListsScreen()
            }
            Tab("nav.tasks", systemImage: "checklist", value: Section.tasks) {
                TasksScreen()
            }
            Tab("nav.activity", systemImage: "clock.arrow.circlepath", value: Section.activity) {
                ActivityScreen()
            }

            // The search role gives search its own slot on iPhone and folds it into the
            // sidebar's search field on iPad — the platform's own idiom in each case,
            // and the closest native equivalent to the web's ⌘K palette.
            Tab(value: Section.search, role: .search) {
                SearchScreen()
            }
        }
        .tabViewStyle(.sidebarAdaptable)
    }
}

/// The account button that opens Settings — the avatar in a screen's top-trailing
/// corner.
///
/// A `ToolbarContent` so each tab's own `NavigationStack` pushes Settings, keeping
/// the back button and the tab's state intact.
struct AccountToolbarItem: ToolbarContent {
    @Environment(TodoSession.self) private var session

    var body: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            NavigationLink(value: TodoRoute.settings) {
                AvatarView(
                    name: session.viewer?.displayName ?? "",
                    url: session.viewer?.avatarURL ?? "",
                    size: 30
                )
                // `AvatarView` hides itself from accessibility (a row usually names
                // the person next to it); here it *is* the control, so the button
                // needs its own label.
                .accessibilityHidden(false)
            }
            .accessibilityLabel("nav.settings")
            .accessibilityIdentifier("nav.account")
        }
    }
}
