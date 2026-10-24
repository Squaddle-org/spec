# ADR-0011: Polyrepo with a versioned spec as the contract
Status: accepted (supersedes the monorepo layout of the bootstrap)

## Context
Preference for separate repos per component. The risk of a polyrepo is drift between Kotlin and Go protocol implementations.

## Decision
- `spec` holds the protocol, test vectors and all cross-cutting docs (architecture, threat model, roadmap, ADRs).
- `spec` is released via tags; each release attaches `testvectors.tar.gz`.
- `core` and `relay` pin `SPEC_VERSION` and run the vectors in CI; local dev can override with `SQUADDLE_SPEC_DIR`.
- `core` is published as `org.squaddle:core` (Maven Central, namespace verified via squaddle.org; GitHub Packages as interim).
- `android` depends on a released `core`, with a composite build for local work.

## Consequences
+ Clear ownership and release cadence per component, small CI per repo.
+ The spec release is the explicit contract — drift shows up as failing vectors.
− Protocol changes need 3 PRs in order (spec → core/relay → app).
− Vector generation lives in `core` but output is committed in `spec`.
