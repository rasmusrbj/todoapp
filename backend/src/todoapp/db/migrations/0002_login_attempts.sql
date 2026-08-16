-- 0002_login_attempts.sql — throttling data for the sign-in endpoint.
--
-- Attempts are keyed by the *submitted* email rather than by user id, so attempts
-- against an address that does not exist are counted too. That is the whole point:
-- an attacker spraying passwords at an unknown address must not get unlimited
-- tries just because the account is absent.

CREATE TABLE login_attempts (
    id         bigserial PRIMARY KEY,
    email      citext NOT NULL,
    succeeded  boolean NOT NULL,
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Serves the "failures for this address in the last N minutes" count.
CREATE INDEX login_attempts_email_created_at_idx
    ON login_attempts (email, created_at DESC) WHERE succeeded = false;

-- Serves the periodic purge in todoapp.db.maintenance.
CREATE INDEX login_attempts_created_at_idx ON login_attempts (created_at);
