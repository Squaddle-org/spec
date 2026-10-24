# ADR-0008: Federation-ready identifiers from day one
Status: accepted (federation itself deferred)

## Decision
Rooms are addressed as `roomId@relayHost`; users are bare public keys with no home server. Log entries, ops and snapshots are self-contained, signed and content-addressed. Invite links carry the relay host.

## Consequences
+ Federation later = relays replicating a room's log/ops + a head-agreement rule; no client protocol break.
− Slightly longer links.
