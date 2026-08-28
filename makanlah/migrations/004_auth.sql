-- Accounts, sessions and saved preferences.
--
-- Auth exists to PERSIST PREFERENCES, not to guard the corpus. /recommend stays
-- open: the product promises a decision in under two minutes and a login wall in
-- front of search breaks that (docs/PRODUCT.md).
--
-- Every migration re-runs on every deploy, so everything here is idempotent.

create table if not exists app_user (
  id            uuid primary key default gen_random_uuid(),
  -- Stored already lower-cased by the application, so a plain unique constraint
  -- does the work of citext without depending on the extension being installed.
  email         text not null unique,
  password_hash text,
  is_guest      boolean not null default false,
  created_at    timestamptz not null default now()
);

create table if not exists user_session (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references app_user(id) on delete cascade,
  -- The token itself is never stored. A leaked dump must not yield live sessions.
  token_hash text not null unique,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists user_session_user_idx on user_session (user_id);
create index if not exists user_session_expiry_idx on user_session (expires_at);

create table if not exists user_pref (
  user_id    uuid primary key references app_user(id) on delete cascade,
  prefs      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- The shared guest. ONE row that every "Sign In As Guest" lands on, so anything
-- written under it is visible to every other guest -- which is why the API
-- reports `shared: true` and the client must disclose it BEFORE the click.
-- It has no password_hash, so the login path can never authenticate as it.
insert into app_user (email, password_hash, is_guest)
values ('guest@makanlah.local', null, true)
on conflict (email) do nothing;

-- A password_hash is required for a real account and forbidden for the guest.
-- Enforced here rather than in application code, because a guest that could be
-- logged into with a password would be a shared account with a shared password.
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'app_user_guest_has_no_password') then
    alter table app_user add constraint app_user_guest_has_no_password
      check ((is_guest and password_hash is null) or (not is_guest and password_hash is not null));
  end if;
end $$;
