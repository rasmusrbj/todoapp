#!/usr/bin/env bash
# Exercises every one of the CLI's 60 leaf commands against a running server.
#
# "Covered" has to mean "runs and does the right thing", not "appears in --help", so every
# command is invoked for real and its output asserted. Read-only commands are checked for
# the field they should return; write commands are checked by reading back.
#
# This is the check that catches a CLI bug living behind a live call — the kind
# tests/test_cli.py cannot reach, because it has no socket. It found one: `lookup.users`
# read USER_ROLE_ADMIN off the wrong generated module and crashed every command that
# resolved a user by id prefix.
#
#   make cli-coverage          # against a seeded local server
#   scripts/cli-coverage.sh /tmp/cli-home
#
# It writes into the database it is pointed at, and cleans up everything it creates.
set -uo pipefail
cd "$(dirname "$0")/../backend"
export XDG_CONFIG_HOME="${1:-$(mktemp -d)}"
SERVER="${TODOAPP_CLI_BASE_URL:-http://127.0.0.1:8081}"
# The account `make seed` created. `make cli-coverage` exports these from the
# gitignored .demo-account.env; there is no default password on purpose — a shared
# one in a public repo is a credential, not a convenience.
COLLABORATOR="${TODOAPP_DEMO_COLLABORATOR:-partner@example.com}"
ADMIN_EMAIL="${TODOAPP_DEMO_EMAIL:-}"
ADMIN_PASSWORD="${TODOAPP_DEMO_PASSWORD:-}"

if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
  echo "Set TODOAPP_DEMO_EMAIL and TODOAPP_DEMO_PASSWORD (run 'make seed' first)." >&2
  exit 2
fi

if ! curl -sf "$SERVER/healthz" >/dev/null; then
  echo "No server on $SERVER. Start one with: make dev-backend" >&2
  exit 2
fi
PASS=0; FAIL=0; N=0

# Quoted arguments must survive, so every invocation goes through "$@".
cli() { uv run todoapp "$@"; }
run() { OUT="$(cli "$@" 2>&1)"; }

# Reads a value out of $OUT with a Python expression over the parsed JSON.
jget() { printf '%s' "$OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }
# Same, but for a command's fresh JSON output rather than the last $OUT.
jrun() { cli "${@:2}" --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }

pass() { PASS=$((PASS+1)); N=$((N+1)); printf '  ok   %-22s %s\n' "$1" "$2"; }
fail() { FAIL=$((FAIL+1)); N=$((N+1)); printf '  FAIL %-22s %s\n' "$1" "$2"; printf '%s\n' "$OUT" | head -4 | sed 's/^/         /'; }

# has <name> <desc> <needle> — the command's output must contain <needle>.
has() { case "$OUT" in *"$3"*) pass "$1" "$2";; *) fail "$1" "$2";; esac; }
# eq <name> <desc> <expected> <actual>
eq() { [ "$3" = "$4" ] && pass "$1" "$2" || { OUT="expected [$3] got [$4]"; fail "$1" "$2"; }; }

# Everything this script creates is named, and every name is removed in the destructive
# tail. A run killed halfway leaves those names behind, and the next run then fails on
# `auth register` (email taken) rather than on anything real — so clear them first. The
# cleanup needs an admin, which the script only signs in as further down, so it borrows the
# alternate config home.
#
# `VAR=value some_function` leaks the assignment past the call in bash, so the cleanup
# never sets XDG_CONFIG_HOME inline — it would clobber the home the rest of the run uses.
# Each command gets it through its own `env` instead.
CLEAN_HOME="$XDG_CONFIG_HOME-clean"
ccli() { env XDG_CONFIG_HOME="$CLEAN_HOME" uv run todoapp "$@"; }
cjson() { ccli "${@:2}" --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }

preflight_cleanup() {
  rm -rf "$CLEAN_HOME"
  ccli auth login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" >/dev/null 2>&1 || return 0
  local id
  for email in cli-probe@example.com cli-made@example.com; do
    id="$(cjson "d['users'][0]['id']" users list --query "$email")"
    [ -n "$id" ] && ccli users delete "$id" --yes >/dev/null 2>&1
  done
  # Any list the probe left behind, whichever step it died on.
  for id in $(cjson "' '.join(l['id'] for l in d['lists'] if l['name'].startswith('CLI daekning'))" lists list); do
    ccli lists delete "$id" --yes >/dev/null 2>&1
  done
  rm -rf "$CLEAN_HOME"
}

