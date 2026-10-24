# ADR-0002: Signed op-log with LWW instead of Yjs/Automerge
Status: accepted

## Context
Roles and per-author permissions (only I may change my vote; only author/admin may edit an idea) must be verifiable per operation. Generic CRDT update blobs (Yjs/Automerge) don't expose per-op authorship in a verifiable way and need WASM/JS bindings on native.

## Decision
Event-sourced op-log; each op signed by a device key and encrypted. State = LWW registers per field + per-user vote entries + tombstones.

## Consequences
+ Small, pure Kotlin, portable to Go/TS, every op authorizable.
− No collaborative rich-text editing. Not needed for this domain; revisit if ever.
