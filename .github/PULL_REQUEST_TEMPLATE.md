## What this changes

<!-- One or two sentences. The diff says what; say why. -->

## How it was verified

<!-- Not "it builds". Which command, and what it printed. -->

- [ ] `make check` passes (lint, backend tests, web build)
- [ ] `make ios-test` passes — *if the change touches `apple/`*
- [ ] `make cli-coverage` passes — *if the change touches the CLI or an RPC*
- [ ] A test fails without this change and passes with it

## Contract checklist

Tick what applies, delete what does not. These are the ways a change to one consumer
quietly breaks another.

- [ ] **Proto changed** → ran `make generate`, and updated every consumer the type errors
      pointed at
- [ ] **New enum value** → proto, migration, web catalogues (da + en), CLI display, iOS
      `EnumDisplay.swift` + `Localizable.xcstrings`
- [ ] **New user-facing string** → added in Danish *and* English, written natively
- [ ] **New error case** → added an `ErrorReason` with a message in every client
- [ ] **Schema changed** → a new forward-only migration; no applied migration edited
- [ ] **New read path** → filtered by the `EXISTS` over `list_members` inside the query

## Anything reviewers should look at closely

<!-- Trade-offs you made, things you were unsure about, things you deliberately left out. -->
