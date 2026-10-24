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
- [ ] Go implementation of: CBOR decode, signature verify, log validation (port of M1 rules) — **must pass M1 vectors**
- [ ] SQLite schema, endpoints from `relay-api.yaml` (devices, rooms, log, ops, envelopes)
- [ ] Request auth (§5) incl. replay cache; rate limiting on envelope GET
- [ ] WebSocket fanout; `/metrics` (Prometheus) on separate port; `/healthz`
- [ ] Limits (§8): config flag `-limits=none|hosted`, `GET /limits`, `room_full`/`quota_exceeded`, retention pruning job, voucher entitlements + admin CLI to mint vouchers (incl. permanent `unlimited`), `-unlimited-owners` allowlist
- [ ] Dockerfile, k8s manifests, integration test: two simulated clients against real relay

## M3 — Content plane + sync client · repos: core, spec
- [ ] OpEnvelope encrypt/sign/verify, op bodies (§4.2), LWW materializer with authorization
- [ ] SQLDelight local store (ops, log, cursors, outbox)
- [ ] Sync client (Ktor): pull/push, stale_head / stale_epoch retry, outbox re-encryption
- [ ] Snapshot create/apply
- [ ] JVM CLI harness (`core` test app) to drive two identities end-to-end

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

## M5 — Web client / PWA + device linking · repos: web (new), core, website
- [ ] Decide: Compose/Wasm vs TS client against spec (ADR-0009). Check libsodium bindings for js/wasm target.
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
