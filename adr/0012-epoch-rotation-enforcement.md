# ADR-0012: Enforce epoch rotation after remove via relay-rejected rotationPending
Status: accepted

## Context
PROTOCOL.md §3.4 already says "a `remove` ... MUST be followed by an `epochRotate` from the same
actor. Clients MUST rotate automatically when they author a `remove`." This was never enforced by
anything: not the membership state machine, not the relay, not a test. A buggy, compromised, or
simply offline client could append `remove` and never rotate, leaving the removed member able to
decrypt all new content indefinitely under the epoch key they already have. THREAT_MODEL.md's
kicked-member row already *claims* "Cannot: ... write after `remove` (relay blocks, clients
reject)", and ADR-0005 already decided `remove ⇒ epochRotate` - the mechanism to make either of
those true was never specified.

## Decision
`MembershipState` gains a `rotationPending` boolean:
- Set to `true` whenever a `remove` entry is accepted.
- Cleared to `false` whenever the next `epochRotate` entry is accepted - by **any** current
  owner/admin, not necessarily the actor who authored the `remove`. This relaxes the literal
  "from the same actor" wording: the goal (no new content under a key the removed member still
  holds) is achieved regardless of who performs the rotation, and requiring the *same* actor would
  leave a room stuck if that admin goes offline before rotating.
- Unaffected by every other entry type. In particular, membership-log appends other than
  `epochRotate` (invites, approvals, further removes, `roomSettings`, ...) are still accepted
  while `rotationPending` is `true` - only the content plane is gated.

While `rotationPending` is `true`, the relay MUST reject `POST /rooms/{room}/ops` with a new error
code `rotation_required` (409), added to `relay-api.yaml`'s `Error.code` enum. Clients MUST retry
after the next successful `epochRotate`, the same way they already retry on `stale_epoch`.

`leave`'s existing guidance ("SHOULD" rotate afterwards) is intentionally left as-is: unenforced,
advisory. This ADR scopes the hard gate to `remove`'s literal MUST only.

## Consequences
+ Closes a real confidentiality gap mechanically instead of relying on client goodwill, and makes
  THREAT_MODEL.md's already-stated guarantee actually true.
+ No new crypto primitive, no protocol structure change - `rotationPending` is derived state, not
  a new signed field.
− A room is briefly unable to post new content if nobody rotates immediately after a `remove`.
  Acceptable: `remove` is already a deliberate admin/owner action, and a well-behaved client
  rotates automatically as part of that same flow (sub-second window in practice).
− Membership and relay implementations (core, relay, and any future client) must now track one
  more piece of derived state and keep it in sync; covered by `logentry.json`'s existing
  genesis→...→remove→epochRotate chain (extended with a `rotationPending` field per step) so
  Kotlin and Go are checked against the same vectors.
