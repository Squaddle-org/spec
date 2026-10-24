# Squaddle Protocol v1 (draft)

Normative. "MUST/SHOULD/MAY" per RFC 2119. Every structure here gets test vectors in `testvectors/`.

## 1. Primitives

| Purpose | Construction (libsodium) |
|---|---|
| Hash | BLAKE2b-256 (`crypto_generichash`, 32 bytes, no key) |
| Signature | Ed25519 (`crypto_sign_detached`) |
| Symmetric AEAD | XChaCha20-Poly1305-IETF (`crypto_aead_xchacha20poly1305_ietf_*`), random 24-byte nonce |
| Public-key wrap | X25519 sealed box (`crypto_box_seal`) |
| Subkey derivation | `crypto_kdf_derive_from_key` (BLAKE2b), 8-char context strings below |
| Password KDF | Argon2id (`crypto_pwhash`, `OPSLIMIT_MODERATE`, `MEMLIMIT_MODERATE` minimum) |
| Random | `randombytes_buf` |

**Encoding:** canonical CBOR (RFC 8949 §4.2.1 deterministic encoding). Maps use small
unsigned integer keys (listed per struct) to keep payloads tiny. Byte strings are raw bytes.
In JSON (HTTP bodies, test vectors) binary fields are base64url without padding.

A decoder MUST reject any input that is not *the* unique canonical encoding of its value:
non-shortest-form integers or lengths, indefinite-length byte strings/text strings/arrays/maps,
map keys not in strictly ascending order of their encoded bytes (including duplicate keys), and
any trailing bytes after the top-level value. This applies to every CBOR decode in this protocol,
not only to structures that get hashed or signed - accepting a second valid encoding of the same
logical value is exactly what canonical CBOR exists to rule out. See `testvectors/cbor-reject.json`.

**Signing rule:** `sig = Ed25519(sk, "SQDL1" ‖ domain ‖ 0x00 ‖ BLAKE2b(CBOR(struct without sig field)))`
where `domain` is the ASCII tag given per struct. Domain separation is mandatory.

## 2. Identity

### 2.1 Seed → user keys
- `entropy`: 32 random bytes, exported as BIP39 24-word mnemonic (English wordlist).
- `master = BLAKE2b-256(entropy)` (32 bytes, used as crypto_kdf master key)
- `userSignSeed = kdf(master, id=1, ctx="SQDLUSIG")` → `crypto_sign_seed_keypair` → `userKey` (Ed25519 pk, 32B)
- `userBoxSeed  = kdf(master, id=2, ctx="SQDLUBOX")` → `crypto_box_seed_keypair` → `userBoxKey` (X25519 pk, 32B)
- `backupKey    = kdf(master, id=3, ctx="SQDLBKUP")` (reserved: seed-only encrypted backups)

`UserId` = `userKey` (32 bytes). Display as base32 (RFC 4648, lowercase, no padding).

### 2.2 Device keys and certs
Each device generates a random Ed25519 `deviceKey`. Domain `"devcert"`.

```
DeviceCert {
  0: v          uint = 1
  1: user       bytes(32)   userKey
  2: userBox    bytes(32)   userBoxKey
  3: device     bytes(32)   deviceKey
  4: label      tstr        e.g. "Pixel 8", max 64 chars
  5: issuedAt   uint        unix seconds
  6: sig        bytes(64)   by user signing key
}
DeviceRevoke { 0:v, 1:user, 2:device, 3:revokedAt, 4:sig }  domain "devrevoke"
```

### 2.3 Device linking
1. New device N generates its `deviceKey`, an ephemeral X25519 keypair `ek` and a random 16-byte `code`.
   It shows a QR: `squaddle-link:v1:<relayHost>:<b64 code>:<b64 ek.pk>`.
2. Existing device E scans and posts `crypto_box_seal(ek.pk, CBOR{0:entropy, 1:rooms[]})` to `POST /v1/link/{code}`.
3. N polls `GET /v1/link/{code}`, opens the box, derives the user keys, issues its own `DeviceCert`
   (it now holds the user signing key) and publishes it.
