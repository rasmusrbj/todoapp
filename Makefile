# Everything you need to run, test, and change this project.
#
# `make setup` once, `make dev` after that. Every target is safe to re-run.

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND := backend
WEB     := web
DB_URL  ?= postgresql://postgres@localhost:5432/todoapp
TEST_DB_URL ?= postgresql://postgres@localhost:5432/todoapp_test

# Anything that touches the backend runs through uv, from the backend directory.
UV := cd $(BACKEND) && uv run
BUF := buf

# The demo account `make seed` created, for the targets that need to sign in.
#
# Written by the seed into a gitignored file rather than living here: this repository
# is public, and a real address next to a plaintext password is exactly what it must
# not carry. `-include` so every other target still works before the first seed.
DEMO_ENV := .demo-account.env
-include $(DEMO_ENV)
export TODOAPP_DEMO_EMAIL
export TODOAPP_DEMO_PASSWORD

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# --- Setup -------------------------------------------------------------------

.PHONY: setup
setup: install generate db-create migrate seed ## Full first-time setup
	@echo
	@echo "Ready. Run 'make dev' and open http://localhost:3000"
	@echo "Sign in with the account you chose during 'make seed'."

.PHONY: install
install: install-backend install-web ## Install backend and web dependencies

# Split so CI can install one side without the other — the web install needs a licensed
# icon registry token that a fork's pull request cannot have.
.PHONY: install-backend
install-backend: ## Install backend dependencies
	cd $(BACKEND) && uv sync --extra dev

.PHONY: install-web
install-web: ## Install web dependencies (needs FONTAWESOME_NPM_TOKEN)
	cd $(WEB) && pnpm install

.PHONY: generate
generate: generate-backend generate-web generate-ios ## Regenerate every client from proto/

# One target per consumer, each with its own buf config. Splitting them matters: the
# configs use `clean: true`, so a failure part-way through a combined run wipes the
# outputs it had already deleted and leaves the repo unbuildable. A rate-limited BSR
# call should cost one tree, not three.
.PHONY: generate-backend
generate-backend: ## Regenerate the Python backend stubs (remote plugins)
	$(BUF) generate --template buf.gen.backend.yaml

.PHONY: generate-web
generate-web: ## Regenerate the TypeScript client (local protoc-gen-es)
	$(BUF) generate --template buf.gen.web.yaml

.PHONY: generate-ios
generate-ios: ## Regenerate the Swift client (local protoc-gen-swift)
	$(BUF) generate --template buf.gen.swift.yaml

.PHONY: lint-proto
lint-proto: ## Lint the proto contract
	buf lint

.PHONY: breaking
breaking: ## Check the proto contract for breaking changes against main
	buf breaking --against '.git#branch=main'

# --- Database ----------------------------------------------------------------

.PHONY: db-create
db-create: ## Create the development and test databases
	-createdb -h localhost -U postgres todoapp 2>/dev/null
	-createdb -h localhost -U postgres todoapp_test 2>/dev/null
	@echo "databases ready"

.PHONY: migrate
migrate: ## Apply pending migrations
	cd $(BACKEND) && TODOAPP_DATABASE_URL=$(DB_URL) uv run todoapp-migrate

.PHONY: migrate-dry
migrate-dry: ## Show which migrations would run
	cd $(BACKEND) && TODOAPP_DATABASE_URL=$(DB_URL) uv run todoapp-migrate --dry-run

.PHONY: db-reset
db-reset: ## Drop the schema and re-migrate (development only)
	cd $(BACKEND) && TODOAPP_DATABASE_URL=$(DB_URL) uv run todoapp-migrate --reset

.PHONY: seed
seed: ## Write development seed data (asks which account to create)
	# Asks for an email and password unless TODOAPP_DEMO_EMAIL/PASSWORD are set, and
	# saves them to $(DEMO_ENV) so the CLI and iOS end-to-end targets can sign in.
	cd $(BACKEND) && TODOAPP_DATABASE_URL=$(DB_URL) uv run todoapp-seed \
		--credentials-file "$(CURDIR)/$(DEMO_ENV)"

