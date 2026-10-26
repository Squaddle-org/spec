# Roadmap

Shared across all repos. Work strictly in order. Each milestone ends with green tests, a spec release if the protocol changed, and `SPEC_VERSION` bumped in core + relay.

## M0 — Foundations · repos: core, spec
- [x] Gradle wrapper, KMP `core` builds for `jvm` and `android`, publishes `org.squaddle:core` to mavenLocal
- [x] Verify libsodium bindings on JVM + Android; thin `Crypto` facade (`squaddle-org/core `crypto``) -
      JVM verified with real round-trip tests; Android verified by compiling the android target
      against the published `-android` artifact (no device/emulator in this environment, so the
      native binding itself is not yet exercised on-device - tracked as a follow-up, not re-listed
      as a separate checkbox since the roadmap item as written is about the build/target, not CI hardware)
- [x] Canonical CBOR encoder check (kotlinx-serialization CBOR: verify deterministic output; wrap or replace if not) -
      confirmed non-deterministic (indefinite-length collections, unsorted map keys even with
      `useDefiniteLengthEncoding`), replaced with a minimal hand-written encoder/decoder
- [x] Identity: entropy ↔ BIP39, key derivation (§2.1), DeviceCert sign/verify (§2.2)
- [x] Test vector generator → `protocol/testvectors/identity.json`, `devicecert.json`
**Done when:** vectors generated, round-trip + reject tests pass. ✅

## M1 — Membership log · repos: core, spec
- [x] LogEntry model, signing, hashing, chain validation
- [x] State machine: roles, pending, invites (uses/expiry against `rts`), all authorization rules of §3.3
- [x] Epoch key wrap/unwrap, invite envelope (§3.5)
- [x] Property tests: random valid/invalid entry sequences; every rule has a reject test -
      44 tests in core's MembershipStateTest (one accept + >=1 reject per §3.3 row, a full
      12-entry-type lifecycle, one kotest-property test over random member-set sizes injecting a
      deliberately-unauthorized mutation each run)
- [x] Vectors: `logentry.json`, `log-reject.json`, `invite.json` - log-reject.json has one reject
      case per §3.3 row plus a chain-level stale-head case (13 total)

## M2 — Relay MVP · repo: relay
- [x] Go implementation of: CBOR decode, signature verify, log validation (port of M1 rules) —
      passes cbor-reject.json, identity.json, devicecert.json, logentry.json, log-reject.json,
      invite.json (the cross-implementation test: same vectors as core's Kotlin, independently)
- [x] SQLite schema, endpoints from `relay-api.yaml` (devices, rooms, log, ops, envelopes) -
      every endpoint except `google_play`/`/billing/google/rtdn` (explicit M5b stub)
- [x] Request auth (§5) incl. replay cache; rate limiting on envelope GET
- [x] WebSocket fanout; `/metrics` (Prometheus) on separate port; `/healthz`
- [x] Limits (§8): config flag `-limits=none|hosted`, `GET /limits`, `room_full`/`quota_exceeded`,
      voucher entitlements + admin CLI to mint vouchers (incl. permanent `unlimited`),
      `-unlimited-owners` allowlist, hosted `maxPending`/`maxActiveInvites` defaults (§8.1) -
      retention pruning job (§4.4/§8.1, `internal/retention`) running hourly in `cmd/relay`,
      now that §4.4 gives Snapshot's fields real CBOR field numbers (closed via core+relay+spec
      PRs adding the field table, generating `snapshot.json`, and both sides passing it)
- [x] Dockerfile, k8s manifests (untouched, already correct from bootstrap), integration test:
      two simulated clients against the real relay HTTP stack (real httptest.Server + real
      temp-file SQLite, not mocked)

## M3 — Content plane + sync client · repos: core, spec
- [x] OpEnvelope encrypt/sign/verify (§4.1), op bodies (§4.2) + RoomState LWW materializer with
      per-epoch authorization - vectors `op.json` (1 valid + 4 reject: tampered sig, wrong epoch
      key, tampered ad, device not certified for author); kotest permutation property test
      (fold() order-independence) + one authorization-reject case per §4.2 row + an epoch-boundary
      case. `event.create`'s "member if room setting allows" half is now implemented too, via
      §3.3 row 11 field 1 (`membersCanCreateEvents`, default `true`) - closed in v1.0.0-draft.2.
- [x] Request auth (§5) signing - vectors `request-auth.json`, verified on both core and relay
      (`TestRequestAuthVectors`, the real cross-implementation check for this section)
- [x] SQLDelight local store (log_entries, ops, cursors, device_seq, outbox, invite_secrets,
      epoch_keys) - JVM driver + Android driver (compile-checked only, no device/emulator here)
