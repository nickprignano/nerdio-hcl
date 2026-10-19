"""Read-only readiness engine for Nerdio Manager deployments.

One check registry and runner behind every front door: `./nerdio preflight`, the deploy
pipeline, the setup chat (through the pipeline) and, later, a standalone zipapp. Checks only read
(az show/list, GET); every az and HTTP call goes through a context object so tests can replace
them, and a guard refuses anything that writes.

The spec is docs/knowledge/nerdio/readiness.md (decision 0026). Standard library only, and
Python 3.9 syntax, because Azure Cloud Shell's Python is 3.9.
"""

__version__ = "0.1.0"
SCHEMA_ID = "nerdio-readiness/1"
