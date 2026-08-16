# Contributing

Thanks for looking. This is a contract-first stack — one Protobuf contract, four
consumers — and most of the review effort goes into keeping those four honest with each
other. The rules below exist so a change to one of them does not quietly break the rest.

## Getting set up

```bash
make setup     # installs, generates, creates the databases, migrates, seeds
make dev       # backend on :8081, web on :3000
make check     # what CI runs: lint, tests, web build
```

`make setup` **asks which email and password** you want for the demo admin account. It
writes them to `.demo-account.env`, which is gitignored and which the CLI and iOS
end-to-end targets read. No credentials live in this repository.

You need PostgreSQL 16, [uv](https://docs.astral.sh/uv/), Node 22 + pnpm, and
[buf](https://buf.build/docs/installation). `docker compose up -d` gives you PostgreSQL
if you would rather not install it.

Two things a fresh clone cannot build, and it is fair to know up front:

- **The web app needs a Font Awesome Pro token.** `web/.npmrc` reads
  `${FONTAWESOME_NPM_TOKEN}`; without a licence, `pnpm install` in `web/` will fail. The
  backend, the CLI and the iOS app are unaffected. If this blocks you, say so in an issue —
  swapping the icon set is a change we would consider.
- **The iOS app needs Xcode 26 and macOS.** Device builds additionally need your own
  Apple Developer team: `make ios-signing TEAM=ABCDE12345`. Simulator builds need nothing.

## The five rules

These are not style preferences; each one has a test that fails when it is broken.

1. **The proto is the source of truth.** Change `proto/todo/v1/*.proto` first, run
   `make generate`, then follow the type errors. Nothing generated is hand-edited, and
   nothing generated is committed.
2. **Every closed set is an enum, end to end** — proto enum, a real PostgreSQL enum type,
   and a localized display name in *every* client. Six edits; see
   [`.claude/skills/todoapp/SKILL.md`](.claude/skills/todoapp/SKILL.md).
   `tests/test_enum_parity.py` fails if the database is out of step.
3. **Authorization lives in SQL.** Every read is filtered by an `EXISTS` over
   `list_members` inside the query. There is no request shape that returns a list the
   caller cannot see. Clients only hide controls the API would refuse anyway — they never
   re-implement the rule.
4. **No raw enum and no English string ever reaches a user.** The server sends an
   `ErrorReason`; clients translate it. Danish and English are both first-class, written
   natively rather than machine-translated.
5. **Migrations are forward-only and checksummed.** Editing an applied migration makes
   `todoapp-migrate` refuse to run. Write a new one.

## Sending a pull request

1. Branch from `main`.
2. Make the change, and add the test that would have caught the bug. A PR that changes
   behaviour without a test that fails before it will get that comment.
3. Run `make check`. For iOS, `make ios-test`. For the CLI's 60 commands against a live
   server, `make cli-coverage`.
4. Write the commit message so it explains *why*. The diff already says what.
5. Open the PR and fill in the template.

Reviews look for the same things in every language: does it match the shape of the code
around it, are the enums and translations complete, is authorization enforced server-side,
and does the test actually fail without the fix.

## Style

- **Python** follows the Google style guide. Type annotations, docstrings on anything
  public, `ruff` clean. Raw SQL in repository modules, no ORM.
- **Swift 6** with strict concurrency. `apple/AGENTS.md` documents the architecture and
  the platform traps — read it before touching `apple/`.
- **TypeScript / React** — Server Components for reads, Server Actions for writes, and
  every string through `next-intl`.
- **Comments explain why, not what.** If a line needs a comment to say what it does,
  rename something instead. Comments that record a decision, a constraint or a trap you
  hit are the valuable ones.

## Reporting a security issue

Do not open a public issue. See [SECURITY.md](SECURITY.md).
