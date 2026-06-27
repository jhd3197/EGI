# Push Notifications Setup (Web Push + FCM)

Plan-16. EGI can push alerts to the PWA (Web Push / VAPID) and to Android (Firebase
Cloud Messaging). **Both are optional.** Out of the box the push hub uses the
`log` driver: subscribe / unsubscribe and alert fan-out work end to end with
**zero credentials and nothing extra installed** — messages are recorded as sent
without any external call. Configure a real driver only when you have credentials.

The driver is chosen by `PUSH_PROVIDER` (env) or a `message_providers` row:

```bash
PUSH_PROVIDER=log       # default — record only, no external call
PUSH_PROVIDER=webpush   # Web Push to the PWA (needs VAPID keys + pywebpush)
PUSH_PROVIDER=fcm       # Firebase Cloud Messaging to Android
```

Each subscription also carries its own `kind` (`webpush` / `fcm`), so a mixed
fleet works regardless of the default driver.

## Web Push (VAPID) for the PWA

Web Push needs a VAPID key pair (one per deployment) and the optional
`pywebpush` package for payload encryption.

1. **Install the dependency** (uncomment it in `server/requirements.txt`):

   ```bash
   pip install pywebpush
   ```

2. **Generate a VAPID key pair** once. `pywebpush` ships the `py-vapid` CLI:

   ```bash
   vapid --gen
   ```

   This writes `private_key.pem` / `public_key.pem` and prints the
   `Application Server Key` (the base64url public key the browser subscribes with).

   OpenSSL equivalent:

   ```bash
   openssl ecparam -name prime256v1 -genkey -noout -out vapid_private.pem
   openssl ec -in vapid_private.pem -pubout -out vapid_public.pem
   ```

3. **Set the env vars** (`server/.env`):

   ```bash
   PUSH_PROVIDER=webpush
   VAPID_PUBLIC_KEY=<base64url application server key>
   VAPID_PRIVATE_KEY=<base64url or PEM private key>
   VAPID_SUBJECT=mailto:egi@example.org
   ```

   The public key is served to clients at `GET /push/vapid-public-key` so the PWA
   can subscribe. If `VAPID_PRIVATE_KEY` is unset (or `pywebpush` is absent),
   delivery degrades to a `failed` result and the subscription bookkeeping still
   works.

## Firebase Cloud Messaging (FCM) for Android

There are two delivery paths. The server tries them in order and `_fail`s only if
neither is configured.

### Preferred: FCM HTTP v1 via a service account

Uses the optional `firebase-admin` package and a service-account JSON.

1. **Install the dependency** (uncomment it in `server/requirements.txt`):

   ```bash
   pip install firebase-admin
   ```

2. **Create a service account** in the Firebase console
   (*Project settings → Service accounts → Generate new private key*) and save the
   downloaded JSON on the server.

3. **Point the server at the JSON** with either env var (`server/.env`):

   ```bash
   PUSH_PROVIDER=fcm
   FCM_CREDENTIALS_FILE=/etc/egi/fcm-service-account.json
   # or the Google standard variable:
   GOOGLE_APPLICATION_CREDENTIALS=/etc/egi/fcm-service-account.json
   ```

`firebase-admin` is imported lazily; if it is missing the server degrades to a
`failed` result rather than crashing.

### Legacy: FCM server key

The deprecated legacy HTTP API. No extra dependency (plain `urllib`):

```bash
PUSH_PROVIDER=fcm
FCM_SERVER_KEY=<your legacy server key>
```

Use this only if you cannot adopt the HTTP v1 path. When a service-account
credential is configured it takes precedence over the legacy key.

## Summary

| Channel        | Driver    | Needs                                   | Optional dep    |
| -------------- | --------- | --------------------------------------- | --------------- |
| (default)      | `log`     | nothing                                 | —               |
| PWA Web Push   | `webpush` | VAPID key pair                          | `pywebpush`     |
| Android (v1)   | `fcm`     | service-account JSON                     | `firebase-admin`|
| Android (legacy)| `fcm`    | `FCM_SERVER_KEY`                        | —               |

Everything degrades gracefully: with no credentials the server stays on the `log`
driver, and a missing optional package returns a clear `failed` reason instead of
raising.
