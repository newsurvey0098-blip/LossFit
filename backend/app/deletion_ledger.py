"""Signed export format for the restricted account-deletion ledger."""
import hashlib
import hmac
import json
import re

FORMAT = "lossfit-deletion-ledger-v1"


def canonical_payload(digests: list[str]) -> bytes:
    cleaned = sorted(set(digests))
    if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in cleaned):
        raise ValueError("Deletion ledger contains an invalid digest")
    return json.dumps({"format": FORMAT, "digests": cleaned}, separators=(",", ":"), sort_keys=True).encode()


def export_ledger(digests: list[str], secret: str) -> dict:
    payload = canonical_payload(digests)
    return {"format": FORMAT, "digests": json.loads(payload)["digests"], "signature": hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()}


def verify_ledger(document: dict, secret: str) -> list[str]:
    if not isinstance(document, dict) or document.get("format") != FORMAT or not isinstance(document.get("digests"), list) or len(document["digests"]) > 1_000_000:
        raise ValueError("Unsupported or malformed deletion ledger")
    payload = canonical_payload(document["digests"])
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    signature = document.get("signature")
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise ValueError("Deletion ledger signature is invalid")
    return json.loads(payload)["digests"]
