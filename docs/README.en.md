<div align="center">

# EGI

<img width="720" alt="EGI mobile app preview" src="../frontend/screenshots/mobile-home.png" />

**EMERGENCIA · GENTE · INFO**

An open-source, offline-first emergency information system for helping families
find each other after disasters, even when internet access is limited.

[Español](../README.md) | English | [Português](README.pt.md) | More languages welcome

<br>

![Offline First](https://img.shields.io/badge/offline-first-E5343B?style=for-the-badge)
![PWA](https://img.shields.io/badge/PWA-ready-1A1714?style=for-the-badge)
![Node.js](https://img.shields.io/badge/Node.js-server-339933?style=for-the-badge&logo=node.js&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Android](https://img.shields.io/badge/Android-planned-3DDC84?style=for-the-badge&logo=android&logoColor=black)
![BLE](https://img.shields.io/badge/Bluetooth_LE-planned-0082FC?style=for-the-badge&logo=bluetooth&logoColor=white)

[Features](#-features) · [Quick Start](#-quick-start) · [Screenshots](#-screenshots) · [Architecture](#-architecture) · [Roadmap](#-roadmap) · [Docs](#-documentation) · [Contributing](#-contributing)

</div>

---

## 💡 Why EGI Exists

After a disaster, people need answers quickly:

> Is my family member safe?  
> Where were they last seen?  
> Has someone already reported them?  
> Can this information still move if the internet is down?

In many emergencies, people rely on WhatsApp groups, screenshots, reposts,
paper lists, and spreadsheets. Those tools matter, but they are hard to search,
easy to duplicate, and difficult to keep updated.

**EGI** exists to make emergency people information easier to register, search,
sync, translate, and self-host.

The name means:

**Emergencia**: built for crisis situations  
**Gente**: centered on people, families, and communities  
**Info**: focused on useful, searchable information

This project started from a Venezuelan emergency context, but it is designed for
any community that needs a lightweight family reunification system.

---

## 📸 Screenshots

> Prototype/demo screenshots. Data shown in screenshots should be treated as fictional unless documented otherwise.

<details open>
<summary><strong>Mobile Home</strong>: emergency dashboard, people search, report actions, and offline status</summary>

![EGI mobile home](../frontend/screenshots/mobile-home.png)

</details>

<details>
<summary><strong>Desktop Modal</strong>: larger screen workflow for viewing or editing emergency information</summary>

![EGI desktop modal](../frontend/screenshots/desktop-modal.png)

</details>

---

## 🎯 Features

### 🧭 Emergency Registry

**Person reports**: register someone as `missing`, `found`, `safe`, or `deceased`

**Local search**: search by name, status, location, notes, or other keywords

**Event context**: designed around a specific disaster or emergency, not a generic database

**Community hosting**: any group can deploy its own server and manage its own data

### 📡 Offline First

**Local storage**: the web app saves records on the device first

**Progressive Web App**: works from a browser and can be installed on supported phones

**Sync when online**: records can sync with the server when internet is available

**Low-bandwidth design**: intended for phones, unstable data, and crisis conditions

### 🔵 Bluetooth Mesh Vision

**Android first**: the future native app will focus on Android because it gives better access to Bluetooth features

**Bluetooth Low Energy**: planned peer-to-peer sync between nearby phones

**Store and forward**: phones can exchange records offline, then upload later when any device gets internet

**Shared protocol draft**: see [`mobile/shared/protocol.md`](../mobile/shared/protocol.md)

### 🌎 Languages

**Spanish first**: the project started from a Venezuelan context

**English support**: useful for contributors, operators, and international response teams

**More languages welcome**: Portuguese, Indigenous languages, and local community translations

**Plain-language goal**: emergency software should be clear to non-technical users

### 🔒 Safety and Privacy

**No ads or tracking**: this project should not monetize crisis data

**Minimal data collection**: only collect what is useful for reunification and response

**Moderation ready**: public deployments should review false, harmful, duplicated, or abusive reports

**Sensitive information warning**: photos, phone numbers, ID numbers, and exact addresses require care

---

## 🚀 Quick Start

### Web App

The backend serves the frontend automatically. With the server running on
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

Run the Python, FastAPI and SQLite sync API:

```bash
cd server
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
python -m db
uvicorn main:app --host 127.0.0.1 --port 3000 --reload
```

Default URL (frontend + API):

```text
http://localhost:3000
```

For a deployed server, set the API URL in the browser:

```js
localStorage.setItem('egi_api_url', 'https://your-server.example.com');
```

### Android

The Android app is planned and partially scaffolded. See
[`mobile/android/README.md`](../mobile/android/README.md) for the current direction.

---

## 🏗️ Architecture

```text
                              INTERNET AVAILABLE
                                     │
                                     ▼
┌──────────────────────┐      ┌──────────────────────┐
│      Web / PWA       │      │     Android App       │
│  IndexedDB storage   │      │  Local mobile store   │
└──────────┬───────────┘      └──────────┬───────────┘
           │                             │
           │ HTTPS /sync                 │ Bluetooth LE sync
           │                             │ (planned)
           ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                    EGI Server                       │
│              Node.js + Express + SQLite             │
│                                                     │
│  GET /persons       search records                  │
│  GET /persons/:id   fetch one record                │
│  POST /sync         upload changed records          │
│  GET /sync          download changed records        │
└─────────────────────────────────────────────────────┘
```

The web app and future Android app should both keep local data first. The server
acts as a sync hub, not as the only place where records can exist.

---

## 🗺️ Roadmap

- [x] Offline-first web app prototype
- [x] Browser local storage with IndexedDB
- [x] Basic person registration and search
- [x] Node.js + SQLite sync server
- [x] Public contribution and conduct files
- [x] Android folder and Bluetooth protocol draft
- [ ] Multilingual UI structure
- [ ] Spanish and English app strings
- [ ] Import and export of local records
- [ ] Photo support with careful privacy controls
- [ ] Duplicate detection and merge workflow
- [ ] Moderation queue for public deployments
- [ ] Android WebView wrapper
- [ ] Native Android local database
- [ ] Bluetooth LE discovery and pairing
- [ ] Bluetooth record exchange
- [ ] Deployment guide for VPS and community servers
- [ ] Security and privacy review
- [ ] Accessibility review

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`frontend/README.md`](../frontend/README.md) | Web app setup, deployment, and TODOs |
| [`docs/README.pt.md`](README.pt.md) | Portuguese README |
| [`server/README.md`](../server/README.md) | Sync API endpoints and server setup |
| [`mobile/android/README.md`](../mobile/android/README.md) | Android app direction and Bluetooth notes |
| [`mobile/shared/protocol.md`](../mobile/shared/protocol.md) | Draft Bluetooth mesh sync protocol |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | How to contribute |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Community expectations |
| [`LICENSE`](../LICENSE) | MIT license |

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|------------|
| Web app | Vanilla HTML, CSS, JavaScript, Service Worker |
| Local web storage | IndexedDB |
| Server | Python, FastAPI |
| Database | SQLite |
| OCR / AI | Tesseract + Prompture |
| Mobile | Android planned, Kotlin direction |
| Offline mesh | Bluetooth Low Energy planned |
| Deployment | Single backend serves web + API, VPS or small server |

---

## 🔒 Privacy Principles

EGI may handle sensitive personal information. Treat it with care.

- Collect the minimum useful information.
- Use HTTPS for public deployments.
- Back up the database securely.
- Avoid publishing unnecessary phone numbers, ID numbers, exact addresses, or photos.
- Make unverified reports visibly unverified.
- Prefer soft updates and corrections over deleting history silently.
- Do not add analytics, advertising, or tracking pixels.
- Remove harmful, false, abusive, or exploitative content quickly.

EGI is a community coordination tool. It is not a replacement for emergency
services, shelters, hospitals, local responders, or trusted humanitarian groups.

---

## 🤝 Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](../CONTRIBUTING.md)
before opening a pull request.

```text
fork -> feature branch -> commit -> push -> pull request
```

Priority areas:

- Android Bluetooth Low Energy sync
- Offline-first PWA improvements
- Spanish and English translations
- Accessibility and plain-language UX
- Security and privacy review
- Deployment documentation
- Duplicate detection and moderation workflows
- Real-world testing in low-connectivity environments

Small contributions matter. If you notice a bug, open an issue. If you can fix
it, open a pull request.

---

## ⚠️ Disclaimer

EGI is an open-source community project, not an official government service or
emergency authority. Information entered into the system may be incomplete,
duplicated, outdated, or unverified.

In an emergency, follow official safety instructions when available and contact
local emergency services, shelters, hospitals, or trusted humanitarian
organizations.

---

<div align="center">

**EGI**: Emergencia · Gente · Info

Built for Venezuela, and for every place where families are trying to find each other.

</div>