4. Both devices show a 6-digit confirmation code = first 20 bits of `BLAKE2b(ek.pk ‖ userKey)`; user compares.
5. Mailbox entries expire after 5 minutes and are deleted on first read.

## 3. Rooms and the membership log (control plane)

### 3.1 Room id
`roomNonce` = 16 random bytes. `roomId = BLAKE2b-256("SQDL1room" ‖ creatorUserKey ‖ roomNonce)`.
External ref: `RoomRef = base32(roomId) "@" relayHost`.

### 3.2 Log entry
Append-only, hash-chained, linearized by the relay. Domain `"logentry"`.

```
LogEntry {
  0: v         uint = 1
  1: room      bytes(32)
  2: index     uint          0 for genesis, then +1
  3: prev      bytes(32)?    hash of previous entry (absent only for genesis)
  4: author    bytes(32)     userKey of the actor
  5: cert      DeviceCert    cert of the signing device
  6: type      uint          see table
  7: body      map           type-specific
  8: ts        uint          author's clock, informational
  9: sig       bytes(64)     by device key
}
entryHash = BLAKE2b(CBOR(full entry incl. sig))
```
The relay stores an additional **relay timestamp** `rts` per entry (not signed by the author;
used for invite expiry, see §3.5 — trust assumption documented in THREAT_MODEL.md).

### 3.3 Entry types

| type | name | body | authorized if |
|---|---|---|---|
| 0 | genesis | `{0:roomNonce, 1:relayHost, 2:epoch0Wrapped}` | index=0, `roomId` matches author+nonce. Author becomes **owner**. |
| 1 | inviteCreate | `{0:inviteId(16B), 1:expiresAt?, 2:maxUses?, 3:requiresApproval(bool), 4:role="member"}` | author is owner/admin |
| 2 | inviteRevoke | `{0:inviteId}` | owner/admin |
| 3 | join | `{0:inviteId}` | author not a member, invite exists, not revoked, `rts < expiresAt`, uses < maxUses. → member, or **pending** if requiresApproval |
| 4 | approve | `{0:user, 1:wrappedEpochKey}` | owner/admin, target pending |
| 5 | reject | `{0:user}` | owner/admin, target pending |
| 6 | remove | `{0:user}` | owner removes anyone but self; admin removes members only |
| 7 | leave | `{}` | author is member/admin (owner must transfer first) |
| 8 | setRole | `{0:user, 1:role}` role ∈ {admin, member} | owner only |
| 9 | transferOwner | `{0:user}` | owner only, target is admin. Old owner becomes admin. |
| 10 | epochRotate | `{0:epoch, 1:[{0:user, 1:sealedKey}]}` | owner/admin; MUST contain exactly the current non-pending members |
| 11 | roomSettings | `{0:joinApprovalDefault?, …}` | owner/admin |

Roles: `owner` (exactly one) > `admin` > `member`; `pending` has no read access.

**Validation:** every client and the relay replay the log from genesis and reject an entry if
signature, cert chain, `prev`, `index` or authorization fails. The relay accepts an append only
if `prev == currentHead` (else `409`, client refetches and retries).

### 3.4 Epoch keys
- `epochKey` = 32 random bytes, `epoch` starts at 0 (in genesis).
- Wrapped per user: `crypto_box_seal(userBoxKey, CBOR{0:room, 1:epoch, 2:epochKey})`.
- A `remove` (and SHOULD after `leave`) MUST be followed by an `epochRotate` from the same actor.
  Clients MUST rotate automatically when they author a `remove`.
- After `epochRotate`, the relay rejects content ops with `epoch < current` (`409 stale_epoch`);
  clients re-encrypt pending ops with the new key and retry.

