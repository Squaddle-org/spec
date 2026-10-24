# ADR-0003: Separate membership log (signed, plaintext) from content ops (encrypted)
Status: accepted

## Decision
Membership/roles/invites live in a hash-chained, relay-linearized log that both relay and clients validate. Content is encrypted and only clients validate it.

## Consequences
+ Relay can enforce kicks and invite expiry without reading content. Roles can't be forged via CRDT merges.
− Relay sees the membership graph (accepted non-goal for v1).
