# Threat model

## Assets
Room content (ideas, votes, comments, events), user identity seed, epoch keys, invite secrets.

## Adversaries and what we guarantee

| Adversary | Can | Cannot |
|---|---|---|
| Relay operator (honest-but-curious) | See room ids, user/device public keys, membership graph, timing, sizes, IPs | Read content, forge ops/log entries, grant roles |
| Malicious relay | Withhold/delay data, refuse service, lie about `rts` (invite expiry), show different log heads to different clients (fork) | Read content, forge signatures. Fork detection: clients gossip head hashes inside encrypted ops (M5) |
| Kicked member | Keep everything they had before removal | Read anything after `epochRotate`; write after `remove` (relay blocks, clients reject) |
| Holder of a leaked invite link | Join while the invite is valid | Join after revoke/expiry; join approval invites without admin approval |
| WhatsApp / link preview crawler | See link path (relay host, room id, invite id) | See invite secret (URL fragment) |
| Stolen unlocked device | Everything the user can do until the device is revoked | After revoke: write or fetch via relay. **Not protected:** already synced data; user secret is shared across devices → identity rotation (M6) required for full recovery |
| XSS in web client | Steal keys from IndexedDB | — mitigate with strict CSP, no third-party scripts, SRI |
| Relay operator with billing enabled | Link a store purchase (and thus potentially a Google account) to a room id | Read content. Mitigation later: blind-signed boost tokens |

`GET /users/{user}/rooms` (self-only, added for seed-restore room recovery) serves a user's own
membership graph back to that user's own devices - it exposes nothing beyond what the relay
operator row above already states the relay operator can see.

## Explicit non-goals (v1)
- Metadata privacy against the relay (membership graph is visible). Sealed-sender style later if needed.
- Forward secrecy within an epoch (MLS would provide it; see ADR-0005).
- Hiding that a user uses the app.

## Trust assumptions
- Relay timestamp `rts` is trusted for invite expiry and use counting.
- libsodium is correct; platform RNG is sound.
- Android Keystore protects at-rest key material (seed is encrypted with a Keystore-wrapped key).
