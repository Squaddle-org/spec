#!/usr/bin/env python3
"""Independent (PyNaCl, not core's ionspin/Kotlin stack) re-check of identity.json and
devicecert.json. Every structure here is re-derived from each vector's "input" using a from-
scratch Python implementation of PROTOCOL.md §2.1/§2.2, then diffed against "expected" - the
point is that a bug shared between core's CanonicalCbor encoder and core's own vector generator
would not be caught by core's tests alone, since both sides are the same code.

Usage: python3 verify_vectors.py [path/to/protocol/testvectors]
(defaults to ../protocol/testvectors relative to this script, i.e. the sibling spec checkout)
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import nacl.bindings
import nacl.encoding
import nacl.hash
import nacl.signing
from nacl.exceptions import BadSignatureError

TOOLS_DIR = Path(__file__).resolve().parent
WORDLIST = TOOLS_DIR.joinpath("wordlist_english.txt").read_text().split()
WORD_INDEX = {w: i for i, w in enumerate(WORDLIST)}
VALID_WORD_COUNTS = (12, 15, 18, 21, 24)
VALID_ENTROPY_LENGTHS = (16, 20, 24, 28, 32)


class VectorError(ValueError):
    pass


# ---- base64url, no padding (PROTOCOL.md: "binary fields are base64url without padding") ----

def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


# ---- PROTOCOL.md §1 primitives, via PyNaCl ----

def blake2b256(*parts: bytes) -> bytes:
    return nacl.hash.blake2b(b"".join(parts), digest_size=32, encoder=nacl.encoding.RawEncoder)


def kdf_derive(master: bytes, subkey_id: int, context: str, length: int = 32) -> bytes:
    """crypto_kdf_derive_from_key - PyNaCl doesn't bind crypto_kdf itself, but for its default
    "blake2b" primitive (crypto_kdf_PRIMITIVE) libsodium defines it directly as BLAKE2b keyed by
    `master`, salted with the subkey id (8 bytes little-endian, zero-padded to SALTBYTES) and
    personalized with `context` (zero-padded to PERSONALBYTES) - see libsodium's kdf_blake2b.c.
    Verified against core's own identity.json vectors, not just asserted."""
    assert len(context) == 8, "crypto_kdf context must be exactly 8 ASCII chars"
    salt = subkey_id.to_bytes(8, "little")
    return nacl.bindings.crypto_generichash_blake2b_salt_personal(
        b"", digest_size=length, key=master, salt=salt, person=context.encode("ascii"),
    )


def signing_input(domain: str, unsigned_cbor: bytes) -> bytes:
    return b"SQDL1" + domain.encode("ascii") + b"\x00" + blake2b256(unsigned_cbor)


# ---- minimal canonical CBOR (uint/bytes/text/map only - exactly what DeviceCert needs) ----

def cbor_head(major: int, arg: int) -> bytes:
    if arg < 24:
        return bytes([major << 5 | arg])
    if arg <= 0xFF:
        return bytes([major << 5 | 24, arg])
    if arg <= 0xFFFF:
        return bytes([major << 5 | 25]) + arg.to_bytes(2, "big")
    if arg <= 0xFFFFFFFF:
        return bytes([major << 5 | 26]) + arg.to_bytes(4, "big")
    return bytes([major << 5 | 27]) + arg.to_bytes(8, "big")


def cbor_uint(n: int) -> bytes:
    return cbor_head(0, n)


def cbor_bytes(b: bytes) -> bytes:
    return cbor_head(2, len(b)) + b


def cbor_text(s: str) -> bytes:
    u = s.encode("utf-8")
    return cbor_head(3, len(u)) + u


def cbor_map(pairs: list[tuple[int, bytes]]) -> bytes:
    """`pairs` MUST already be sorted ascending by key - this does not sort for you."""
    out = cbor_head(5, len(pairs))
    for key, value in pairs:
        out += cbor_uint(key) + value
    return out