.PHONY: db-shell
db-shell: ## Open psql against the development database
	psql $(DB_URL)

# --- Running -----------------------------------------------------------------

.PHONY: dev
dev: ## Run the backend and the web app together
	@trap 'kill 0' EXIT; \
	$(MAKE) dev-backend & \
	$(MAKE) dev-web & \
	wait

.PHONY: dev-backend
dev-backend: ## Run the ConnectRPC backend with reload
	cd $(BACKEND) && uv run uvicorn todoapp.main:app --reload --port 8081

.PHONY: dev-backend-lan
dev-backend-lan: ## Backend on all interfaces, so a phone on the same Wi-Fi can reach it
	# `dev-backend` binds loopback only, which a physical device cannot reach. This
	# exposes the dev API to the local network — fine on a trusted network, and it is
	# still a development server with development data.
	cd $(BACKEND) && uv run uvicorn todoapp.main:app --reload --host 0.0.0.0 --port 8081

.PHONY: dev-web
dev-web: ## Run the Next.js web app
	cd $(WEB) && pnpm dev

# --- Quality -----------------------------------------------------------------

.PHONY: test
test: ## Run the backend test suite
	cd $(BACKEND) && TODOAPP_TEST_DATABASE_URL=$(TEST_DB_URL) uv run pytest -q

.PHONY: test-verbose
test-verbose: ## Run the backend tests with names
	cd $(BACKEND) && TODOAPP_TEST_DATABASE_URL=$(TEST_DB_URL) uv run pytest -v

.PHONY: lint
lint: lint-proto lint-backend lint-web ## Lint everything

.PHONY: lint-backend
lint-backend: ## Lint the Python backend and CLI
	$(UV) ruff check src tests
	$(UV) ruff format --check src tests

.PHONY: lint-web
lint-web: ## Typecheck the web app and check locale parity
	cd $(WEB) && pnpm typecheck
	cd $(WEB) && pnpm check:messages

.PHONY: format
format: ## Format the backend
	$(UV) ruff check --fix src tests
	$(UV) ruff format src tests

.PHONY: typecheck
typecheck: ## Type-check both sides
	$(UV) ty check src || true
	cd $(WEB) && pnpm typecheck

.PHONY: build
# Depends on `generate-web`, not `generate`: the web build needs the TypeScript stubs
# and nothing else. Depending on the full generate put the *remote* Python plugins on
# the hot path of `make check`, and because every buf config uses `clean: true`, one
# rate-limited BSR call wiped backend/gen and left the repo unbuildable. Local codegen
# only, here.
build: generate-web ## Build the web app for production
	cd $(WEB) && pnpm build

.PHONY: check
check: lint test build ## Everything CI would run

# --- CLI ---------------------------------------------------------------------

.PHONY: cli
cli: ## Show the CLI's help
	$(UV) todoapp --help

.PHONY: cli-login
cli-login: require-demo-account ## Sign the CLI in as the seeded admin
	$(UV) todoapp auth login --email "$(TODOAPP_DEMO_EMAIL)" --password "$(TODOAPP_DEMO_PASSWORD)"

.PHONY: require-demo-account
require-demo-account:
	@test -n "$(TODOAPP_DEMO_EMAIL)" -a -n "$(TODOAPP_DEMO_PASSWORD)" || { \
		echo "No demo account yet. Run 'make seed' first."; exit 1; }

.PHONY: cli-coverage
cli-coverage: require-demo-account ## Run all 60 CLI commands against a running server
	scripts/cli-coverage.sh

# --- iOS ---------------------------------------------------------------------
# The Xcode project is generated; `apple/project.yml` is the source of truth.

APPLE := apple
IOS_PROJECT := $(APPLE)/Todoapp.xcodeproj
IOS_SIM ?= iPhone 16 Pro Max
IOS_DEST := platform=iOS Simulator,name=$(IOS_SIM)

