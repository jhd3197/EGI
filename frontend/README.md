# EGI Frontend

EGI's web app — an offline-first PWA built with **React + Vite**. It talks to
the Python sync server (`../server`) and falls back to cached/demo data when
offline.

## Develop

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies the API routes
(`/persons`, `/sync`, `/import`, `/health`, `/uploads`) to the Python server on
`http://localhost:3000`, so run the backend too (see `../server/README.md`).

Point the proxy at a different backend with:

```bash
EGI_API_TARGET=https://your-server.example.com npm run dev
```

## Build (what the server ships)

```bash
npm run build      # outputs to frontend/dist/
```

The FastAPI server serves `frontend/dist/` (via `FRONTEND_DIR`), so the whole
app is available at `http://localhost:3000` in production. `npm run preview`
serves the built bundle locally for a quick check.

## How it's wired

| Path | Role |
|------|------|
| `src/main.jsx` | React entry point |
| `src/App.jsx` | Top-level routing: auth → disaster picker → app shell |
| `src/store.js` | `useEgi()` hook — all state, offline cache, and sync logic |
| `src/lib/view.js` | Derives display-ready values from state (keeps components dumb) |
| `src/lib/person.js` | Normalizes/decorates person records |
| `src/lib/css.js` | `css('…')` helper — inline CSS strings → React style objects |
| `src/data/demo.js` | Fallback demo data (fictional) |
| `src/components/*` | Screens and UI pieces (Sidebar, ReportSheet, etc.) |

### Server connection

By default the app uses **same-origin** relative URLs, which is correct when
FastAPI serves the built app. To target a remote server from the browser:

```js
localStorage.setItem('egi_api_url', 'https://your-server.example.com')
```

### Offline behavior

- On load it pulls from `/sync` and `/persons`; offline it uses `localStorage`.
- New reports queue locally and `POST /sync` when the connection returns.
- Online/offline state drives the connection banner; the sidebar/topbar pill
  also toggles it manually for testing.

## What's next

- Endpoint real de `/institutions` en el servidor (refugios son demo).
- Feed de actividad real desde el servidor.
- Gestión real de emergencias en el servidor.
- Búsqueda por texto contra el servidor (hoy filtra en cliente).
- Conectar el `ImageSlot` con `POST /import/paper` para subir fotos de papel.
- Empaquetar como app Android/Capacitor; Bluetooth mesh.
