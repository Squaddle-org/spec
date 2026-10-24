# ADR-0007: Kotlin Multiplatform core, Android first, Web/PWA second, no iOS native yet
Status: accepted

## Context
Native Kotlin preferred. Targets: Android, browser, later Windows. No Apple developer account.

## Decision
`core` in KMP (android, jvm; js/wasm and iOS later). Android UI in Compose. Desktop via Compose Desktop. Web/PWA covers iOS users for now (Web Push for installed PWAs). Push via UnifiedPush, no Firebase.

## Consequences
+ One implementation of protocol logic. No Google/Apple account dependency for v1.
− Must verify libsodium bindings per target before enabling it. PWA key storage weaker than Keystore.