.PHONY: ios-project
ios-project: ## Regenerate Todoapp.xcodeproj from project.yml
	cd $(APPLE) && xcodegen

.PHONY: ios-open
ios-open: ios-project ## Open the app in Xcode
	open $(IOS_PROJECT)

.PHONY: ios-build
ios-build: ios-project ## Build the iOS app for the simulator
	xcodebuild -project $(IOS_PROJECT) -scheme Todoapp -configuration Debug \
		-destination '$(IOS_DEST)' build

.PHONY: ios-test
ios-test: ios-project ## Run the hermetic iOS tests (no backend needed)
	xcodebuild -project $(IOS_PROJECT) -scheme Todoapp -configuration Debug \
		-destination '$(IOS_DEST)' \
		-only-testing:TodoappTests -only-testing:TodoappUITests/LaunchTests test

.PHONY: ios-test-live
ios-test-live: ios-project require-demo-account ## Run the end-to-end iOS tests against a running backend
	# The TEST_RUNNER_ prefix is required: xcodebuild forwards only those variables into
	# the UI-test runner process, and without it the tests silently skip.
	TEST_RUNNER_TODOAPP_LIVE_TESTS=1 \
	TEST_RUNNER_TODOAPP_DEMO_EMAIL="$(TODOAPP_DEMO_EMAIL)" \
	TEST_RUNNER_TODOAPP_DEMO_PASSWORD="$(TODOAPP_DEMO_PASSWORD)" \
	xcodebuild -project $(IOS_PROJECT) -scheme Todoapp \
		-configuration Debug -destination '$(IOS_DEST)' \
		-only-testing:TodoappUITests/LiveFlowTests test

# The Mac's Bonjour name, so a device build survives a DHCP lease change.
#
# Guarded because this is evaluated on *every* make invocation, including on the Linux
# CI runners where `scutil` does not exist — an unguarded call printed
# "scutil: command not found" in front of unrelated targets.
IOS_DEV_HOST := $(shell command -v scutil >/dev/null 2>&1 && echo "$$(scutil --get LocalHostName).local")
# First paired, available iPhone. Matched by UUID shape rather than column position:
# the device *name* column contains spaces ("rasse 15 pro max titanium"), so positional
# fields land in the middle of a name.
IOS_DEVICE_ID := $(shell xcrun devicectl list devices 2>/dev/null \
	| grep iPhone | grep -v unavailable \
	| grep -oE '[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}' \
	| head -1)

.PHONY: ios-signing
ios-signing: ## Write apple/Signing.local.xcconfig (TEAM=ABCDE12345 [BUNDLE_ID=...])
	@test -n "$(TEAM)" || { echo "Usage: make ios-signing TEAM=ABCDE12345 [BUNDLE_ID=com.you.todoapp]"; exit 1; }
	@printf '// Local, gitignored. Your Apple Developer team and bundle id.\nDEVELOPMENT_TEAM = %s\nPRODUCT_BUNDLE_IDENTIFIER = %s\n' \
		"$(TEAM)" "$(if $(BUNDLE_ID),$(BUNDLE_ID),com.example.todoapp)" > $(APPLE)/Signing.local.xcconfig
	@echo "Wrote $(APPLE)/Signing.local.xcconfig — run 'make ios-project'."

.PHONY: ios-devices
ios-devices: ## List paired physical devices
	xcrun devicectl list devices

