<div align="center">

# EGI

<img width="720" alt="EGI mobile app preview" src="frontend/screenshots/mobile-home.png" />

**EMERGENCIA · GENTE · INFO**

An open-source, offline-first, self-hostable system to help families find each
other after a disaster, even when internet access is limited or unstable.

English | [Español](docs/README.es.md) | [Português](docs/README.pt.md) | More languages welcome

<br>

![Offline First](https://img.shields.io/badge/offline-first-E5343B?style=for-the-badge)
![PWA](https://img.shields.io/badge/PWA-ready-1A1714?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-server-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Prompture](https://img.shields.io/badge/Prompture-AI%20extraction-8A2BE2?style=for-the-badge)
![Android](https://img.shields.io/badge/Android-in%20development-3DDC84?style=for-the-badge&logo=android&logoColor=black)
![BLE](https://img.shields.io/badge/Bluetooth_LE-in%20development-0082FC?style=for-the-badge&logo=bluetooth&logoColor=white)

[Features](#-features) · [Quick Start](#-quick-start) · [Screenshots](#-screenshots) · [Architecture](#-architecture) · [Roadmap](#-roadmap) · [Docs](#-documentation) · [Contributing](#-contributing)

</div>

---

## 💡 Why EGI Exists

After a disaster, people need answers fast:

> Is my family member safe?  
> Where were they last seen?  
> Has someone already reported them?  
> Can this information move even when there is no internet?

In many emergencies, people end up relying on WhatsApp groups, screenshots,
reposts, paper lists, and spreadsheets. Those tools help, but they are hard to
search, easy to duplicate, and difficult to keep updated.

**EGI** exists to make emergency information about people easier to register,
search, sync, translate, and self-host.

The name means:

**Emergencia**: built for crisis situations  
**Gente**: centered on people, families, and communities  
**Info**: focused on useful, searchable information

This project started from a Venezuelan context, but it is designed for any
community that needs a lightweight family reunification system.

---

## 📸 Screenshots

> Prototype/demo screenshots. Data shown in the screenshots should be treated as fictional unless documented otherwise.

<details open>
<summary><strong>Mobile Home</strong>: emergency dashboard, people search, report actions, and offline status</summary>

![EGI mobile home](frontend/screenshots/mobile-home.png)

</details>

<details>
<summary><strong>Desktop Modal</strong>: larger screen workflow for viewing or editing emergency information</summary>

![EGI desktop modal](frontend/screenshots/desktop-modal.png)

</details>

---

## 🎯 Features

### 🧭 Emergency Registry

**Person reports**: register someone as `missing`, `found`, `safe`, or `deceased`

**Local search**: search by name, status, location, notes, or other keywords

**Event context**: designed around a specific disaster or emergency, not a generic database

**Community hosting**: any group can deploy its own server and own its data

### 📡 Offline First

**Local storage**: the web app saves records on the device first

**Progressive Web App**: works from a browser and can be installed on supported phones

**Sync when online**: records can sync with the server when connectivity returns

**Low-bandwidth design**: built for phones, unstable data, and crisis conditions

### 🔵 Bluetooth Mesh (In Development)

**Android first**: the native app focuses on Android because it offers better Bluetooth access.

**Bluetooth Low Energy**: functional peer-to-peer sync between nearby phones (GATT index exchange + bloom filter + store-and-forward).

**Store and forward**: phones exchange records offline and upload them when any device gets internet.

**Wi-Fi Direct planned**: bulk transfer for photos and large record batches.

**Protocol draft**: see [`mobile/shared/protocol.md`](mobile/shared/protocol.md).

### 📄 Paper Import With OCR + AI

**Tesseract OCR**: extracts text from photos of lists, flyers, or paper forms.

**Structured extraction with Prompture**: turns OCR text into fields like name, age, location, and status.

**Clear provenance**: each OCR record stores which image it was extracted from and its original text.

**Human review**: OCR records enter as drafts (`reviewed=0`) until a moderator approves them.

**No paper required**: you can still create manual reports directly in the app.

### 🧑‍⚖️ Moderation & Data Quality

**Moderation queue**: OCR, AI, PFIF, and SMS records enter as untrusted until reviewed (`/moderation/pending`).

**Duplicate detection**: fuzzy clustering by cédula, name+age, and location+time; soft merge with preserved history.

**Report confidence**: reports have tiers (`self`, `official`, `witness`, `ocr`) and the displayed status is derived from the most trustworthy, most recent report.

**SMS fallback**: emergency text check-in for areas without data (`EGI CHECKIN ...`).

### 🌎 Languages

**Spanish first**: the project started from a Venezuelan emergency

**English as a second language**: useful for contributors, operators, and international efforts

**More languages welcome**: Portuguese, Indigenous languages, and local community translations

**Plain language**: emergency software should be understandable without being technical

### 🔒 Safety and Privacy

**No ads or tracking**: this project should not monetize crisis data

**Minimal data collection**: only ask for information useful for reunification and response

**Moderation ready**: public deployments should review false, harmful, duplicated, or abusive reports

**Care with sensitive data**: photos, phone numbers, ID numbers, documents, and exact addresses require special care

---

## 🚀 Quick Start

### Web App

The backend serves the frontend automatically. With the server running at
`http://localhost:3000`, open:

```text
http://localhost:3000
```

For UI-only development you can also serve `frontend/` separately:

```bash
cd frontend
python -m http.server 8081
```

### Server

Run the sync API with Python, FastAPI, and SQLite:

```bash
cd server
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python -m db
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

Default API URL:

```text
http://localhost:3000
```

The web app points to `http://localhost:3000` by default. To use a deployed
server, set the API URL in the browser:

```js
localStorage.setItem('egi_api_url', 'https://your-server.example.com');
```

### Android

The Android app is in active development: BLE advertise/scan, GATT exchange,
Room DB, cloud sync, and the PWA bridge are already implemented. Mesh mode works
between nearby devices; Wi-Fi Direct bulk transfer and the foreground service are
in progress. See [`mobile/android/README.md`](mobile/android/README.md).

---

## 🏗️ Architecture

```text
                              INTERNET AVAILABLE
                                     │
                                     ▼
┌──────────────────────┐      ┌──────────────────────┐
│      Web / PWA       │      │      Android App      │
│  served by backend   │      │  Local mobile store   │
└──────────┬───────────┘      └──────────┬───────────┘
           │                             │
           │ HTTPS /sync                 │ Sync over Bluetooth LE
           │ + static files              │ (in development)
           │                             │ Wi-Fi Direct (planned)
           ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                    EGI Server                       │
│         Python + FastAPI + SQLite (port 3000)       │
│                                                     │
│  GET /               web app                        │
│  GET /persons        search records                 │
│  GET /persons/{id}   fetch one record               │
│  POST /sync          upload changed records         │
│  GET /sync           download changed records       │
│  POST /import/paper  OCR + AI on paper reports      │
│  GET|POST /moderation moderation queue              │
│  GET|POST /duplicates duplicate detection           │
│  POST /sms/webhook   SMS check-in                   │
└─────────────────────────────────────────────────────┘
```

The web app and the Android app store data locally first. The server works as a
sync hub, not as the only place where records can exist.

---

## 🗺️ Roadmap

See the full and updated roadmap in [`docs/roadmap.md`](docs/roadmap.md). Below is a summary of the current state:

### Done
- [x] Offline-first web prototype
- [x] Browser local storage (currently `localStorage`; IndexedDB migration in progress, see plan-06)
- [x] Basic person registration and search
- [x] Public contribution and conduct files
- [x] Python + FastAPI + SQLite server
- [x] Sync server with timestamp-guarded last-write-wins
- [x] OCR endpoint to import paper reports
- [x] Structured extraction with Prompture / local LLM fallback
- [x] Moderation queue (`/moderation`)
- [x] Fuzzy duplicate detection and soft-merge workflow (`/duplicates`)
- [x] Confidence-based derived status (`self > official > witness > ocr`)
- [x] SMS check-in fallback (`/sms/webhook`)
- [x] `egi` CLI (backend, frontend, build, seed, unseed, export/import, synthetic)
- [x] Android folder with BLE advertise/scan, GATT exchange, Room DB, cloud sync, JS bridge
- [x] Server and frontend test suites + CI

### In progress
- [ ] Migrate PWA cache from `localStorage` to IndexedDB
- [ ] Bluetooth mesh encryption + privacy warning
- [ ] Mesh UI in the PWA
- [ ] Reports (PFIF notes) over the mesh
- [ ] Wi-Fi Direct bulk transfer

### Pending
- [ ] Multilingual UI structure
- [ ] App strings in Spanish, English and Portuguese
- [ ] Import and export of local records (CLI partial; UI pending)
- [ ] Photo support with careful privacy controls
- [ ] Android WebView wrapper fully wired
- [ ] Deployment guide for VPS and community servers
- [ ] Security and privacy review (CORS, rate limiting, operator auth)
- [ ] Accessibility review

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`README.md`](../README.md) | English README (this file, canonical) |
| [`docs/README.en.md`](docs/README.en.md) | English README (docs copy) |
| [`docs/README.es.md`](docs/README.es.md) | Spanish README |
| [`docs/README.pt.md`](docs/README.pt.md) | Portuguese README |
| [`docs/roadmap.md`](docs/roadmap.md) | Consolidated roadmap for plans 01-07 |
| [`frontend/README.md`](../frontend/README.md) | Web app setup, deployment, and TODOs |
| [`server/README.md`](../server/README.md) | Sync API endpoints and Python server setup |
| [`mobile/android/README.md`](../mobile/android/README.md) | Android app direction and Bluetooth notes |
| [`mobile/shared/protocol.md`](../mobile/shared/protocol.md) | Draft Bluetooth mesh sync protocol |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | How to contribute |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Community expectations |
| [`LICENSE`](../LICENSE) | MIT license |

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|------------|
| Web app | React + Vite (offline-first PWA) |
| Local web storage | `localStorage` (IndexedDB migration planned) |
| Server | Python, FastAPI |
| Database | SQLite |
| OCR / AI | Tesseract + Prompture / Ollama / OpenAI |
| Mobile | Android (Kotlin + Room + BLE) |
| Offline mesh | Bluetooth Low Energy + Wi-Fi Direct (planned) |
| Deployment | Single backend serves web + API; VPS or community server |
| Tests | pytest (server), vitest (frontend), JVM unit tests (Android) |

---

## 🔒 Privacy Principles

EGI may handle sensitive personal information. Treat it with care.

- Collect only the minimum useful information.
- Use HTTPS in public deployments.
- Back up the database securely.
- Avoid publishing unnecessary phone numbers, ID numbers, documents, exact addresses, or photos.
- Make unverified reports visibly unverified.
- Prefer corrections and history over deleting data silently.
- Do not add analytics, advertising, or tracking pixels.
- Quickly remove harmful, false, abusive, or exploitative content.

EGI is a community coordination tool. It does not replace emergency services,
shelters, hospitals, local responders, or trusted humanitarian organizations.

---

## 🤝 Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md)
before opening a pull request.

```text
fork -> feature branch -> commit -> push -> pull request
```

Priority areas:

- Migrate PWA cache from `localStorage` to IndexedDB
- Bluetooth mesh encryption + privacy warning
- Mesh UI in the PWA
- Reports (PFIF notes) over the mesh
- Wi-Fi Direct bulk transfer
- Multilingual UI (es/en/pt) and community languages
- Accessibility and plain-language UX
- Security and privacy review (CORS, rate limiting, operator auth)
- Deployment documentation for VPS and community servers
- Real-world testing in low-connectivity environments

Small contributions matter. If you find a bug, open an issue. If you can fix it,
open a pull request.

---

## ⚠️ Disclaimer

EGI is an open-source community project, not an official government service or
emergency authority. Information entered into the system may be incomplete,
duplicated, outdated, or unverified.

In an emergency, follow official safety instructions when available and contact
emergency services, shelters, hospitals, or trusted humanitarian organizations.

---

<div align="center">

**EGI**: Emergencia · Gente · Info

Built for Venezuela, and for every place where a family is trying to find their own.

</div>