def _cbor_read_head(data: bytes, pos: int) -> tuple[int, int, int]:
    b0 = data[pos]
    major, info = b0 >> 5, b0 & 0x1F
    pos += 1
    if info < 24:
        return major, info, pos
    sizes = {24: 1, 25: 2, 26: 4, 27: 8}
    if info not in sizes:
        raise VectorError(f"unsupported additional info {info}")
    n = sizes[info]
    return major, int.from_bytes(data[pos:pos + n], "big"), pos + n


def cbor_decode_map(data: bytes) -> dict[int, object]:
    """Decodes a single top-level map of uint keys to uint/bytes/text values. Not a general or
    strict-canonical decoder - that is CanonicalCborCodec's job (see cbor-reject.json); this just
    needs to read back the specific DeviceCert shape used in devicecert.json's reject vectors."""
    major, count, pos = _cbor_read_head(data, 0)
    if major != 5:
        raise VectorError(f"expected a top-level map, got major type {major}")
    result: dict[int, object] = {}
    for _ in range(count):
        key_major, key, pos = _cbor_read_head(data, pos)
        if key_major != 0:
            raise VectorError("map key must be an unsigned integer")
        val_major, arg, pos = _cbor_read_head(data, pos)
        if val_major == 0:
            result[key] = arg
        elif val_major == 2:
            result[key] = data[pos:pos + arg]
            pos += arg
        elif val_major == 3:
            result[key] = data[pos:pos + arg].decode("utf-8")
            pos += arg
        else:
            raise VectorError(f"unsupported value major type {val_major}")
    return result


# ---- BIP39 (PROTOCOL.md §2.1) - SHA-256 is BIP39's own requirement, not a protocol primitive ----

def _bytes_to_bits(b: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in b)


def _bits_to_bytes(bits: str) -> bytes:
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def entropy_to_mnemonic(entropy: bytes) -> list[str]:
    if len(entropy) not in VALID_ENTROPY_LENGTHS:
        raise VectorError(f"entropy must be one of {VALID_ENTROPY_LENGTHS} bytes, was {len(entropy)}")
    checksum_bit_count = len(entropy) // 4
    checksum = hashlib.sha256(entropy).digest()
    bits = _bytes_to_bits(entropy) + _bytes_to_bits(checksum)[:checksum_bit_count]
    return [WORDLIST[int(bits[i:i + 11], 2)] for i in range(0, len(bits), 11)]


def mnemonic_to_entropy(words: list[str]) -> bytes:
    if len(words) not in VALID_WORD_COUNTS:
        raise VectorError(f"word count must be one of {list(VALID_WORD_COUNTS)}, was {len(words)}")
    indices = []
    for w in words:
        if w not in WORD_INDEX:
            raise VectorError(f"'{w}' is not a BIP39 English wordlist word")
        indices.append(WORD_INDEX[w])
    bits = "".join(f"{idx:011b}" for idx in indices)
    total_bits = len(words) * 11
    entropy_bit_count = total_bits * 32 // 33
    checksum_bit_count = total_bits - entropy_bit_count
    entropy = _bits_to_bytes(bits[:entropy_bit_count])
    expected_checksum_bits = bits[entropy_bit_count:]
    actual_checksum_bits = _bytes_to_bits(hashlib.sha256(entropy).digest())[:checksum_bit_count]
    if expected_checksum_bits != actual_checksum_bits:
        raise VectorError("checksum mismatch")
    return entropy


# ---- vector checks ----

