# The iOS app

A native SwiftUI client for the same ConnectRPC backend the web app and the CLI talk
to. Layout mirrors the Happenings Apple workspace, so anything learned here transfers.

```
apple/
  project.yml            XcodeGen source of truth — Todoapp.xcodeproj is generated
  gen/                   protobuf + connect-swift stubs (generated, not checked in)
  Core/                  app-agnostic plumbing: config, keychain, networking, enums
  DesignSystem/          app-agnostic UI: Theme, Components, FlowLayout
  Apps/Todo/
    iOS/App/             entry point, session, backend, actions, shell, routes
    iOS/Features/<Area>/ one directory per tab, screen + its @Observable model
    iOS/Components/      proto-aware views (task rows, badges, scaffolding)
    Resources/           Localizable.xcstrings (da + en), Assets.xcassets
    Tests/               Swift Testing unit suite + FakeTransport
    UITests/             launch smoke, live end-to-end, screenshot capture
```

## Commands

```bash
make ios-project      # regenerate the Xcode project after touching project.yml
make ios-build        # build for the simulator
make ios-test         # hermetic unit + launch tests, no backend needed
make ios-test-live    # end-to-end against `make dev-backend`
make ios-screenshots  # every screen as a PNG in apple/screenshots/
make generate         # regenerate gen/ after editing proto
```

## Running on a real phone

```bash
make ios-devices          # what is paired
make dev-backend-lan      # the API on all interfaces — required, see below
make ios-device           # build, sign, install on the first available iPhone
make ios-test-live-device # the end-to-end tests, on the phone
```

Signing comes from `Signing.xcconfig`, which is committed and deliberately empty, plus a
gitignored `Signing.local.xcconfig` holding **your** team and bundle id — write it with
`make ios-signing TEAM=ABCDE12345 [BUNDLE_ID=com.you.todoapp]`. A team id in a public
repository ties it to one Apple Developer account, and a contributor needs their own.

`-allowProvisioningUpdates` is what lets Xcode register the App ID and the device with
your team and mint the profile. Simulator builds are unsigned and need none of this.

Two things make a device different from the simulator, and both are handled:

- **`127.0.0.1` is the phone, not the Mac.** `make ios-device` bakes the Mac's Bonjour
  name (`$(scutil --get LocalHostName).local`) into `Info.plist` as `TodoappDevHost`,
  and `AppConfig` uses it on device builds. A *name*, not an IP, so a new DHCP lease
  does not break the build. ATS permits plain HTTP to it via `NSAllowsLocalNetworking`.
- **`make dev-backend` binds loopback only**, so a phone cannot reach it however it is
  addressed. `make dev-backend-lan` binds `0.0.0.0`. It exposes the development API,
  with development data, to the local network — fine on a trusted one.

If the phone still cannot reach the Mac (a network that blocks mDNS, or a different
Wi-Fi), Settings → Developer inside the app takes an explicit host — that screen exists
for exactly this, and it is compiled out of release builds.

**On-device UI testing needs a toggle only a human can flip:** Settings → Privacy &
Security → Developer Mode → **Enable UI Automation**. Without it the runner fails with
"Timed out while enabling automation mode", which says nothing about the cause.

## Architecture

**One `TodoBackend`, four Connect clients, one shared `ProtocolClient`.** Its
`init(client:)` is an additive seam: production passes an authenticated client, tests
pass a fake transport. Nothing in the app changes to make it testable.

**`Actions` is the only place that writes.** The mirror of the web's
`app/actions/` modules, for the same reason — mutations need one error sink and one
invalidation rule. Screens observe `actions.revision` and refetch when it changes, so
completing a task on Today updates the list counters and the activity feed without
either screen knowing the other exists.

**Reads live in an `@Observable` model per screen**, holding a `LoadState` that has a
distinct `.empty` case. That separation is deliberate: "no tasks yet" and "here are
your tasks" want different screens, and `loaded([])` is how a blank page with no
explanation ships.

**Failures go through `AppFailure`.** The server sends a machine-readable
`todo.v1.ErrorReason`; the reason *is* the translation key, so the same failure reads
natively in Danish and English and a new language needs no server change. The English
developer message is never shown.

## The session token is opaque, not a JWT

This is the one place the app diverges from the other Happenings apps, and
`SessionTokenStore` documents why in full. Briefly: the backend issues a single opaque
token, stores only its hash, and rotates it through `RefreshSession` — which
authenticates with the *current* token. Consequences:

- Expiry has to be remembered alongside the token; there is no claim to decode.
- The renewal call must go out on a client **without** the auth interceptor, with the
  token passed explicitly via `headers:`. Routing it through the interceptor would
  re-enter the token store that is awaiting the renewal.
