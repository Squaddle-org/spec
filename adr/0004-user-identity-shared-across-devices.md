# ADR-0004: One user identity (seed) shared by all devices, per-device signing keys
Status: accepted

## Context
Multi-device (phone, browser, Windows) and restore-from-backup are requirements.

## Decision
Seed → user Ed25519 + X25519. Epoch keys sealed to the user box key. Each device has its own Ed25519 key, certified by the user key. Devices are linked via QR and receive the seed.

## Consequences
+ New/restored device reads all rooms instantly, no admin interaction. Backup = seed.
− Stolen device ⇒ seed compromised. Device revoke blocks it at the relay; full recovery needs identity rotation (M6). Per-device box keys would be stronger but multiply fan-out on every rotation/link.
