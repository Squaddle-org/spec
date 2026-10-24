# ADR-0006: Discord-style invites via relay-held encrypted envelopes
Status: accepted

## Decision
Invite = log entry (expiry, max uses, approval flag) + secret in the URL fragment + relay-stored envelope with the epoch key encrypted under a key derived from the secret. Joiner self-authors a `join` entry authorized by the invite.

## Consequences
+ Joining works with no admin online; revocation/expiry enforced by deleting the envelope and by log validation.
− Expiry relies on the relay timestamp. Admins must re-wrap envelopes after each rotation.