- A token near expiry is still valid *now*, so a transient renewal failure returns the
  existing token rather than discarding it. Only an outright rejection signs the user
  out. Being on a train is not a reason to lose your session.

## Localization

`Localizable.xcstrings` is the source of truth, with Danish and English written
natively (not machine-translated). Rules:

- Every user-facing string is a key. `SWIFT_EMIT_LOC_STRINGS` puts new `Text("key")`
  literals into the catalog on build.
- Enum display names are keys too, resolved through `DisplayableEnum.displayKey`. A
  raw `TASK_STATUS_DONE` must never reach the screen.
- The app follows the **account's** language (`User.locale`), mirrored into
  `UserDefaults` so the first frame is right before `GetCurrentUser` returns. So a UI
  test cannot force the language with `-AppleLanguages` after sign-in — assert on
  accessibility identifiers instead.
- `LocalizationTests` reads the *compiled* `da.lproj` / `en.lproj`, not the JSON: that
  proves Xcode compiled the entry and it is reachable at runtime. It also reads
  `Localizable.stringsdict`, because plural variations compile there and reading only
  `.strings` would silently skip every count key.

## Gotchas worth knowing before you hit them

**SwiftProtobuf renames fields that collide with its own accessors.** A proto field
named `clear_due_at` becomes `clearDueAt_p`, because `clearDueAt()` is already the
generated method that unsets the optional `due_at`. Same for `clear_assignee` →
`clearAssignee_p` (the oneof clearer) and `has_more` → `hasMore_p` (the `hasX`
presence convention). Assigning the un-suffixed name is a compile error, which is the
good outcome — the bad one would be a request that silently does nothing.

**Two Swift names collide with the standard library.** A view called `TaskGroup`
resolves to Swift concurrency's `TaskGroup` and fails with a baffling error about
`ChildTaskResult`; ours is `TaskCardGroup`. A view called `Section` shadows SwiftUI's
and breaks every `Form`; ours is `ScreenSection`.

**`SettingsRow` takes both a `@ViewBuilder trailing` and an `action`.** A bare trailing
closure binds to the *builder*, so pass `action:` explicitly.

**iOS 26's `.sidebarAdaptable` tab bar is not drivable from XCUITest.** There is no
`TabBar` element and the tab buttons report `isHittable == false` — verified by dumping
the hierarchy. That is why `--initial-tab <name>` exists as a DEBUG-only launch
argument: without it the screenshot pass could not reach four of the five screens. The
live test therefore asserts on the dashboard and Settings, and leaves tab switching
alone rather than faking a tap the platform does not expose.

**Signing in triggers iOS's "Save this password?" dialog.** Being a system dialog it
swallows every subsequent tap, which surfaces as an unrelated "the Lists tab did not
load". `addUIInterruptionMonitor` handles it.

**The simulator keeps Keychain items across app uninstall.** `simctl uninstall` leaves
a valid session behind, so a test that assumes a signed-out start fails with "sign-in
screen never appeared". `LiveFlowTests` signs out first, whichever state it launched
in.

**`xcodebuild` forwards only `TEST_RUNNER_`-prefixed variables** into the UI-test
runner process. A bare `TODOAPP_LIVE_TESTS=1` reaches xcodebuild and stops there, so
the tests skip — which looks exactly like passing.

## Design rules

The Happenings system, native edition — see `DesignSystem/Theme.swift`.

- Zinc neutrals, a single accent that inverts per appearance so actions always
  contrast. The one exception is a **list's own colour**, which is content chosen by
  the user, not decoration.
- **Borders, not shadows.** The only shadow in the app is on the toast, where it
  explains that the thing floats above the content.
- 4px rhythm via `Theme.Space`; radii via `Theme.Radius`. No magic numbers in views.
- Every tappable thing scales down on press (`pressable`), with light haptics.
- Light and dark both work, resolved through `Theme.dyn`. Never hardcode a hex in a
  view.
- Loading is a `Skeleton` in the shape of the content, never a full-screen spinner.
- iPad is not a stretched phone: `.sidebarAdaptable` gives a real sidebar, lists flow
  into more columns via `GridItem(.adaptive)`, and detail panes cap to
  `Theme.readingWidth` rather than running the full width.

## Tests

- `TodoappTests` — Swift Testing. Enum semantics and wire names, localization parity,
  and the session token's renewal rules (including that concurrent readers share one
  rotation, and that a transient failure does *not* sign you out).
- `TodoappUITests/LaunchTests` — launches, draws, and asserts no untranslated key is
  on screen.
- `TodoappUITests/LiveFlowTests` — sign in, load the dashboard, open a task, reach
  Settings, sign out; plus the wrong-password path showing a translated message.
- `TodoappUITests/ScreenshotTests` — not assertions; writes PNGs for design review.