def verify_identity(path: Path) -> list[str]:
    errors = []
    for vector in json.loads(path.read_text()):
        name = vector["name"]
        try:
            expected = vector.get("expected", {})
            if expected.get("accept") is False:
                words = vector["input"]["mnemonic"]
                try:
                    mnemonic_to_entropy(words)
                    errors.append(f"{name}: expected reject, but mnemonic_to_entropy succeeded")
                except VectorError:
                    pass
                continue

            entropy = b64u_decode(vector["input"]["entropy"])
            master = blake2b256(entropy)
            user_sign_seed = kdf_derive(master, 1, "SQDLUSIG")
            user_box_seed = kdf_derive(master, 2, "SQDLUBOX")
            backup_key = kdf_derive(master, 3, "SQDLBKUP")
            user_key = bytes(nacl.signing.SigningKey(user_sign_seed).verify_key)
            user_box_key, _ = nacl.bindings.crypto_box_seed_keypair(user_box_seed)
            mnemonic = entropy_to_mnemonic(entropy)

            checks = {
                "mnemonic": (mnemonic, expected["mnemonic"]),
                "master": (b64u_encode(master), expected["master"]),
                "userKey": (b64u_encode(user_key), expected["userKey"]),
                "userBoxKey": (b64u_encode(user_box_key), expected["userBoxKey"]),
                "backupKey": (b64u_encode(backup_key), expected["backupKey"]),
            }
            for field, (actual, expect) in checks.items():
                if actual != expect:
                    errors.append(f"{name}: {field} mismatch: got {actual!r}, expected {expect!r}")
        except Exception as e:  # noqa: BLE001 - a vector-level failure must not abort the whole run
            errors.append(f"{name}: unexpected error: {e}")
    return errors


def devicecert_accepts(fields: dict[int, object]) -> tuple[bool, str]:
    """Independently applies PROTOCOL.md §2.2/§9: v==1, label<=64 chars, Ed25519 signature valid
    under domain "devcert" - the same three rules core/identity/DeviceCert.kt verify() applies."""
    v = fields[0]
    if v != 1:
        return False, f"unknown major v={v}"
    label = fields[4]
    if len(label) > 64:
        return False, "label exceeds 64 chars"
    sig = fields.get(6)
    if sig is None:
        return False, "missing signature"
    unsigned = cbor_map([
        (0, cbor_uint(v)),
        (1, cbor_bytes(fields[1])),
        (2, cbor_bytes(fields[2])),
        (3, cbor_bytes(fields[3])),
        (4, cbor_text(label)),
        (5, cbor_uint(fields[5])),
    ])
    try:
        nacl.signing.VerifyKey(fields[1]).verify(signing_input("devcert", unsigned), sig)
        return True, ""
    except BadSignatureError:
        return False, "signature does not verify"


def verify_devicecert(path: Path) -> list[str]:
    errors = []
    for vector in json.loads(path.read_text()):
        name = vector["name"]
        try:
            expected = vector.get("expected", {})
            accept_expected = expected["accept"]

            if not accept_expected:
                fields = cbor_decode_map(b64u_decode(vector["input"]["cbor"]))
                accepts, _ = devicecert_accepts(fields)
                if accepts:
                    errors.append(f"{name}: expected reject, but independently verified as accepted")
                continue

            fields = cbor_decode_map(b64u_decode(expected["cbor"]))
            accepts, reason = devicecert_accepts(fields)
            if not accepts:
                errors.append(f"{name}: expected accept, but independently rejected: {reason}")
                continue

            unsigned = cbor_map([
                (0, cbor_uint(fields[0])),
                (1, cbor_bytes(fields[1])),
                (2, cbor_bytes(fields[2])),
                (3, cbor_bytes(fields[3])),
                (4, cbor_text(fields[4])),
                (5, cbor_uint(fields[5])),
            ])
            if b64u_encode(unsigned) != expected["unsignedCbor"]:
                errors.append(f"{name}: unsignedCbor mismatch")
            if b64u_encode(signing_input("devcert", unsigned)) != expected["signingInput"]:
                errors.append(f"{name}: signingInput mismatch")
            if b64u_encode(fields[6]) != expected["sig"]:
                errors.append(f"{name}: sig mismatch")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: unexpected error: {e}")
    return errors


def main() -> int:
    vectors_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else TOOLS_DIR.parent / "protocol" / "testvectors"
    errors = verify_identity(vectors_dir / "identity.json") + verify_devicecert(vectors_dir / "devicecert.json")
    if errors:
        print(f"FAIL: {len(errors)} mismatch(es)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: identity.json + devicecert.json independently re-verified via PyNaCl ({vectors_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
