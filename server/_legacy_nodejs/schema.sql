CREATE TABLE IF NOT EXISTS persons (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('missing', 'found', 'safe', 'deceased')),
  age INTEGER,
  location TEXT,
  notes TEXT,
  contact TEXT,
  source TEXT DEFAULT 'web',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_persons_status ON persons(status);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_location ON persons(location);
CREATE INDEX IF NOT EXISTS idx_persons_updated_at ON persons(updated_at);
