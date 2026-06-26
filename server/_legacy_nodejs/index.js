require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { getDb } = require('./db');

const app = express();
const PORT = process.env.PORT || 3000;
const TRUSTED_SOURCES = (process.env.TRUSTED_SOURCES || '').split(',').filter(Boolean);

app.use(cors());
app.use(express.json({ limit: '5mb' }));

function validateRecord(r) {
  if (!r.id || typeof r.id !== 'string') return 'id is required';
  if (!r.name || typeof r.name !== 'string') return 'name is required';
  if (!['missing', 'found', 'safe', 'deceased'].includes(r.status)) return 'invalid status';
  return null;
}

// Health check
app.get('/', (req, res) => {
  res.json({ ok: true, service: 'EGI Sync Server' });
});

// Search records
app.get('/persons', (req, res) => {
  const { q, status, location, since, limit = 100 } = req.query;
  const db = getDb();
  let sql = 'SELECT * FROM persons WHERE 1=1';
  const params = [];

  if (q) {
    sql += ' AND (name LIKE ? OR notes LIKE ?)';
    params.push(`%${q}%`, `%${q}%`);
  }
  if (status) {
    sql += ' AND status = ?';
    params.push(status);
  }
  if (location) {
    sql += ' AND location LIKE ?';
    params.push(`%${location}%`);
  }
  if (since) {
    sql += ' AND updated_at > ?';
    params.push(since);
  }
  sql += ' ORDER BY updated_at DESC LIMIT ?';
  params.push(parseInt(limit, 10) || 100);

  try {
    const rows = db.prepare(sql).all(...params);
    res.json({ records: rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  } finally {
    db.close();
  }
});

// Get single record
app.get('/persons/:id', (req, res) => {
  const db = getDb();
  try {
    const row = db.prepare('SELECT * FROM persons WHERE id = ?').get(req.params.id);
    if (!row) return res.status(404).json({ error: 'Not found' });
    res.json(row);
  } catch (err) {
    res.status(500).json({ error: err.message });
  } finally {
    db.close();
  }
});

// Receive sync batch from clients (web or mobile mesh)
app.post('/sync', (req, res) => {
  const { records } = req.body || {};
  if (!Array.isArray(records)) {
    return res.status(400).json({ error: 'records array required' });
  }

  const db = getDb();
  const insertOrReplace = db.prepare(`
    INSERT OR REPLACE INTO persons
    (id, name, status, age, location, notes, contact, source, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  try {
    db.transaction(() => {
      for (const r of records) {
        const error = validateRecord(r);
        if (error) throw new Error(error);
        const source = TRUSTED_SOURCES.includes(r.source) ? r.source : 'web';
        insertOrReplace.run(
          r.id,
          r.name.trim(),
          r.status,
          r.age || null,
          r.location ? r.location.trim() : null,
          r.notes ? r.notes.trim() : null,
          r.contact ? r.contact.trim() : null,
          source,
          r.createdAt || new Date().toISOString(),
          r.updatedAt || new Date().toISOString()
        );
      }
    })();
    res.json({ saved: records.length });
  } catch (err) {
    res.status(400).json({ error: err.message });
  } finally {
    db.close();
  }
});

// Get records changed since a timestamp
app.get('/sync', (req, res) => {
  const since = req.query.since || '1970-01-01T00:00:00Z';
  const db = getDb();
  try {
    const rows = db.prepare('SELECT * FROM persons WHERE updated_at > ? ORDER BY updated_at ASC').all(since);
    res.json({ records: rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  } finally {
    db.close();
  }
});

app.listen(PORT, () => {
  console.log(`EGI server listening on port ${PORT}`);
});