- [x] Sync client (Ktor, OkHttp engine): pull/push, `stale_head`/`stale_epoch` retry (re-encrypts
      the outbox from its retained plaintext body under the new key), `rotation_required`
      auto-rotate for owner/admin (else waits), invite create/join incl. envelope re-upload after
      rotation, WebSocket live updates (§6)
- [x] Snapshot create/apply on the §4.4 outer envelope - inner "materialized state + seq vector"
      format is implementation-internal (§4.4 gives it no field table, unlike every other
      structure - nothing cross-implementation to settle)
- [x] Backup file (§7) - vectors `backup.json` (low, test-only Argon2id params)
- [x] JVM CLI harness (`core/cli`, 8 subcommands) - verified by hand against a real relay process
      (identity/room/invite/join/idea/vote/kick, convergent state); integration test drives 3 real
      identities through the full lifecycle incl. kick against the actual relay binary (not a
      mock), asserting the kicked member loses ops read and the rest converge byte-for-byte

## Spec v1.0.0-draft.2
- §5 request auth: added a random 16-byte `nonce` to the Authorization header and the signing
  input; relay's replay cache is now keyed by `nonce` instead of `sig` (closes the
  deterministic-Ed25519-signature false-positive a same-second repeat request used to hit).
- §3.3 `roomSettings`: added field 1, `membersCanCreateEvents` (bool, default `true`) - the
  missing field `event.create`'s "member if room setting allows" half (§4.2) needed.

## Spec v1.0.0-draft.3
- §5: added `GET /users/{user}/rooms` (self-only) - lists every room on the relay where `{user}`
  holds an active role, with each room's recorded `relayHost` (§3.3 row 0 field 1, now persisted
  by the relay instead of only living inside the opaque genesis blob). Closes a seed-only-restore
  gap: recovering an identity from the seed alone previously recovered no room membership at all,
  since nothing let a client ask "which rooms am I in" without an existing local log copy.

## M4 — Android app · repos: android, website
- [ ] Onboarding: create identity, show seed, set display name
- [ ] Rooms list, room view (ideas sorted by score, vote, comment), create idea
- [ ] Members screen: roles, kick, promote, transfer owner, pending approvals
- [ ] Invite screen: expiry, max uses, approval toggle, share sheet → WhatsApp
- [ ] App Links (`assetlinks.json`, `autoVerify`), join flow from link, clipboard fallback, Install Referrer
- [ ] Idea → event, export to device calendar (CalendarContract) and `.ics` share
- [ ] UnifiedPush + WorkManager background sync
- [ ] Product flavors `foss` / `play`; limits UI ("room full", boost CTA), voucher redemption in both flavors
- [ ] Backup: seed display, encrypted file via SAF, periodic auto-backup, restore flow

## M5 — Web client / PWA + device linking · repos: webclient (new), core, website
- [x] Decide: Compose/Wasm vs TS client against spec (ADR-0009) - `core`'s `js(IR)` target,
      hosted at `app.squaddle.org`. The pinned libsodium bindings' `js` artifact's crypto bridge
      is fixed and verified cryptographically correct end to end (identity create/restore, via
      the new `IdentityApi` facade + `webclient`'s `IdentityStore`). A real-browser DOM/CSP check
      (`wasm-unsafe-eval`) is still open - see ADR-0009.
- [ ] Device linking via QR (§2.3), device list + revoke
- [ ] PWA install + Web Push (UnifiedPush-compatible endpoint or Web Push via relay)
- [ ] Strict CSP, no third-party JS, SRI
- [ ] Fork detection: clients embed observed log head in ops, warn on divergence

## M5b — Monetization · repos: android, relay
- [ ] Play Billing subscription "Room Boost" (+ optional one-time "Supporter" unlock for cosmetics)
- [ ] Relay: Play Developer API verification, acknowledge, RTDN endpoint for renew/cancel/refund
- [ ] Boost management screen: who boosted, until when, move boost to another room (once per period)
- [ ] Donation links (Liberapay/GitHub Sponsors) in About screen — no store fees on these

## M6 — Hardening & later
- [ ] Identity rotation (new seed, re-join rooms via signed handover)
- [ ] Desktop (Compose Desktop, Windows MSI)
- [ ] Federation (ADR-0008): relay-to-relay replication of a room
- [ ] Optional MLS upgrade path (ADR-0005)
- [ ] iOS (KMP + SwiftUI) once a dev account exists (StoreKit as additional entitlement provider)
- [ ] Blind-signed, unlinkable boost tokens
- [ ] Club/organization offering: managed relay on custom domain