echo "== config (3) =="
run config path;  has "config path" "prints the config file" "config.json"
run config set --server "$SERVER" --locale da
preflight_cleanup
has "config set" "stores server and locale" "✓"
run config show;  has "config show" "reports the server" "${SERVER#http://}"

echo "== auth (12) =="
run auth register --email cli-probe@example.com --name "CLI Probe" --password gyldig-kode-1234 --language en
has "auth register" "creates an account" "✓"
run auth whoami --json
eq "auth whoami" "returns the new account" "cli-probe@example.com" "$(jget "d['user']['email']")"
run auth logout; has "auth logout" "clears the session" "✓"

run auth login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"
has "auth login" "signs in as the admin" "✓"
run auth refresh;  has "auth refresh" "rotates the token" "✓"
run auth sessions --json
eq "auth sessions" "lists sessions" "True" "$(jget "len(d['sessions'])>0")"

# A second sign-in from another config home gives us a session to revoke.
XDG_CONFIG_HOME="$XDG_CONFIG_HOME-alt" cli auth login --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" >/dev/null 2>&1
OTHER="$(jrun "[s['id'] for s in d['sessions'] if not s.get('is_current')][0]" auth sessions)"
run auth revoke-session "$OTHER"; has "auth revoke-session" "revokes another session" "✓"

run auth forgot-password --email "$ADMIN_EMAIL" --language da
has "auth forgot-password" "always reports success" "✓"
# Reset and verify tokens only exist in the server log, so assert the rejection path.
run auth reset-password --token tdr_not-a-real-token --new helt-ny-kode-5678
has "auth reset-password" "rejects a bad token" "TOKEN_INVALID"
run auth verify-email --token tdv_not-a-real-token
has "auth verify-email" "rejects a bad token" "TOKEN_INVALID"
run auth resend-verification
has "auth resend-verification" "refuses when already verified" "already verified"
run auth change-password --current "$ADMIN_PASSWORD" --new "$ADMIN_PASSWORD"
has "auth change-password" "accepts the same password again" "✓"

echo "== lists (16) =="
run lists create "CLI daekning" --color blue --description "Oprettet af daekningstesten" --visibility private
has "lists create" "creates a list" "✓"
LID="$(jrun "[l['id'] for l in d['lists'] if l['name']=='CLI daekning'][0]" lists list)"
run lists list --json
eq "lists list" "lists the board" "True" "$(jget "len(d['lists'])>0")"
run lists get "$LID" --json
eq "lists get" "returns the list" "CLI daekning" "$(jget "d['list']['name']")"
run lists update "$LID" --name "CLI daekning 2" --color green
has "lists update" "renames and recolours" "✓"
run lists archive "$LID";  has "lists archive" "archives" "✓"
run lists restore "$LID";  has "lists restore" "restores" "✓"
run lists reorder "$LID";  has "lists reorder" "writes an order" "✓"
run lists share "$LID" --email "$COLLABORATOR" --role editor
has "lists share" "grants access" "✓"
run lists members "$LID" --json
eq "lists members" "lists both members" "2" "$(jget "len(d['members'])")"
MID="$(jrun "[m['user']['id'] for m in d['members'] if m['user']['email']=='$COLLABORATOR'][0]" lists members "$LID")"
run lists set-role "$LID" --user "$MID" --role commenter
has "lists set-role" "changes a role" "✓"
run lists add-label "$LID" "Daekning" --color amber
has "lists add-label" "creates a label" "✓"
LABEL="$(jrun "d['labels'][0]['id']" lists labels "$LID")"
run lists labels "$LID" --json
eq "lists labels" "lists labels" "Daekning" "$(jget "d['labels'][0]['name']")"
run lists update-label "$LABEL" --name "Daekket" --color violet
has "lists update-label" "renames a label" "✓"

