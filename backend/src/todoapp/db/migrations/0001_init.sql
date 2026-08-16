-- 0001_init.sql — the whole domain in one migration.
--
-- Every closed set of values is a real PostgreSQL enum type, mirroring the proto
-- enum of the same name. The proto `*_UNSPECIFIED = 0` sentinel is deliberately
-- absent here: it exists only to satisfy proto3's zero-value rule and must never
-- reach storage. Enum values are declared in the same order as the proto so that
-- ORDER BY on an enum column sorts meaningfully (notably task_priority).
--
-- tests/test_enum_parity.py asserts both facts against pg_enum.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------------

CREATE TYPE user_role AS ENUM ('member', 'admin');

CREATE TYPE user_status AS ENUM (
    'pending_verification',
    'active',
    'suspended',
    'deactivated'
);

CREATE TYPE locale AS ENUM ('da', 'en');

CREATE TYPE theme_preference AS ENUM ('system', 'light', 'dark');

CREATE TYPE session_client AS ENUM ('web', 'mobile', 'cli');

CREATE TYPE list_visibility AS ENUM ('private', 'shared', 'public');

CREATE TYPE list_color AS ENUM (
    'zinc', 'red', 'amber', 'green', 'blue', 'violet', 'pink'
);

-- Ordered most → least privileged, matching the role ladder in
-- todoapp.domain.enums (WRITE_ROLES ⊂ COMMENT_ROLES ⊂ READ_ROLES).
CREATE TYPE member_role AS ENUM ('owner', 'editor', 'commenter', 'viewer');

CREATE TYPE task_status AS ENUM (
    'todo', 'in_progress', 'blocked', 'done', 'cancelled'
);

-- Ordered least → most urgent, so ORDER BY priority DESC puts urgent first.
CREATE TYPE task_priority AS ENUM ('none', 'low', 'medium', 'high', 'urgent');

CREATE TYPE recurrence_frequency AS ENUM (
    'none', 'daily', 'weekly', 'monthly', 'yearly'
);

CREATE TYPE activity_action AS ENUM (
    'created',
    'updated',
    'status_changed',
    'assigned',
    'unassigned',
    'commented',
    'archived',
    'restored',
    'deleted',
    'member_added',
    'member_removed',
    'member_role_changed'
);

CREATE TYPE activity_target_type AS ENUM ('list', 'task', 'comment', 'membership');

-- ---------------------------------------------------------------------------
-- Shared trigger: keep updated_at honest without trusting the application.
-- ---------------------------------------------------------------------------

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Users
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- citext gives case-insensitive uniqueness without a functional index.
    email           citext NOT NULL UNIQUE,
    -- Argon2id PHC string. Never a plaintext or reversible value.
    password_hash   text NOT NULL,
    display_name    text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 80),
    bio             text NOT NULL DEFAULT '' CHECK (length(bio) <= 500),
    avatar_url      text NOT NULL DEFAULT '',
    time_zone       text NOT NULL DEFAULT 'Europe/Copenhagen',
    role            user_role NOT NULL DEFAULT 'member',
    status          user_status NOT NULL DEFAULT 'pending_verification',
    locale          locale NOT NULL DEFAULT 'da',
    theme           theme_preference NOT NULL DEFAULT 'system',
    email_verified  boolean NOT NULL DEFAULT false,
    -- Free text set by an admin when suspending; surfaced to the user.
    status_reason   text NOT NULL DEFAULT '',
    last_seen_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    -- An account awaiting verification cannot already be verified.
    CONSTRAINT users_pending_is_unverified
        CHECK (NOT (status = 'pending_verification' AND email_verified))
);

CREATE INDEX users_status_idx ON users (status);
CREATE INDEX users_created_at_idx ON users (created_at DESC);
-- Backs the prefix search in SearchUsers / ListUsers.
CREATE INDEX users_display_name_idx ON users (lower(display_name) text_pattern_ops);

CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Sessions and one-time tokens
-- ---------------------------------------------------------------------------

CREATE TABLE sessions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    -- SHA-256 of the bearer token. The token itself is never stored.
    token_hash   bytea NOT NULL UNIQUE,
    client       session_client NOT NULL DEFAULT 'web',
    user_agent   text NOT NULL DEFAULT '',
    ip_address   inet,
    expires_at   timestamptz NOT NULL,
    last_used_at timestamptz NOT NULL DEFAULT now(),
    revoked_at   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX sessions_user_id_idx ON sessions (user_id) WHERE revoked_at IS NULL;
CREATE INDEX sessions_expires_at_idx ON sessions (expires_at);

