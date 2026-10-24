# Architecture

## Goals
- No accounts, no passwords, no phone numbers. Identity = keypair derived from a seed.
- Rooms shared via HTTPS invite links (Discord-style: expiry, max uses, optional approval).
- Roles like WhatsApp/Telegram: owner, admins, members. Admins can kick; kicked users lose access to new content.
- Multi-device per user (phone + browser + later Windows).
- Works when the room creator is offline. Async by default.
- Self-hostable relay (single binary + SQLite). Federation later without protocol break.
- Relay is untrusted for content (E2E), semi-trusted for availability, ordering and invite expiry.

## Components

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Android app  │  │  Web / PWA   │  │ Desktop app  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       └────────── core (KMP) ─────────────┘
         identity · crypto · membership log · op-log · LWW state · sync client · backup
                         │  HTTPS + WebSocket (signed requests)
                 ┌───────▼────────┐        ┌──────────────┐
                 │  relay (Go)    │──push─▶│ ntfy / UP    │──▶ devices
                 │  SQLite        │        │ distributor  │
                 └────────────────┘        └──────────────┘
```

## Two planes per room

| Plane | Content | Encrypted? | Who validates |
|---|---|---|---|
| **Control plane** — membership log | genesis, join, approve, remove, leave, setRole, invite create/revoke, epoch rotate | No (signed only). Wrapped keys inside are sealed boxes. | Relay **and** every client |
| **Content plane** — op-log | ideas, votes, comments, events, RSVPs, room profile | Yes, AEAD with the current epoch key | Clients only |

The relay must read the control plane to enforce access (who may read/write, who is kicked,
whether an invite is still valid). It never needs the content plane.

## Identity

```
Seed (BIP39, 24 words, 256-bit entropy)
 └─ crypto_kdf → user signing key (Ed25519) + user box key (X25519)
     └─ per device: random Ed25519 device key + DeviceCert signed by user key
```
- Room membership and roles attach to the **user** key.
- Content ops are signed by the **device** key; the DeviceCert chains it to the user.
- Epoch keys are sealed to the **user** X25519 key → a newly linked device can read every room immediately.
- Device linking: new device shows QR (ephemeral X25519 pubkey + relay), existing device sends the user secret sealed to it.
- Trade-off (ADR-0004): devices share the user secret. Revoking a device blocks it at the relay; full protection against a stolen device needs identity rotation (roadmap M6).

## State model (content plane)
- Op-log, append-only, each op signed and encrypted. Materialized state = fold over ops.
- Ideas: LWW register per field, ordering `(lamport, deviceKey)`.
- Votes: key `(ideaId, userKey)`, only the user may write their own vote → conflict-free by construction.
- Authorization (author-or-admin for edit/delete) checked by clients against the membership state at the op's epoch.

## Sync
- Client keeps a local op store (SQLDelight). Pull `GET /ops?after=cursor`, push batches.
- WebSocket for live updates while foregrounded; UnifiedPush wake-up ("room X has news", no content) when backgrounded → WorkManager pulls.
- Snapshots: a member periodically uploads an encrypted materialized-state snapshot; relay may prune ops covered by it after a grace period.

## Links
- Link domain `squaddle.org` serves: `/.well-known/assetlinks.json`, later `apple-app-site-association`, the web client, and a fallback page.
- Invite URL: `https://squaddle.org/j/<relayHost>/<roomId>/<inviteId>#<inviteSecret>`
- Fragment carries the secret → never sent to the link server, relay, or WhatsApp's preview crawler.
- Deferred deep link: fallback page offers "copy & install"; app checks clipboard on first start; Android Install Referrer as bonus.

## Backup
- Seed phrase (always works, relay holds the data).
- Encrypted backup file (Argon2id passphrase) containing seed + room list, written via Storage Access Framework → user picks Google Drive / Nextcloud / local. Optional periodic auto-backup via WorkManager.

## Limits & monetization (ADR-0010)
Relay-local room limits (members, retention, invites, attachments) with a free tier on the hosted relay
and paid "Room Boosts" redeemed via store purchase tokens or vouchers. Self-hosted relays are unlimited.
Details: PROTOCOL.md §8, squaddle-org/infra BUSINESS.md (private).

## Federation (later, ADR-0008)
Room refs are `roomId@relayHost`; users are bare public keys; ops and log entries are self-contained and content-addressed. Federation = relays replicating a room's log and ops. Nothing in v1 may assume a single relay per user.