.PHONY: ios-device
ios-device: ios-project ## Build, sign and install on a paired iPhone
	@test -n "$(IOS_DEVICE_ID)" || { echo "No available iPhone. Plug one in; see 'make ios-devices'."; exit 1; }
	@echo "Installing on $(IOS_DEVICE_ID), pointing at $(IOS_DEV_HOST):8081"
	# -allowProvisioningUpdates lets Xcode register the App ID and this device with the
	# team and mint the profile. Without it the build fails on a missing profile.
	xcodebuild -project $(IOS_PROJECT) -scheme Todoapp -configuration Debug \
		-destination 'platform=iOS,id=$(IOS_DEVICE_ID)' \
		-allowProvisioningUpdates \
		TODOAPP_DEV_HOST=$(IOS_DEV_HOST) \
		build
	# Resolve the .app into a variable and check it before handing it to devicectl.
	# Inlining the substitution meant an empty result became `NSURL = file:///` and a
	# CoreDevice "not of a type that CoreDevice recognizes" — which says nothing about
	# the actual problem.
	@APP="$$(xcodebuild -project $(IOS_PROJECT) -scheme Todoapp -configuration Debug \
			-destination 'platform=iOS,id=$(IOS_DEVICE_ID)' \
			-showBuildSettings 2>/dev/null \
			| awk -F' = ' '/ BUILT_PRODUCTS_DIR /{d=$$2} / FULL_PRODUCT_NAME /{n=$$2} END{if (d && n) print d"/"n}')"; \
	 test -n "$$APP" -a -d "$$APP" || { echo "Could not resolve the built app. Run 'make ios-build' and check for errors."; exit 1; }; \
	 echo "Installing $$APP"; \
	 xcrun devicectl device install app --device $(IOS_DEVICE_ID) "$$APP"
	@echo "Installed. Start the API with: make dev-backend-lan"

.PHONY: ios-test-live-device
ios-test-live-device: ios-project require-demo-account ## Run the end-to-end tests on a paired iPhone
	@test -n "$(IOS_DEVICE_ID)" || { echo "No available iPhone. See 'make ios-devices'."; exit 1; }
	# Needs `make dev-backend-lan`: the phone reaches the Mac by Bonjour name, not loopback.
	TEST_RUNNER_TODOAPP_LIVE_TESTS=1 \
	TEST_RUNNER_TODOAPP_API_BASE_URL=http://$(IOS_DEV_HOST):8081 \
	TEST_RUNNER_TODOAPP_DEMO_EMAIL="$(TODOAPP_DEMO_EMAIL)" \
	TEST_RUNNER_TODOAPP_DEMO_PASSWORD="$(TODOAPP_DEMO_PASSWORD)" \
	xcodebuild -project $(IOS_PROJECT) -scheme Todoapp -configuration Debug \
		-destination 'platform=iOS,id=$(IOS_DEVICE_ID)' \
		-allowProvisioningUpdates \
		TODOAPP_DEV_HOST=$(IOS_DEV_HOST) \
		-only-testing:TodoappUITests/LiveFlowTests test

.PHONY: ios-screenshots
ios-screenshots: ios-project require-demo-account ## Capture every screen as a PNG (needs a running backend)
	rm -rf $(APPLE)/screenshots && mkdir -p $(APPLE)/screenshots
	TEST_RUNNER_TODOAPP_SCREENSHOTS=1 \
	TEST_RUNNER_TODOAPP_SCREENSHOT_DIR=$(PWD)/$(APPLE)/screenshots \
	TEST_RUNNER_TODOAPP_DEMO_EMAIL="$(TODOAPP_DEMO_EMAIL)" \
	TEST_RUNNER_TODOAPP_DEMO_PASSWORD="$(TODOAPP_DEMO_PASSWORD)" \
	xcodebuild -project $(IOS_PROJECT) -scheme Todoapp -configuration Debug \
		-destination '$(IOS_DEST)' \
		-only-testing:TodoappUITests/ScreenshotTests test
	@echo "screenshots in $(APPLE)/screenshots"

# --- Docker ------------------------------------------------------------------

.PHONY: docker-up
docker-up: ## Start PostgreSQL in Docker (port 5433)
	docker compose up -d
	@echo "PostgreSQL on 5433. Use DB_URL=postgresql://postgres:postgres@localhost:5433/todoapp"

.PHONY: docker-down
docker-down: ## Stop the Docker PostgreSQL
	docker compose down

.PHONY: clean
clean: ## Remove generated code and build output
	rm -rf $(BACKEND)/gen $(WEB)/src/gen $(WEB)/.next
	find . -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "cleaned; run 'make generate' before building again"
