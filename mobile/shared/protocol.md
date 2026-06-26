# EGI Bluetooth Mesh Protocol (Draft)

## Goal

Let two nearby Android phones exchange missing-person records without internet.
When any phone later gets internet, it uploads the merged records to the EGI server.

## Assumptions

- Devices are running the EGI Android app.
- Bluetooth Low Energy (BLE) is available and enabled.
- Devices may be anonymous; trust is based on timestamped records, not identity.

## Record envelope

Every record that crosses the mesh is wrapped in an envelope so the same record
bouncing through multiple phones is never duplicated and its provenance is kept.

```json
{
  "record_type": "person",
  "record_id": "egi:venezuela-2026:la-guaira:uuid",
  "origin_device": "device_fingerprint_or_pubkey",
  "hop_count": 0,
  "created_at": "2026-06-26T03:42:50Z",
  "updated_at": "2026-06-26T03:42:50Z",
  "payload": {
    "id": "uuid",
    "name": "Maria Garcia",
    "status": "missing",
    "age": 34,
    "location": "La Guaira",
    "notes": "Wearing red shirt",
    "contact": "+58...",
    "source": "mesh"
  }
}
```

Envelope rules:

- `record_id` is globally unique (it equals `payload.id`).
- `origin_device` identifies the device that first created the record. It is
  preserved across every hop and never rewritten by relays.
- `hop_count` starts at `0` on the creator and is incremented by one each time a
  device relays the record to a peer. It is advisory (for duty-cycling and debug)
  and never affects conflict resolution.
- `updated_at` drives last-write-wins.
- `created_at` / `updated_at` use ISO-8601 UTC and mirror `payload.createdAt` /
  `payload.updatedAt` so the cloud `/sync` contract is unchanged.

The `payload` is exactly the JSON the server `/sync` endpoint already accepts (a
PFIF-style person, or a report). The envelope is a thin transport wrapper; when a
device reaches the internet it unwraps `payload` and POSTs it to `/sync`, copying
`origin_device` and `hop_count` onto the record.

### Bare record fields (payload)

```json
{
  "id": "uuid",
  "name": "Maria Garcia",
  "status": "missing",
  "age": 34,
  "location": "La Guaira",
  "notes": "Wearing red shirt",
  "contact": "+58...",
  "source": "mesh",
  "origin_device": "device_fingerprint_or_pubkey",
  "hop_count": 0,
  "createdAt": "2026-06-26T03:42:50Z",
  "updatedAt": "2026-06-26T03:42:50Z"
}
```

## Sync handshake

1. **Advertise**: each device broadcasts a small BLE advertisement containing:
   - The EGI service UUID (`0000e91f-0000-1000-8000-00805f9b34fb`).
   - A short bloom filter (service data) summarising locally known record IDs, so
     a passing peer can skip a connection when it already has everything we hold.

2. **Discover**: each device scans for the EGI service UUID.

3. **Compare**: when two devices meet, they open a GATT connection. Each side reads
   the peer's **index characteristic** — a JSON array of `{record_id, updated_at,
   hop_count}` for all local records.

4. **Request**: each device computes the set of records the peer is missing, or
   holds with an older `updated_at`, and writes those record IDs to the peer's
   **request characteristic**.

5. **Transfer**: requested records (full envelopes) are written to the **records
   characteristic** in length-prefixed chunks sized to the negotiated MTU.

6. **Merge**: each device keeps the record with the latest `updated_at`,
   incrementing `hop_count` on records it received from a peer.

7. **Upload**: when internet is available, the device unwraps each envelope and
   POSTs `payload` (plus `origin_device`/`hop_count`) to `/sync`, then pulls newer
   cloud records with `GET /sync?since=`.

### GATT layout

| Characteristic | UUID suffix | Direction | Payload |
| -------------- | ----------- | --------- | ------- |
| Index   | `…e911` | peer reads  | `[{record_id, updated_at, hop_count}, …]` |
| Request | `…e912` | peer writes | `[record_id, …]` |
| Records | `…e913` | peer writes | length-prefixed envelope chunks |

## Conflict resolution

- Last write wins by `updated_at`.
- Deletions are soft (status changes to `deceased` or a `deleted` flag), never hard deletes.

## Privacy

- Personal data travels unencrypted over BLE in this first draft. Future versions should encrypt the GATT connection.
- Users should be warned that nearby strangers can receive public registry data.
