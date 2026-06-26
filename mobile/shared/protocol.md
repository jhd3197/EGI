# EGI Bluetooth Mesh Protocol (Draft)

## Goal

Let two nearby Android phones exchange missing-person records without internet.
When any phone later gets internet, it uploads the merged records to the EGI server.

## Assumptions

- Devices are running the EGI Android app.
- Bluetooth Low Energy (BLE) is available and enabled.
- Devices may be anonymous; trust is based on timestamped records, not identity.

## Data packet

Each record is a JSON object with these fields:

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
  "createdAt": "2026-06-26T03:42:50Z",
  "updatedAt": "2026-06-26T03:42:50Z"
}
```

## Sync handshake

1. **Advertise**: each device broadcasts a small BLE advertisement containing:
   - A service UUID unique to EGI.
   - A compressed bitmap/hash of locally known record IDs.

2. **Discover**: each device scans for other EGI advertisements.

3. **Compare**: when two devices meet, they connect and exchange a list of:
   - `(record_id, updated_at)` for all local records.

4. **Request**: each device asks for records it is missing or that have a newer `updated_at`.

5. **Transfer**: records are sent over a BLE GATT characteristic in chunks if needed.

6. **Merge**: each device keeps the record with the latest `updated_at`.

7. **Upload**: when internet is available, the device POSTs all new/updated records to `/sync`.

## Conflict resolution

- Last write wins by `updated_at`.
- Deletions are soft (status changes to `deceased` or a `deleted` flag), never hard deletes.

## Privacy

- Personal data travels unencrypted over BLE in this first draft. Future versions should encrypt the GATT connection.
- Users should be warned that nearby strangers can receive public registry data.
