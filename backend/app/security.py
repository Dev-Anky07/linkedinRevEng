import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SessionCipher:
    """Encrypts the mutable Redis session record with AES-256-GCM."""

    def __init__(self, encoded_key: str):
        try:
            raw_key = base64.urlsafe_b64decode(encoded_key.strip() + "===")
        except Exception as error:
            raise ValueError("SESSION_ENCRYPTION_KEY must be base64 encoded.") from error
        if len(raw_key) != 32:
            raise ValueError("SESSION_ENCRYPTION_KEY must decode to exactly 32 bytes.")
        self._aesgcm = AESGCM(raw_key)

    def encrypt(self, payload: dict[str, Any]) -> dict[str, Any]:
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return {"version": 1, "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"), "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii")}

    def decrypt(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if envelope.get("version") != 1:
            raise ValueError("Unsupported encrypted session version.")
        try:
            nonce = base64.urlsafe_b64decode(envelope["nonce"])
            ciphertext = base64.urlsafe_b64decode(envelope["ciphertext"])
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as error:
            raise ValueError("Unable to decrypt the Redis session record.") from error
        payload = json.loads(plaintext.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("The decrypted Redis session record is invalid.")
        return payload
