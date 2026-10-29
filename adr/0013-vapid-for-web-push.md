# ADR-0013: VAPID (ECDSA P-256) for Web Push transport authentication
Status: accepted

## Context
PROTOCOL.md §6 specifies that the relay sends a content-free wake-up (`{"r":..., "c":...}`) to
each registered UnifiedPush endpoint on new ops/log entries, but says nothing about *how* the
relay authenticates itself to the push service receiving that request. The current `relay`
implementation (`internal/api/push.go`) just does a bare, unauthenticated HTTP `POST` with a raw
JSON body - not a real Web Push send. Real push services (and UnifiedPush distributors like
ntfy, which themselves speak standard Web Push under the hood) generally expect or require VAPID
(RFC 8292): an `Authorization` header carrying a JWT signed by the sender's own keypair, so the
push service can rate-limit/attribute requests to a sender without that sender needing a
pre-arranged account per service.

`PROTOCOL.md` §1 restricts this project to "only libsodium constructions" and `spec/CLAUDE.md`'s
own rule is "New primitive = new ADR first." VAPID's signing algorithm is mandated by RFC 8292
§3 to be ES256 (ECDSA over NIST P-256 with SHA-256) - not a choice Squaddle is free to make, and
not something libsodium's Ed25519 can substitute for: push services implementing RFC 8292
validate the JWT's signature using the P-256 public key presented alongside it, per the spec.
This ADR exists to make that carve-out explicit and bounded, rather than silently introducing a
second signature algorithm into the codebase without comment.

## Decision
The relay holds exactly one VAPID keypair (ECDSA P-256), generated via a new `vapid generate`
admin CLI subcommand (mirrors the existing `voucher` admin command) and supplied to the running
relay via `-vapid-private-key-file` (PEM). On every push send, the relay signs a minimal ES256
JWT (`{"typ":"JWT","alg":"ES256"}` header, `aud`/`exp`/`sub` claims per RFC 8292 §2, raw `r‖s`
signature encoding per RFC 7518 §3.4 - *not* the ASN.1 DER form Go's `crypto/ecdsa.Sign` normally
produces) and sends `Authorization: vapid t=<jwt>, k=<base64url pubkey>` with the push request.

The push payload itself stays content-free (§6, unchanged) - RFC 8291 (Web Push payload
encryption) therefore never applies here: encryption is only relevant when a push carries a
body, and this one deliberately never does. No payload encryption code exists or is needed.

A new unauthenticated endpoint, `GET /v1/push/vapid` → `{"publicKey": "<base64url, uncompressed
P-256 point>"}`, exposes the public key - useful for a future client (e.g. `webclient`'s own
eventual Web Push support, M5) that needs `applicationServerKey` at subscription time; Android's
UnifiedPush flow does not need this at registration (the distributor hands out the endpoint
directly), only the relay-side send needs the keypair at all.

**Scope boundary**: this keypair and its JWTs never touch the membership log, the content plane,
device certs, or any client-held key material. They exist solely at the relay↔push-service
transport edge, entirely orthogonal to every libsodium construction PROTOCOL.md §1 already lists.
No existing signed/encrypted structure changes shape; no test vectors are needed for this reason -
cross-implementation test vectors exist to keep core/relay's *shared* CBOR structures in sync,
and VAPID JWTs are standard JOSE consumed by third-party push services, not a Squaddle-defined
wire format with a second implementation to keep in sync against.

Stdlib only (`crypto/ecdsa`, `crypto/elliptic`, `crypto/rand`, `encoding/pem`) - no new Go
dependency, consistent with `relay/CLAUDE.md`'s stdlib-first posture.

## Consequences
+ Real Web Push delivery that push services/distributors will actually accept, instead of a bare
  POST that happens to work only against a permissive test receiver.
+ Zero new third-party dependencies in `relay`.
+ The carve-out is explicit, bounded, and documented - a future reader hitting "ES256" in the
  codebase has one place that explains why it isn't libsodium/Ed25519 and confirms the scope is
  contained to this one subsystem.
- A second, unrelated signature algorithm now exists in the relay codebase, purely for this one
  purpose - a minor maintenance surface (one keypair format, one JWT signer) that didn't exist
  before.
- The relay operator must now provision and rotate one additional secret (the VAPID private key)
  outside the membership/content-plane key material it already manages.
