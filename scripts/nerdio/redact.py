"""Mask tenant-identifying values in command output before it's shared (chat, issues, support).

GUIDs, public IP addresses, email addresses, tenant domains, and the signed-in account's
subscription name and user name are replaced with placeholders. Private address ranges
(10/8, 172.16/12, 192.168/16) and Azure's platform DNS address are kept because they help
with troubleshooting and identify nobody.
"""

from __future__ import annotations

import ipaddress
import re

from engine import az_json

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TENANT_DOMAIN = re.compile(r"\b[A-Za-z0-9-]+\.(?:onmicrosoft\.com|onmicrosoft\.us|mail\.onmicrosoft\.com)\b", re.I)
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
KEEP_IPS = {"168.63.129.16", "169.254.169.254"}


def _ip(match: re.Match) -> str:
    text = match.group(0)
    try:
        addr = ipaddress.IPv4Address(text)
    except ValueError:
        return text
    if addr.is_private or addr.is_loopback or text in KEEP_IPS:
        return text
    return "<public-ip>"


def account_terms() -> list[str]:
    """Names from az account show that would identify the tenant or the person."""
    acct = az_json(["account", "show"]) or {}
    terms = [acct.get("name"), (acct.get("user") or {}).get("name"), acct.get("tenantDefaultDomain"),
             acct.get("tenantDisplayName")]
    return sorted({t for t in terms if t and len(t) > 3}, key=len, reverse=True)


def redact(text: str, terms: list[str] | None = None) -> str:
    text = ANSI.sub("", text)
    for term in terms or []:
        text = re.sub(re.escape(term), "<account>", text, flags=re.I)
    text = EMAIL.sub("<email>", text)
    text = TENANT_DOMAIN.sub("<tenant-domain>", text)
    text = GUID.sub("<id>", text)
    return IPV4.sub(_ip, text)
