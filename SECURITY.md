# Security policy

## Reporting a vulnerability

**Please do not open a public issue.** Report it privately through
[GitHub's private vulnerability reporting](https://github.com/rasmusrbj/todoapp/security/advisories/new)
— Security → Report a vulnerability on this repository. That keeps the discussion and any
fix private until there is something to release.

If you would rather use email, write to **security@happenings.dk**.

Please include what you can: the affected component (backend, web, CLI, iOS), a way to
reproduce it, and what an attacker gets out of it. A proof of concept helps but is not
required, and a partial report is better than none.

You will get an acknowledgement within a few days. There is no bounty programme; there is
credit in the release notes if you would like it.

## Supported versions

This project has not cut a release yet, so `main` is the only supported version. Once
there are tags, this table will say which of them still get fixes.

## What this project is, in security terms

Being straight about it, because it changes what counts as a vulnerability:

- **Nothing here is deployed.** There is no production instance. `AppConfig.productionBaseURL`
  in the iOS app points at a host that does not exist.
- **The defaults are development defaults.** `TODOAPP_SESSION_COOKIE_SECURE` is `false`,
  CORS is pinned to `http://localhost:3000`, and the backend binds loopback unless told
  otherwise. Anyone deploying this needs to change all three, plus terminate TLS.
- **`make dev-backend-lan` deliberately exposes the API to the local network** so a phone
  can reach it. It is a development server with development data; do not run it on a
  network you do not trust.
- **The seed asks for the credentials it creates** rather than shipping a pair. If you find
  a hardcoded credential anywhere in this repository, that *is* a vulnerability — please
  report it.

Findings we are already aware of, so you need not spend time on them:

- `LIST_VISIBILITY_PUBLIC` is documented as "anyone with the link may read", but every RPC
  requires a session, so it currently means "readable by any signed-in account". The copy
  is wrong, not the enforcement. Tracked as a known issue.
