# Squaddle Spec

Normative protocol and design documents for Squaddle — an account-less, E2E-encrypted app for friend groups
to collect, vote on and schedule ideas. Implementations: [core](https://github.com/squaddle-org/core) (Kotlin), [relay](https://github.com/squaddle-org/relay) (Go).

| Path | Content |
|---|---|
| `protocol/PROTOCOL.md` | Wire protocol v1 (normative) |
| `protocol/relay-api.yaml` | Relay HTTP API (OpenAPI 3.1) |
| `protocol/testvectors/` | Cross-implementation test vectors |
| `ARCHITECTURE.md` | Big picture |
| `THREAT_MODEL.md` | Guarantees and non-goals |
| `ROADMAP.md` | Milestones across all repos |
| `adr/` | Architecture Decision Records |

Releases: tags `vX.Y.Z[-draft.N]`, each with `testvectors.tar.gz` attached (see `.github/workflows/release.yml`).

## License

The protocol/design text (everything outside `tools/`) is [CC-BY-4.0](LICENSE) — the protocol
should be freely implementable, with attribution. `tools/` (test vector generation/verification
tooling) is separately [Apache-2.0](tools/LICENSE), since that's code, not protocol text.
