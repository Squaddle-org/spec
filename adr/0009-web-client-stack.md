# ADR-0009: Web client protocol stack

Status: accepted

## Context
M5 needs a browser client. ADR-0007 flagged this exact decision ("js/wasm... later... must verify
libsodium bindings per target before enabling it") without resolving it. Three candidates,
measured via real spikes (branches `spike/adr-0009-js-ir` / `spike/adr-0009-wasmjs-negative` in
`core`, never merged) rather than decided on paper:

(a) `core`'s Kotlin `js(IR) { browser() }` target, exported as an ES module, thin TS/vanilla UI.
(b) Compose for Web (`wasmJs`), reusing `core`.
(c) A standalone TypeScript reimplementation of the protocol (no `core` reuse).

## Decision
**(a)**: real `js(IR)` target. Its crypto-bridge blocker is fixed, and - beyond just bundling -
verified cryptographically correct end to end in a real JS engine (V8, via Node/Vitest): real
24-word mnemonic generation, correct key derivation, valid Ed25519 signatures, and
restore-from-mnemonic correctly reproducing the same user keys with a fresh device keypair
(PROTOCOL.md §2.1). This is not yet a real-*browser* (DOM/CSP-enforcement) check - see
Consequences for what's still open.

- **(a) js(IR)** - `commonMain` compiles for `js(IR)` with no structural changes (the module's
  only `expect`/`actual` pairs - `createHttpClient`/`nowUnixSeconds`/`createSqlDriver` - are
  trivially satisfiable). Found and fixed four latent `"%02x".format(it)` calls (JVM-only
  `java.util.Formatter`, blocks every non-JVM target) in `RoomState.kt`, `SnapshotState.kt`,
  `SyncClient.kt`, `CanonicalCborTest.kt` - a fifth call site (`MembershipStateImpl.kt`) had
  already been ported to a portable hex-encoder, these four hadn't; worth consolidating into one
  shared helper when this lands for real. **Crypto bridge**: the pinned crypto dependency
  (`com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5`, confirmed the latest
  release) does publish a `js` variant, but its generated bridge code statically ESM-imports named
  bindings (`crypto_generichash`, `_sodium_init`, `ready`, ...) from a package literally named
  `libsodium-sumo`, whose real ESM build has no static named exports at all (`export default
  Module` only - the raw Emscripten exports are attached to that object dynamically, after
  `ready()` resolves) - confirmed directly against the resolved `node_modules` tree, not a stale
  version pin. **Fixed** (not just diagnosed) via a `webpack.config.d` shim: a hand-written module
  aliased onto the literal `'libsodium-sumo'` import specifier that lazily forwards each needed
  symbol to the real Module object's properties at *call* time rather than import time (sidesteps
  a second, separate incompatibility this surfaced too - `libsodium-wrappers-sumo`'s own internals
  do a bare, synchronous `require('libsodium-sumo')` that cannot consume an async ES module using
  top-level await) plus a `resolve.fallback` for a dead-code Node `url`/`path` import inside
  `libsodium-sumo`'s own polyfill that webpack's static analysis doesn't see through a runtime
  guard for. Result: `jsBrowserTest`'s webpack bundle step succeeds with **zero** resolution
  errors. **Verified correct, not just bundling**: `webclient`'s own consumer-side build hits the
  exact same broken import (confirmed independently - the fix isn't webpack-specific) via a
  completely different bundler, Vite/Rollup - ported the same shim as a Vite `resolve.alias`
  (plus a second fix this surfaced: `libsodium-wrappers-sumo`'s own `package.json` declares no
  `exports` map, and `core` is consumed via an npm `file:` dependency, whose symlink Vite follows
  to a real path *outside* `webclient`'s own `node_modules` tree by default - `preserveSymlinks:
  true` fixes that). A real `@JsExport` facade (`IdentityApi`, new - thin, Promise-wrapping,
  no logic duplicated) calling actual identity create/restore through this path, run via Vitest
  (Node + V8, the same engine every real browser also uses - the crypto path here needs nothing
  DOM-specific, only `crypto.getRandomValues`, native since Node 19), produced: a real 24-word
  mnemonic, a real 32-byte Ed25519 public key, a real 64-byte signature verifiable against it, and
  `restore()` from that exact mnemonic reproducing the identical user/box keys with a *different*
  freshly-minted device keypair - exactly PROTOCOL.md §2.1's design. The webpack bundle (measured
  via the same build before this Vite path existed) is 1,115 KB raw / 348 KB gzip for
  `IdentityApi` alone (core's membership/content-plane/sync-client code pulled in transitively,
  Kotlin stdlib included) - a real number now, not a placeholder; expect it to grow as more of
  `core`'s surface gets `@JsExport`ed, and revisit before M5a ships if it's a problem. Still open:
  an actual browser DOM/CSP-enforcement check (`wasm-unsafe-eval` requirement, specifically) - V8
  running under Node enforces no CSP at all, so that one question genuinely needs a real browser,
  unlike the cryptographic-correctness question above. **Persistence**: no official SqlDelight
  browser driver is usable here - the only one that exists, `web-worker-driver-js`, is async by
  construction (`generateAsync`), but `commonMain`'s generated `SquaddleDb` queries are
  synchronous and shared with jvm/android; switching the whole module to async for one target's
  benefit wasn't an option. **Closed**: `SqlJsDriver` hand-implements the synchronous `SqlDriver`
  interface directly against sql.js (own SAVEPOINT-based nested-transaction support included),
  verified end to end through `LocalStore`'s real generated queries via the same Vitest path as
  the identity check above - genuine `CREATE TABLE`/`INSERT`/byte-exact `SELECT` round-trips, not
  a mock. In-memory only for now; sql.js's own `export()`/`import()` would be the next step for
  persistence across page reloads, not done here.
- **(b) wasmJs** - real negative repro: adding `wasmJs { browser() }` and running
  `:wasmJsMainClasses` fails at dependency resolution outright, Gradle exhaustively checking every
  published variant of the pinned crypto library (jvm, androidJvm, every native target, js) and
  finding none declaring `org.jetbrains.kotlin.wasm.target`. No official `wasmJs` variant exists in
  any released version; only an unaudited third-party fork adds one - not viable for
  security-critical crypto. Bundle size/CSP/a11y/maintenance for Compose for Web otherwise come
  from documented, not measured-in-repo, general knowledge. Also: `core/gradle/libs.versions.toml`
  already carries a `compose-compiler` alias for Android's AGP tooling - unrelated to JetBrains
  Compose Multiplatform; (b) would be a second, disjoint Compose flavor sharing zero UI code with
  `android/`'s plain Jetpack Compose, only `core`'s non-UI logic shared either way.
- **(c) standalone TS** - one real data point: npm's `libsodium-wrappers`, used the way the
  library actually intends (`await sodium.ready`, then property access on its default export -
  not static ESM imports), correctly reproduces `request-auth.json`'s
  `request-auth-get-no-query` vector end to end (BLAKE2b-256 signingInput + Ed25519 verify, byte
  for byte). So browser libsodium itself works fine; (a)'s failure is specifically the Kotlin/JS
  interop generator's import style, not a fundamental browser limitation. Rejected anyway: a
  second protocol implementation is a second bug surface and duplicated test-vector maintenance
  forever, directly against "one protocol implementation preferred" - the criterion this ADR
  weighs most heavily, and the only one (a) doesn't need a second implementation to satisfy once
  its one real blocker is fixed.

**Hosting**: `webclient` deploys to its own origin, `client.squaddle.org`, not a path under
`squaddle.org`. `website`'s CSP is already maximally strict (`default-src 'self'; script-src
'self'`, no eval of any kind); `webclient` will need `connect-src` for the relay's HTTPS/WSS origin
and, once the blocker above is fixed, very likely `wasm-unsafe-eval` for libsodium's WASM blob -
widening `website`'s CSP for a static marketing page's benefit is the wrong trade. A separate
origin also gives full IndexedDB/localStorage storage-partition isolation between the marketing
site and whatever holds the wrapped seed. Net effect on `website/nginx.conf`: zero diff.

## Consequences
+ One protocol implementation stays true across jvm/android/js - no second CBOR/membership/crypto
  surface to keep in sync with the spec.
+ `core`'s own portability gap (four JVM-only `String.format` calls, since consolidated into one
  shared `Hex` helper) is now a known, fixed, cited finding rather than a silent landmine for any
  future non-JVM target (iOS included, M6).
+ The crypto bridge is fixed and verified cryptographically correct, not just diagnosed - two
  small shim files (one per bundler: `core`'s own `webpack.config.d`, `webclient`'s
  `vite-shims/`), committed in both repos, no upstream dependency.
+ `IdentityApi`, a real `@JsExport` facade, exists and is proven to work end to end
  (`IdentityStore` in `webclient` calls it; 9 passing tests cover both repos' sides of the
  boundary) - the pattern for exposing more of `core` to TypeScript as later features need it is
  now established, not theoretical.
− A real browser DOM/CSP check (specifically: is `wasm-unsafe-eval` actually required) is still
  open - V8-under-Node enforces no CSP, so this is a genuinely different question from the
  cryptographic-correctness one above, which real-browser access isn't needed to answer.
+ `SqlJsDriver`, a from-scratch synchronous `SqlDriver` against sql.js, closes the browser
  persistence gap no official SqlDelight driver could (verified end to end through `LocalStore`'s
  real generated queries, same rigor as `IdentityApi`) - `webclient` gets `core`'s actual
  `LocalStore`/`SyncClient`, not a reimplementation.
− `SqlJsDriver` is in-memory only - data doesn't survive a page reload yet. sql.js's own
  `export()`/`import()` (persisted to IndexedDB, mirroring `IdentityApi`'s own key storage) is
  the real next step, not done here.
− A second public TLS host (`client.squaddle.org`) and CORS origin to maintain at the relay.
− Bundle size (1,115 KB raw / 348 KB gzip for identity alone, core's membership/sync-client code
  and the Kotlin stdlib pulled in transitively) will grow as more of `core` gets `@JsExport`ed -
  worth revisiting with `manualChunks`/code-splitting before M5a ships if it becomes a problem.
