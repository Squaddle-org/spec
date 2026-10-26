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
**(a), with a known upstream blocker to fix before `webclient` can ship**: real `js(IR)` target.

- **(a) js(IR)** - `commonMain` compiles for `js(IR)` with no structural changes (the module's
  only `expect`/`actual` pairs - `createHttpClient`/`nowUnixSeconds`/`createSqlDriver` - are
  trivially satisfiable). Found and fixed four latent `"%02x".format(it)` calls (JVM-only
  `java.util.Formatter`, blocks every non-JVM target) in `RoomState.kt`, `SnapshotState.kt`,
  `SyncClient.kt`, `CanonicalCborTest.kt` - a fifth call site (`MembershipStateImpl.kt`) had
  already been ported to a portable hex-encoder, these four hadn't; worth consolidating into one
  shared helper when this lands for real. **Blocker**: the pinned crypto dependency
  (`com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings:0.9.5`, confirmed the latest
  release) does publish a `js` variant, but its generated bridge code statically ESM-imports named
  bindings (`crypto_generichash`, `_sodium_init`, `ready`, ...) from a package literally named
  `libsodium-sumo`, while its own `package.json` declares the dependency under a *different* name,
  `libsodium-wrappers-sumo` - confirmed directly against the resolved `node_modules` tree. Worse:
  even pointed at the right package, no version of it (checked up to the current latest, 0.8.4)
  exposes the actual crypto functions as static ESM exports - they're attached to the
  default-exported module object dynamically, after `ready()` resolves, which is incompatible with
  static import analysis by the shape of the library, not a stale pin. `jsBrowserTest`'s webpack
  bundle step fails before a browser ever launches (no headless Chromium was available in the
  spike environment either, a separate, orthogonal gap). Bundle size and the `wasm-unsafe-eval` CSP
  question are consequently **not measured** - blocked upstream of producing a working bundle.
  SqlDelight's browser story is real but non-trivial: `app.cash.sqldelight:web-worker-driver-js`
  exists (2.4.1+) but needs a Web Worker + SQL.js wired up - deferred past the spike, not solved.
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

**Hosting**: `webclient` deploys to its own origin, `app.squaddle.org`, not a path under
`squaddle.org`. `website`'s CSP is already maximally strict (`default-src 'self'; script-src
'self'`, no eval of any kind); `webclient` will need `connect-src` for the relay's HTTPS/WSS origin
and, once the blocker above is fixed, very likely `wasm-unsafe-eval` for libsodium's WASM blob -
widening `website`'s CSP for a static marketing page's benefit is the wrong trade. A separate
origin also gives full IndexedDB/localStorage storage-partition isolation between the marketing
site and whatever holds the wrapped seed. Net effect on `website/nginx.conf`: zero diff.

## Consequences
+ One protocol implementation stays true across jvm/android/js once the blocker is fixed - no
  second CBOR/membership/crypto surface to keep in sync with the spec.
+ `core`'s own portability gap (four JVM-only `String.format` calls) is now a known, fixed, cited
  finding rather than a silent landmine for any future non-JVM target (iOS included, M6).
− `webclient` cannot start on real cryptography until `multiplatform-crypto-libsodium-bindings`'s
  `js` bridge is fixed (upstream PR) or vendored/patched locally (e.g. a webpack alias shimming
  static exports onto the dynamically-populated module) - this is now the literal first blocking
  task for M5a's `core` work, not a nice-to-have.
− SqlDelight's browser-persistence story (Web Worker + SQL.js) is real but unintegrated; the
  `webclient` scaffold's local-storage layer has to solve this from scratch, not copy a working
  pattern from `jvmMain`/`androidMain`.
− A second public TLS host (`app.squaddle.org`) and CORS origin to maintain at the relay.
