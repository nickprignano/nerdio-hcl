"""Azure cloud endpoints, read from `az cloud show` instead of hard-coded.

The kit itself only targets the commercial cloud today, but the readiness engine and `./nerdio fix`
take every endpoint from here so Azure Government works when it reaches the roadmap.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class Cloud:
    name: str
    arm: str  # https://management.azure.com
    graph: str  # https://graph.microsoft.com
    login: str  # https://login.microsoftonline.com
    storage: str  # core.windows.net
    sql: str  # database.windows.net
    keyvault: str  # vault.azure.net

    @property
    def graph_v1(self) -> str:
        return self.graph + "/v1.0"

    def private_dns_zones(self) -> List[str]:
        """The privatelink zones Nerdio Manager's private endpoints use in this cloud."""
        web = WEB_SUFFIX.get(self.name, "azurewebsites.net")
        return [f"privatelink.blob.{self.storage}", f"privatelink.file.{self.storage}",
                f"privatelink.{self.sql}", "privatelink.vaultcore." + self.keyvault.split(".", 1)[1],
                f"privatelink.{web}"]


COMMERCIAL = Cloud("AzureCloud", "https://management.azure.com", "https://graph.microsoft.com",
                   "https://login.microsoftonline.com", "core.windows.net", "database.windows.net", "vault.azure.net")

# `az cloud show` has no App Service suffix, so these come from Microsoft's private endpoint DNS table.
WEB_SUFFIX = {"AzureCloud": "azurewebsites.net", "AzureUSGovernment": "azurewebsites.us",
              "AzureChinaCloud": "chinacloudsites.cn"}
KNOWN = set(WEB_SUFFIX)


def _strip(url: str) -> str:
    return (url or "").rstrip("/")


def from_az(data: Dict) -> Optional[Cloud]:
    try:
        ep, sx = data["endpoints"], data["suffixes"]
        return Cloud(name=data["name"], arm=_strip(ep["resourceManager"]), graph=_strip(ep["microsoftGraphResourceId"]),
                     login=_strip(ep["activeDirectory"]), storage=sx["storageEndpoint"].strip("."),
                     sql=sx["sqlServerHostname"].strip("."), keyvault=sx["keyvaultDns"].strip("."))
    except (KeyError, TypeError, AttributeError):
        return None


def detect(az: Callable) -> Optional[Cloud]:
    """The active cloud through the caller's az runner, or None when az can't say."""
    data = az(["cloud", "show"])
    return from_az(data) if isinstance(data, dict) else None


_current: Optional[Cloud] = None


def current() -> Cloud:
    """The active cloud for code outside the engine (./nerdio fix); commercial when az can't say."""
    global _current
    if _current is None:
        try:
            res = subprocess.run(["az", "cloud", "show", "-o", "json"], capture_output=True, text=True, check=False)
            data = json.loads(res.stdout) if res.returncode == 0 else None
        except (FileNotFoundError, ValueError):
            data = None
        _current = (from_az(data) if isinstance(data, dict) else None) or COMMERCIAL
    return _current
