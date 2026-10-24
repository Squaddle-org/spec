# ADR-0010: Relay-local room limits, paid room boosts
Status: accepted

## Context
No accounts, no ads, no data sales — the privacy promise is the product. Hosting the official relay still costs money.
Limits must not leak into the protocol (federation/self-hosting) and must never hold content hostage.

## Decision
- Limits are relay policy (PROTOCOL.md §8), exposed via `GET /rooms/{room}/limits`, not part of the signed log.
- Free tier on the hosted relay; any member can buy a "Room Boost" (subscription) for a room, Discord-style.
- Entitlements bind a store purchase token (Google Play) or an operator voucher to one room id.
- Downgrades only block new joins; members, content and state are never removed. Retention prunes only ops already covered by snapshots.
- `foss` flavor without Google deps; boosts there via vouchers/donations.
- Self-hosted relays default to unlimited.

## Consequences
+ Sustainable hosting without touching content or identities. Fits the no-account model (pay per room, not per person).
− Relay can link a store purchase to a room id (THREAT_MODEL.md). Store fees (Google 15%).
− Pay-per-room means only one person pays for the group — matches how groups already work ("ich zahl, ihr schuldet mir 'n Bier").
