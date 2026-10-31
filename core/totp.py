"""RFC 6238 time-based one-time codes (30-second steps, 6 digits, SHA-1) for authenticator apps."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_at(secret, step):
    digest = hmac.new(base64.b32decode(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def matching_step(secret, code, after_step=0, now=None):
    """Return the accepted time step, allowing one step of clock drift and refusing reuse."""
    code = "".join(code.split()) if isinstance(code, str) else ""
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = int((time.time() if now is None else now) // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if step > after_step and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret, account):
    label = quote(f"BRIO:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer=BRIO&digits={DIGITS}&period={STEP_SECONDS}"
