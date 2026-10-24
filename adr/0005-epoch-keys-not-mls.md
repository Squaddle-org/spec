# ADR-0005: Epoch keys with pairwise sealed-box wrapping; MLS later
Status: accepted

## Context
Groups are small (<50). Kick must cut off future content.

## Decision
Random 32-byte epoch key per room epoch, wrapped per member with crypto_box_seal. `remove` ⇒ `epochRotate`.

## Consequences
+ Simple, auditable, built only from libsodium primitives.
− No forward secrecy / post-compromise security within an epoch. O(n) wrapping per rotation (fine for n<50). MLS (OpenMLS via Rust/uniffi) is the upgrade path.
