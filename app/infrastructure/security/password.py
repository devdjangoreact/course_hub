import hashlib

import bcrypt


def _password_bytes(plain: str) -> bytes:
    # Pre-hash avoids bcrypt's 72-byte input limit without truncating user passwords.
    return hashlib.sha256(plain.encode("utf-8")).digest()


def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_password_bytes(plain), password_hash.encode("utf-8"))
