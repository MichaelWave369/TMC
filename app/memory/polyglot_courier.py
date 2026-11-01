"""Φ Memory Polyglot R3: opt-in encrypted, signed *offline* courier.

This module emits packages only from an R1-approved, one-use R2 projection.
A recipient must independently pin the signing public key and know the
out-of-band passphrase. It creates no listener, route, or cross-app sync.
Synthetic data ONLY until private key custody/approval are reviewed.
"""
from __future__ import annotations

import base64
import json
import secrets
import time
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.memory.polyglot_consumer import create_consumer_handoff
from app.memory.polyglot_gateway import LocalCapabilityGateway

SCHEMA = "phi.memory.polyglot.courier.r3"
ITERATIONS = 310_000
MAX_TTL = 300
MAX_PACKAGE_BYTES = 32768


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _header(reader: str, issued: int, expires: int, salt: str, iv: str,
            ciphertext: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "reader": reader,
        "issued_at": issued, "expires_at": expires,
        "salt": salt, "iv": iv, "ciphertext": ciphertext,
    }


def _signing_bytes(h: dict[str, Any]) -> bytes:
    return ("\n".join(str(h[k]) for k in (
        "schema", "reader", "issued_at", "expires_at",
        "salt", "iv", "ciphertext",
    ))).encode("ascii")


def _aad(h: dict[str, Any]) -> bytes:
    return ("\n".join(str(h[k]) for k in (
        "schema", "reader", "issued_at", "expires_at",
    ))).encode("ascii")


def _passphrase_bytes(passphrase: str) -> bytes:
    if (not isinstance(passphrase, str) or not 16 <= len(passphrase) <= 1024
            or any(ord(ch) < 32 for ch in passphrase)):
        raise ValueError("an out-of-band, strong passphrase is required")
    return passphrase.encode("utf-8")


def seal_consumer_handoff(
    gateway: LocalCapabilityGateway, *, token: str, reader: str,
    passphrase: str, signer: ec.EllipticCurvePrivateKey,
    ttl_seconds: int = 120, now: int | None = None,
) -> dict[str, Any]:
    """Seal one authorized R2 projection for explicit offline delivery.

    The `signer` must be operator-provisioned outside the repository; the
    consumer pins its corresponding public key through a separate channel.
    """
    if (reader not in ("pocketbrain", "brainc")
            or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL
            or not isinstance(signer, ec.EllipticCurvePrivateKey)
            or not isinstance(signer.curve, ec.SECP256R1)):
        raise ValueError("unsupported courier request")
    secret = _passphrase_bytes(passphrase)
    issued = int(time.time()) if now is None else now
    if type(issued) is not int:
        raise ValueError("invalid issuance timestamp")
    # This consumes an R1 token and validates its approval and source revision.
    handoff = create_consumer_handoff(gateway, token=token, reader=reader, now=issued)
    raw = json.dumps(handoff, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(raw) > 16384:
        raise ValueError("oversized consumer projection")
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                    iterations=ITERATIONS).derive(secret)
    h = _header(reader, issued, issued + ttl_seconds, _b64(salt), _b64(iv), "")
    h["ciphertext"] = _b64(AESGCM(key).encrypt(iv, raw, _aad(h)))
    # Python ECDSA produces ASN.1 DER; WebCrypto expects IEEE P1363 r||s.
    r, s = utils.decode_dss_signature(
        signer.sign(_signing_bytes(h), ec.ECDSA(hashes.SHA256()))
    )
    package = {**h, "signature": _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))}
    if len(json.dumps(package).encode("utf-8")) > MAX_PACKAGE_BYTES:
        raise ValueError("oversized sealed package")
    return package