-- Password reset and email verification share a shape but not a table: their
-- lifetimes, rate limits and blast radius differ.
CREATE TABLE password_reset_tokens (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX password_reset_tokens_user_id_idx ON password_reset_tokens (user_id);

CREATE TABLE email_verification_tokens (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX email_verification_tokens_user_id_idx ON email_verification_tokens (user_id);

-- ---------------------------------------------------------------------------
-- Lists, membership, labels
-- ---------------------------------------------------------------------------

CREATE TABLE lists (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name        text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    description text NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
    color       list_color NOT NULL DEFAULT 'zinc',
    visibility  list_visibility NOT NULL DEFAULT 'private',
    position    integer NOT NULL DEFAULT 0,
    archived_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX lists_owner_id_idx ON lists (owner_id, position, created_at);
CREATE INDEX lists_visibility_idx ON lists (visibility);

CREATE TRIGGER lists_set_updated_at BEFORE UPDATE ON lists
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE list_members (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id       uuid NOT NULL REFERENCES lists (id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role          member_role NOT NULL DEFAULT 'viewer',
    invited_by_id uuid REFERENCES users (id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (list_id, user_id)
);

CREATE INDEX list_members_user_id_idx ON list_members (user_id);

CREATE TRIGGER list_members_set_updated_at BEFORE UPDATE ON list_members
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Exactly one owner row per list, enforced in the database rather than by
-- convention. The application writes it alongside the list itself.
CREATE UNIQUE INDEX list_members_single_owner_idx
    ON list_members (list_id) WHERE role = 'owner';

CREATE TABLE labels (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id    uuid NOT NULL REFERENCES lists (id) ON DELETE CASCADE,
    name       text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 40),
    color      list_color NOT NULL DEFAULT 'zinc',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    -- Label names are unique per list. Migration 0003 folds this to lower case.
    UNIQUE (list_id, name)
);

CREATE TRIGGER labels_set_updated_at BEFORE UPDATE ON labels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Tasks
-- ---------------------------------------------------------------------------

CREATE TABLE tasks (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id              uuid NOT NULL REFERENCES lists (id) ON DELETE CASCADE,
    created_by_id        uuid REFERENCES users (id) ON DELETE SET NULL,
    assignee_id          uuid REFERENCES users (id) ON DELETE SET NULL,
    completed_by_id      uuid REFERENCES users (id) ON DELETE SET NULL,
    title                text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    description          text NOT NULL DEFAULT '' CHECK (length(description) <= 10000),
    status               task_status NOT NULL DEFAULT 'todo',
    priority             task_priority NOT NULL DEFAULT 'none',
    position             integer NOT NULL DEFAULT 0,
    due_at               timestamptz,
    -- false ⇒ due_at is an all-day date; the client renders no clock time.
    due_has_time         boolean NOT NULL DEFAULT false,
    starts_at            timestamptz,
    estimate_minutes     integer NOT NULL DEFAULT 0
                             CHECK (estimate_minutes BETWEEN 0 AND 100000),
    recurrence_frequency recurrence_frequency NOT NULL DEFAULT 'none',
    recurrence_interval  integer NOT NULL DEFAULT 1
                             CHECK (recurrence_interval BETWEEN 1 AND 365),
    recurrence_until     timestamptz,
    completed_at         timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    -- Terminal statuses carry a completion timestamp; open ones never do. Mirrored
    -- by TERMINAL_TASK_STATUSES in todoapp.domain.enums.
    CONSTRAINT tasks_completed_at_matches_status CHECK (
        (status IN ('done', 'cancelled')) = (completed_at IS NOT NULL)
    ),
    CONSTRAINT tasks_due_time_needs_due_at CHECK (due_has_time = false OR due_at IS NOT NULL),
    CONSTRAINT tasks_starts_before_due CHECK (
        starts_at IS NULL OR due_at IS NULL OR starts_at <= due_at
    ),
    CONSTRAINT tasks_recurrence_until_needs_frequency CHECK (
        recurrence_until IS NULL OR recurrence_frequency <> 'none'
    )
);

CREATE INDEX tasks_list_position_idx ON tasks (list_id, position, created_at);
CREATE INDEX tasks_assignee_idx ON tasks (assignee_id) WHERE assignee_id IS NOT NULL;
CREATE INDEX tasks_status_idx ON tasks (list_id, status);
-- Backs the overdue and agenda queries.
CREATE INDEX tasks_due_at_open_idx ON tasks (due_at)
    WHERE status NOT IN ('done', 'cancelled') AND due_at IS NOT NULL;
CREATE INDEX tasks_priority_idx ON tasks (priority);

CREATE TRIGGER tasks_set_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE task_labels (
    task_id  uuid NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    label_id uuid NOT NULL REFERENCES labels (id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, label_id)
);

CREATE INDEX task_labels_label_id_idx ON task_labels (label_id);

CREATE TABLE subtasks (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id      uuid NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    title        text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    completed_at timestamptz,
    position     integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX subtasks_task_id_idx ON subtasks (task_id, position, created_at);

CREATE TRIGGER subtasks_set_updated_at BEFORE UPDATE ON subtasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE comments (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id    uuid NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    author_id  uuid REFERENCES users (id) ON DELETE SET NULL,
    body       text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    edited     boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX comments_task_id_idx ON comments (task_id, created_at DESC);

CREATE TRIGGER comments_set_updated_at BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Activity feed
-- ---------------------------------------------------------------------------

-- Append-only. `target_label` is denormalised on purpose so the feed still reads
-- correctly after the target is renamed or deleted, and `list_id` is nullable with
-- ON DELETE SET NULL so history outlives the list.
CREATE TABLE activities (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id     uuid REFERENCES users (id) ON DELETE SET NULL,
    list_id      uuid REFERENCES lists (id) ON DELETE SET NULL,
    task_id      uuid REFERENCES tasks (id) ON DELETE SET NULL,
    action       activity_action NOT NULL,
    target_type  activity_target_type NOT NULL,
    target_id    uuid NOT NULL,
    target_label text NOT NULL DEFAULT '',
    -- Machine-readable diff. Values are enum labels or raw text, never localized:
    -- the client turns them into words.
    field        text NOT NULL DEFAULT '',
    from_value   text NOT NULL DEFAULT '',
    to_value     text NOT NULL DEFAULT '',
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX activities_list_id_idx ON activities (list_id, created_at DESC);
CREATE INDEX activities_task_id_idx ON activities (task_id, created_at DESC);
CREATE INDEX activities_actor_id_idx ON activities (actor_id, created_at DESC);
