# EGI Server

A small Node.js + SQLite server that acts as the central sync hub for EGI clients.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/persons` | Search records (q, status, location, since, limit) |
| GET | `/persons/:id` | Get one record |
| POST | `/sync` | Upload a batch of records |
| GET | `/sync?since=ISO8601` | Download records changed since timestamp |

## Setup

```bash
cd server
cp .env.example .env
npm install
npm run db:init
npm start
```

## Production

- Set a strong `DB_PATH` outside the repository if you want.
- Put the server behind HTTPS (Caddy or Nginx).
- Back up `data/egi.db` regularly.
- Use PM2 or systemd to keep the process alive.

Example systemd service file path: `docs/egi-server.service`
