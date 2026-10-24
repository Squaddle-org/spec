# ADR-0001: Content-blind relay instead of pure P2P or WebDAV
Status: accepted

## Context
Friend groups are asynchronous; phones are rarely online in the foreground at the same time.
iOS/Android kill background sockets. WebDAV/Nextcloud has no merge semantics (ETag locking loses concurrent votes).

## Decision
A small relay stores signed, encrypted ops and the membership log. Truth lives on devices; the relay is transport + availability + ordering.

## Consequences
+ Works when the creator is offline, enables push wake-ups, trivial self-hosting.
− One semi-trusted component (availability, metadata, invite expiry). Mitigated by E2E + signatures (THREAT_MODEL.md).
