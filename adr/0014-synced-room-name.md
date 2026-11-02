# ADR-0014: Synced room name via a new admin/owner-only content op
Status: accepted

## Context
A room's display name has never been a protocol concept - §4.2's op-body table has no field or op
for it, and the genesis entry (§3.1) carries only `roomNonce`, `relayHost`, and the wrapped epoch-0
key. Every client implementation independently treats the name as purely local bookkeeping, synced
to nobody. The only place a name ever crosses the wire at all is the optional `roomName` field in
an invite envelope (§3.5) - a one-shot, best-effort payload baked in from whatever the inviting
device's own local copy happens to be at that moment.

This already produced a real bug in practice: a device that never actually knew a room's real name
(e.g. one that reached the room via seed-only restore, which has no way to recover it) falls back
to a generic local placeholder - and if *that* device later creates an invite, §3.5's mechanism
faithfully bakes the placeholder into the envelope as though it were the real name, permanently
misleading every future joiner. There is also no way for an already-wrong name to ever be
corrected, and no rename capability exists anywhere, because nothing synced in the first place.

## Decision
Add `room.set` to §4.2's op-body table: `{name}`, rule **admin or owner**.

This deliberately does not follow `profile.set`'s shape, which is the obvious existing template
but the wrong one. `profile.set` is "own only" with no admin override at all - the only content op
with that property - because display name is personal data: an admin overriding someone else's
chosen name would be a moderation capability nobody asked for and the spec never granted anywhere
else. A room's name is the opposite kind of thing: it isn't anyone's personal data, it's a single
shared field describing the room itself, so `room.set` has no author-ownership concept at all -
authorization is a pure role check (`history.roleAt(epoch, author).isAdminOrOwner()`), not an
author-match. `event.create`'s "admin, or member if room setting allows" is the closest existing
precedent for a role-gated op, but it gates *creation* of author-owned items, not a write to a
single shared field with no owner - still not a direct template, hence this ADR rather than simply
adding a table row by analogy.

Conflicts between concurrent writers (two admins renaming around the same time) resolve via the
same `LwwStamp`/`(lamport, deviceKey)` ordering every other LWW field in §4.2 already uses - no new
conflict-resolution primitive.

The existing invite-envelope `roomName` field (§3.5) is unchanged and still needed: it remains the
only way to preview a name before joining, since ops are members-only (§5) and a room's name is
otherwise unreadable pre-join. Once a real `room.set` exists, implementations should source that
envelope field from the materialized name rather than a local-only guess, but that's a client
implementation detail, not a protocol change.

A room created before this op existed has no `room.set` in its history and so has no materialized
name at all until its owner authors one. There is no mechanism to retroactively insert a signed op
into a room's already-existing log, so such a room simply shows no synced name (clients fall back
to whatever local/placeholder behavior they already have) until the owner acts once - this is an
inherent, accepted limitation of adding any new op post-launch, not specific to this one.

## Consequences
+ A room's name becomes exactly as real a piece of shared, synced state as an idea or event -
  authored, signed, materialized, and propagated by the same existing machinery, reaching every
  current and future member, including over relays that never decrypt it (ops are opaque to the
  relay regardless of type, §5).
+ A rename now reaches everyone, and an already-wrong name (the placeholder-propagation bug above)
  self-corrects the moment the room's actual owner sets a real name - no special-case recovery
  logic needed beyond ordinary sync.
+ No new crypto primitive, no envelope/genesis shape change, no relay change at all - `room.set`
  is just one more entry in an existing, open-ended op-type table, and the relay was already
  required to treat every op type opaquely.
− Rooms created before this op existed need one explicit manual action from their owner (a rename,
  or simply "set the name once") to ever get a synced name - there's no automatic migration path,
  and this should be communicated to users rather than assumed to resolve itself.
− A plain member can no longer be given rename rights without also being promoted to admin - a
  deliberate choice (matching every other admin-gated content op), not an oversight, but worth
  stating: there is no room-setting equivalent to `membersCanCreateEvents` for this op in this ADR.