### 3.5 Invites
URL: `https://<linkHost>/j/<relayHost>/<b32 roomId>/<b32 inviteId>#<b64 inviteSecret>`
- `inviteSecret` = 32 random bytes. Never leaves the client except in the link.
- `inviteKey = kdf(BLAKE2b(inviteSecret), id=1, ctx="SQDLINVK")`
- **Envelope** (mutable, stored by relay, readable without auth):
  `nonce ‖ AEAD(inviteKey, nonce, CBOR{0:room, 1:epoch, 2:epochKey, 3:roomName?}, ad=roomId‖inviteId)`
- Only for invites without approval. For approval invites, no envelope exists; the key arrives in `approve`.
- Admins MUST re-upload envelopes of all active invites after every `epochRotate`.
- Relay deletes the envelope on revoke, expiry, or when uses are exhausted.

Join flow: fetch envelope → decrypt → append `join` entry (signed by joiner's device) →
relay validates against log + `rts` → done. No admin needs to be online.

## 4. Content plane (op-log)

### 4.1 Envelope
Domain `"op"`.
```
OpEnvelope {
  0: v        uint = 1
  1: room     bytes(32)
  2: epoch    uint
  3: author   bytes(32)   userKey
  4: device   bytes(32)   deviceKey (cert resolvable via relay /users/{u}/devices)
  5: seq      uint        per-device monotonic, starts at 1 (gap detection)
  6: lamport  uint        max(seen)+1
  7: nonce    bytes(24)
  8: ct       bytes       AEAD(epochKey, nonce, CBOR(OpBody), ad = CBOR(fields 0..7 without ct))
  9: sig      bytes(64)   by device key
}
opId = BLAKE2b(CBOR(full envelope))
```

### 4.2 Bodies
```
OpBody { 0: type tstr, 1: payload map }
```
| type | payload | rule |
|---|---|---|
| `idea.create` | `{id(16B), title, desc?, tags?[]}` | member |
| `idea.set` | `{id, field ∈ {title,desc,tags,status}, value}` | idea author or admin; LWW per (id, field) |
| `idea.delete` | `{id}` | idea author or admin; tombstone wins |
| `vote.set` | `{ideaId, value ∈ {-1,0,1}}` | author's own vote only; LWW per (ideaId, author) |
| `comment.add` | `{id, ideaId, text}` | member |
| `comment.delete` | `{id}` | comment author or admin |
| `event.create` | `{id, ideaId?, title, start, end?, tz, location?, allDay}` | admin, or member if room setting allows |
| `event.set` / `event.cancel` | `{id, field, value}` / `{id}` | event author or admin |
| `rsvp.set` | `{eventId, value ∈ {yes,no,maybe}}` | own only |
| `profile.set` | `{displayName, emoji?}` | own only (per-room display name) |

LWW order: `(lamport, deviceKey bytes)` lexicographic. Unknown types MUST be ignored (forward compat).

### 4.3 Export
`event.*` maps to iCalendar `VEVENT` (RFC 5545) at export time only (`UID = b32(eventId)@squaddle`).

### 4.4 Snapshots
`Snapshot { room, epoch, coversUpTo(cursor), nonce, ct = AEAD(epochKey, CBOR(materialized state + seq vector)) , author, device, sig }` domain `"snapshot"`.
Relay MAY prune ops with cursor ≤ `coversUpTo` 30 days after a snapshot exists.

## 5. Relay API
See `relay-api.yaml`. Limits/boosts: §8. Summary:

- **Auth header** for writes and member reads:
  `Authorization: SQDL1 device=<b64>, ts=<unix>, sig=<b64>`
  over `"SQDL1" ‖ "req" ‖ 0x00 ‖ BLAKE2b(method ‖ "\n" ‖ path+query ‖ "\n" ‖ ts ‖ "\n" ‖ BLAKE2b(body))`.
  Relay rejects `|now − ts| > 60s` and replays within the window (nonce cache keyed by sig).
- Read access to ops/snapshots: device's user is member/admin/owner (not pending, not removed).
- Unauthenticated: `GET /v1/invites/{room}/{inviteId}/envelope` (rate-limited per IP), `/healthz`, `/metrics` (internal port).

## 6. Push
- Client registers a UnifiedPush endpoint per device: `POST /v1/push` `{endpoint}`.
- On new ops/log entries the relay POSTs `{"r":"<b32 roomId>","c":<cursor>}` — no content, no author.
- Relay debounces per (device, room), 30s.

## 7. Backup file (`.squaddle-backup`)
```
Backup { 0:v=1, 1:kdf {0:"argon2id13", 1:opslimit, 2:memlimit, 3:salt(16B)}, 2:nonce, 3:ct }
ct = AEAD(pwhash(passphrase), nonce, CBOR{0:entropy, 1:rooms[{0:roomRef, 1:name?}], 2:createdAt}, ad="squaddle-backup-v1")
```

## 8. Room limits and boosts (relay-local, not part of the signed log)

Limits are **relay policy**, not protocol state: they are never written into the membership log,
so a room keeps working unchanged when it moves to another relay (federation, self-hosting).

### 8.1 Limits
```
RoomLimits {                       // JSON, GET /v1/rooms/{room}/limits (members only)
  tier:            "free" | "boosted" | "unlimited" | "custom"
  maxMembers:      int | null      // non-pending members incl. owner; null = unlimited
  maxPending:      int | null
  opRetentionDays: int | null      // ops older than this AND covered by a snapshot may be pruned
  attachmentBytes: int | null      // reserved for blobs (post-v1), 0 = disabled
  maxActiveInvites:int | null
  boostedUntil:    unix | null
}
```
Defaults on the official hosted relay (tunable relay config):
free = 20 members, 90 days op retention, attachments disabled; boosted = 100 members, unlimited retention, 1 GiB attachments.
unlimited = all limits `null`, no expiry (operator tier, never sold).
**Self-hosted relays default to unlimited** (`-limits=none`).

### 8.1a Operator tier "unlimited"
Granted only by the relay operator, two ways:
1. **Owner allowlist** (relay config `-unlimited-owners=<b32 userKey>,...`): every room whose *current* owner
   (per membership log) is on the list is `unlimited`. Evaluated on every limits check, so it follows
   `transferOwner` — transferring a room to someone not on the list drops it to its normal tier.
2. **Permanent voucher**: voucher with tier `unlimited` and no duration, minted via the relay admin CLI,
   bound to one room like any entitlement.

Precedence: `unlimited` > `boosted` > `free`. Clients just display the tier from `GET /limits`.

Retention never deletes room state: pruning only removes ops already covered by a snapshot (§4.4),
so ideas/votes/events stay; only fine-grained history disappears.

### 8.2 Enforcement
- `join` or `approve` that would exceed `maxMembers` → `409 room_full`. Clients show "room full, ask an admin to boost".
- Exceeding `maxActiveInvites` on `inviteCreate` → `409 quota_exceeded`.
- Downgrade (boost expires) never removes members; it only blocks new joins until under the limit.
- Limits are never applied retroactively to content.

### 8.3 Boosts (entitlements)
Any member can boost a room (Discord-style), paid via the store of the client platform.
```
POST /v1/entitlements   (signed request, member of room)
{ "room": "<b32>", "provider": "google_play" | "voucher", "token": "<purchase token or voucher code>" }
→ 201 { "room": "...", "tier": "boosted", "until": <unix> }
```
- `google_play`: relay verifies the purchase token server-side (Play Developer API), acknowledges it,
  and binds it to exactly one `roomId`. Subscriptions renew via Real-Time Developer Notifications.
- `voucher`: opaque codes generated by the relay operator (club deals, donations, testing).
- The relay stores `(roomId, provider, purchaseRef, until)` only — no Google account data beyond what the token reveals.
- Privacy note (THREAT_MODEL.md): the relay learns that some store purchase is linked to a room.
  Post-v1 option: unlinkable blind-signed boost tokens (Privacy Pass style).

## 9. Versioning
Every struct has `v`. A client MUST reject structures with unknown major `v` and MUST ignore
unknown map keys. Breaking changes bump `v` and the "SQDL1" signing prefix.
