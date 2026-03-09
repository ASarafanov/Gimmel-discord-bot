CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id            TEXT PRIMARY KEY,
  enabled             INTEGER NOT NULL DEFAULT 1,
  report_channel_id   TEXT,
  timezone            TEXT NOT NULL DEFAULT 'UTC',
  daily_time          TEXT NOT NULL DEFAULT '09:00',
  template_text       TEXT NOT NULL,
  post_mode           TEXT NOT NULL DEFAULT 'single',
  mention_mode        TEXT NOT NULL DEFAULT 'no_ping',
  track_mode          TEXT NOT NULL DEFAULT 'voice_only',
  updated_at_utc      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracked_users (
  guild_id            TEXT NOT NULL,
  user_id             TEXT NOT NULL,
  display_name        TEXT,
  enabled             INTEGER NOT NULL DEFAULT 1,
  added_by_user_id    TEXT,
  added_at_utc        TEXT NOT NULL,
  PRIMARY KEY (guild_id, user_id),
  FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_activity (
  guild_id              TEXT NOT NULL,
  user_id               TEXT NOT NULL,
  last_seen_at_utc      TEXT,
  last_seen_type        TEXT,
  last_seen_channel_id  TEXT,
  last_voice_channel_id TEXT,
  updated_at_utc        TEXT NOT NULL,
  PRIMARY KEY (guild_id, user_id),
  FOREIGN KEY (guild_id, user_id) REFERENCES tracked_users(guild_id, user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_optout (
  guild_id           TEXT NOT NULL,
  user_id            TEXT NOT NULL,
  opted_out          INTEGER NOT NULL DEFAULT 0,
  opted_out_at_utc   TEXT,
  reason             TEXT,
  PRIMARY KEY (guild_id, user_id),
  FOREIGN KEY (guild_id, user_id) REFERENCES tracked_users(guild_id, user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_activity_last_seen
  ON user_activity (guild_id, last_seen_at_utc);
