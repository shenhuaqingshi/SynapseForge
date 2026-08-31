"""
At-Rest Symmetric Cryptographic Engine for SynapseForge.
Encrypts and decrypts sensitive documents, sections, and drafts
using standard PBKDF2-HMAC-SHA256 key derivation with AES-style binary masking / base64 serialization.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class CryptoVault:
    """Provides secure encryption and decryption for proprietary research documents."""

    @staticmethod
    def derive_key(passphrase: str, salt: bytes, iterations: int = 100_000) -> bytes:
        """Derives a 256-bit cryptographic key from user passphrase via PBKDF2-HMAC-SHA256."""
        return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)

    @staticmethod
    def encrypt_content(content: str, passphrase: str) -> Dict[str, str]:
        """
        Encrypts plaintext string using derived key and HMAC authentication.
        Outputs JSON-serializable encrypted bundle.
        """
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(16)
        key = CryptoVault.derive_key(passphrase, salt)

        # Byte-level XOR stream cipher with SHA-256 keystream expansion
        raw_bytes = content.encode("utf-8")
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(raw_bytes):
            keystream.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
            counter += 1

        ciphertext = bytes([b ^ k for b, k in zip(raw_bytes, keystream[:len(raw_bytes)])])
        tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()

        return {
            "cipher": "aes-like-stream-hmac256",
            "salt": base64.b64encode(salt).decode("utf-8"),
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
            "tag": base64.b64encode(tag).decode("utf-8"),
        }

    @staticmethod
    def decrypt_content(encrypted_bundle: Dict[str, str], passphrase: str) -> str:
        """Decrypts and authenticates ciphertext. Raises ValueError on authentication failure."""
        salt = base64.b64decode(encrypted_bundle["salt"])
        nonce = base64.b64decode(encrypted_bundle["nonce"])
        ciphertext = base64.b64decode(encrypted_bundle["ciphertext"])
        expected_tag = base64.b64decode(encrypted_bundle["tag"])

        key = CryptoVault.derive_key(passphrase, salt)

        # Authenticate with HMAC
        computed_tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_tag, computed_tag):
            raise ValueError("Decryption failed: Invalid passphrase or corrupted ciphertext (HMAC tag mismatch).")

        # Decrypt
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ciphertext):
            keystream.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
            counter += 1

        decrypted_bytes = bytes([c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)])])
        return decrypted_bytes.decode("utf-8")

    def encrypt_file(self, input_file: Path, output_file: Path, passphrase: str) -> Dict[str, Any]:
        """Encrypts a file and saves as .enc file."""
        text = input_file.read_text(encoding="utf-8")
        bundle = self.encrypt_content(text, passphrase)
        output_file.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "input_file": str(input_file),
            "output_file": str(output_file),
            "encrypted_bytes": output_file.stat().st_size,
        }

    def decrypt_file(self, input_file: Path, output_file: Path, passphrase: str) -> Dict[str, Any]:
        """Decrypts a .enc file and restores original content."""
        bundle = json.loads(input_file.read_text(encoding="utf-8"))
        plaintext = self.decrypt_content(bundle, passphrase)
        output_file.write_text(plaintext, encoding="utf-8")
        return {
            "ok": True,
            "input_file": str(input_file),
            "output_file": str(output_file),
            "decrypted_chars": len(plaintext),
        }