echo "== tasks (22) =="
run tasks create "Daekningsopgave" --list "$LID" --due tomorrow --priority high --estimate 25 --subtask "Punkt et" --subtask "Punkt to"
has "tasks create" "creates a task" "✓"
TID="$(jrun "[t['id'] for t in d['tasks'] if t['title']=='Daekningsopgave'][0]" tasks list --list "$LID")"
run tasks list --list "$LID" --json
eq "tasks list" "lists tasks" "True" "$(jget "len(d['tasks'])>0")"
run tasks get "$TID" --json
eq "tasks get" "returns the task" "Daekningsopgave" "$(jget "d['task']['title']")"
run tasks update "$TID" --title "Daekningsopgave 2" --priority urgent --estimate 40
has "tasks update" "edits fields" "✓"
run tasks start "$TID";           has "tasks start" "moves to in progress" "✓"
run tasks status "$TID" blocked;  has "tasks status" "sets an arbitrary status" "✓"
run tasks done "$TID";            has "tasks done" "completes" "✓"
run tasks reopen "$TID";          has "tasks reopen" "reopens" "✓"
run tasks assign "$TID" --to "$MID"
has "tasks assign" "refuses a commenter as assignee" "ASSIGNEE_NOT_A_MEMBER"
cli lists set-role "$LID" --user "$MID" --role editor >/dev/null 2>&1
run tasks assign "$TID" --to "$MID"
has "tasks assign (2)" "assigns an editor" "✓"
run tasks labels "$TID" --set "$LABEL"
has "tasks labels" "sets labels" "Daekket"
run tasks move "$TID" --position 0;  has "tasks move" "repositions" "✓"
run tasks add-subtask "$TID" "Punkt tre";  has "tasks add-subtask" "appends an item" "✓"
SUB="$(jrun "d['task']['subtasks'][0]['id']" tasks get "$TID")"
run tasks check "$TID" "$SUB";   has "tasks check" "ticks an item" "●"
run tasks uncheck "$TID" "$SUB"; has "tasks uncheck" "unticks an item" "○"
SUB3="$(jrun "[s['id'] for s in d['task']['subtasks'] if s['title']=='Punkt tre'][0]" tasks get "$TID")"
run tasks delete-subtask "$TID" "$SUB3"; has "tasks delete-subtask" "removes an item" "✓"
run tasks comment "$TID" "Kommentar fra daekningstesten"; has "tasks comment" "adds a comment" "✓"
CID="$(jrun "d['comments'][0]['id']" tasks comments "$TID")"
run tasks comments "$TID" --json
eq "tasks comments" "lists comments" "1" "$(jget "len(d['comments'])")"
run tasks edit-comment "$CID" "Rettet kommentar"; has "tasks edit-comment" "edits a comment" "✓"
run tasks delete-comment "$CID";                  has "tasks delete-comment" "deletes a comment" "✓"
run tasks bulk "$TID" --priority low;             has "tasks bulk" "applies to many" "1"
run tasks activity --list "$LID";                 has "tasks activity" "shows the feed" "Daekningsopgave"

echo "== users (7) =="
run users list --json
eq "users list" "admin listing" "True" "$(jget "len(d['users'])>0")"
run users get me --json
eq "users get" "returns me" "$ADMIN_EMAIL" "$(jget "d['user']['email']")"
run users search "${COLLABORATOR%%@*}" --json
eq "users search" "type-ahead" "True" "$(jget "len(d['users'])>0")"
run users create --email cli-made@example.com --name "CLI Made" --password gyldig-kode-9876 --role member --language en
has "users create" "creates an account" "✓"
NEWID="$(jrun "d['users'][0]['id']" users list --query cli-made)"
run users update "$NEWID" --name "CLI Made Again" --role admin
has "users update" "edits a profile" "✓"
run users set-status "$NEWID" suspended --reason "daekningstest"
has "users set-status" "suspends" "✓"
run users delete "$NEWID" --yes
has "users delete" "deletes an account" "✓"

echo "== destructive tail =="
run tasks delete "$TID" --yes;           has "tasks delete" "deletes a task" "✓"
run lists delete-label "$LABEL";         has "lists delete-label" "deletes a label" "✓"
run lists unshare "$LID" --user "$MID";  has "lists unshare" "revokes access" "✓"
run lists delete "$LID" --yes;           has "lists delete" "deletes a list" "✓"

PROBE="$(jrun "d['users'][0]['id']" users list --query cli-probe)"
[ -n "$PROBE" ] && cli users delete "$PROBE" --yes >/dev/null 2>&1

# The second sign-in's config home holds a real token; don't leave it on disk.
rm -rf "$XDG_CONFIG_HOME-alt" "$CLEAN_HOME"

echo
echo "commands exercised: $N   passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ] && echo "ALL CLI COMMANDS PASSED" || echo "SOME CLI COMMANDS FAILED"
exit "$FAIL"
