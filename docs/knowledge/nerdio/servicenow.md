---
title: "ServiceNow integration (ITSM, Event Management, and Service Catalog)"
summary: "Integrating Nerdio Manager and AVD with ServiceNow: outbound Nerdio task webhooks, Azure Monitor Action Group alerts with Entra OAuth, and inbound keyless REST API automation"
topic: nerdio
status: verified
last_reviewed: 2026-11-09
---

# ServiceNow integration (ITSM, Event Management, and Service Catalog)

Enterprise AVD deployments commonly connect Nerdio Manager and Azure Monitor to ServiceNow across
three paths:

1. **Outbound Nerdio Manager task notifications $\rightarrow$ ServiceNow** (failed auto-scale, host
   pool, or image tasks opening incidents).
2. **Outbound Azure Monitor AVD Insights & budget alerts $\rightarrow$ ServiceNow** (session host
   health, FSLogix storage, and cost thresholds via Common Alert Schema webhooks with Entra OAuth
   or the Azure ITSM Connector).
3. **Inbound ServiceNow ITSM / Service Catalog / Change Management $\rightarrow$ Nerdio REST API**
   (employee onboarding/offboarding desktop assignment, approved change windows triggering Desktop
   Image builds, and help-desk session/host actions).

All three paths are supported in this kit without storing static credentials in repositories or
tfvars.

---

## 1. Outbound Nerdio Manager task notifications (`modules/nerdio-rest-gaps`)

Nerdio Manager sends task notifications (for example when a host pool auto-scale, desktop image
update, or scripted action job fails) using three components under **Settings > Environment >
Nerdio > Email and webhook notifications**:

- **Webhooks** (`GET /api/v1/notifications/webhooks`): each linked webhook has an integer `id`,
  `name`, `url`, and `payloadKind` (`"General"` for a JSON payload consumed by ServiceNow Scripted
  REST APIs or Flow Designer webhook triggers, or `"TeamsAdaptiveCard"` for Microsoft Teams).
  - **API gap:** As of `Get-Nerdio/NME-Terraform-Provider` commit `65e547f`
    (`internal/client/api.json`), `/api/v1/notifications/webhooks` only exposes `GET` (no `POST`,
    `PATCH`, or `DELETE`). Link the ServiceNow webhook URL once in the Nerdio console with Payload
    Kind set to **General** (see [upstream-contributions.md](upstream-contributions.md)).
- **Notification conditions** (`/api/v1/notifications/conditions/nerdio` and
  `/api/v1/notifications/conditions/nerdio/{id}`): full `GET`/`POST`/`PATCH`/`DELETE` CRUD matching
  `targets` (`Global`, `Workspace`, or `HostPool`), `tasks` (such as `["ALL"]`), `statuses`
  (`["Error"]`, `["Canceled"]`, `["Completed"]`), `runByUsers`, and `exclusionKeywords`.
- **Notification actions** (`/api/v1/notifications/actions` and
  `/api/v1/notifications/actions/{id}`): full `GET`/`POST`/`PATCH`/`DELETE` CRUD binding one or
  more condition IDs (`conditions.nerdioConditionIds`) to a linked webhook (`delivery.webhook.id`)
  and/or email recipients, with `includeTaskDetails = true` so ServiceNow receives the full task
  context.

In stage 2 (`environments/example/02-nerdio-config`), declare `notification_conditions` and
`notification_actions` under `rest_gaps`:

```hcl
rest_gaps = {
  notification_conditions = {
    failed-avd-tasks = {
      name     = "All failed Nerdio tasks"
      tasks    = ["ALL"]
      statuses = ["Error"]
    }
  }
  notification_actions = {
    servicenow-incidents = {
      condition_keys       = ["failed-avd-tasks"]
      include_task_details = true
      webhook = {
        enable = true
        id     = 1 # ID from GET /api/v1/notifications/webhooks
      }
    }
  }
}
```

---

## 2. Outbound Azure Monitor AVD Insights alerts (`modules/avd-insights`)

For platform-level telemetry—session host performance counters, FSLogix event logs, and monthly
Azure Consumption Budget thresholds—`modules/avd-insights` configures an Azure Monitor Action Group
(`azurerm_monitor_action_group.avd`) that supports two native ServiceNow delivery methods in stage 1
(`environments/example/01-platform`):

### Option A: Webhook receiver with Entra ID OAuth (`aad_auth`, recommended)

Routes Azure Monitor alerts using the **Common Alert Schema** to ServiceNow Event Management
(`/api/sn_em_connector/em/inbound_event?source=azuremonitor`) or a custom ServiceNow Scripted REST
API, authenticating with a Microsoft Entra application (`aad_auth`) so no shared secret or token is
embedded in the webhook URI:

```hcl
avd_insights = {
  alert_email_receivers = ["avd-ops@contoso.com"]
  monthly_budget_amount = 5000
  webhook_receivers = {
    servicenow-events = {
      service_uri             = "https://contoso.service-now.com/api/sn_em_connector/em/inbound_event?source=azuremonitor"
      use_common_alert_schema = true
      aad_auth = {
        object_id      = "00000000-0000-0000-0000-000000000000"
        identifier_uri = "api://contoso-servicenow-azuremonitor"
      }
    }
  }
}
```

For quick setup via `./nerdio init --advanced`, the `servicenow_webhook_uri` parameter populates
`avd_insights.webhook_receivers.<prefix>.service_uri`.

### Option B: Azure ITSM Connector (`itsm_receivers`)

If the subscription uses the Azure IT Service Management Connector (`Microsoft.OperationsManagement`
solution linked to ServiceNow), configure `itsm_receivers` on `avd_insights` with
`workspace_id = "<subscription_id>|<workspace_uuid>"`, `connection_id`, `ticket_configuration`, and
`region`.

---

## 3. Inbound ServiceNow workflows $\rightarrow$ Nerdio REST API (`modules/nerdio-identity`)

Nerdio's [REST API Overview](https://nmehelp.getnerdio.com/hc/en-us/articles/26124297319821-REST-API-Overview)
highlights ServiceNow ITSM and Service Catalog automation for:

- **Employee onboarding and offboarding:** assigning or unassigning users and groups on AVD host
  pools (`POST /api/v1/arm/hostpool/{subscriptionId}/{resourceGroup}/{hostPoolName}/assign` and
  `/unassign`) or Personal desktops when a Service Catalog request is approved.
- **Change Management approvals:** triggering Desktop Image updates (`/api/v1/desktop-image/{id}`)
  or host pool re-image schedules only after a ServiceNow Change Request (`CHG`) enters its
  approved maintenance window.
- **Service Desk operations:** querying session host health, logging off stuck user sessions, or
  running a remediation scripted action from a ServiceNow incident.

To authenticate ServiceNow to the Nerdio REST API without sharing long-lived client secrets
([entra-app.md](entra-app.md#rest-api-client)):

1. **OIDC workload identity federation (`rest_api_federated_credentials`):** attach an
   `azuread_application_federated_identity_credential` directly to the Nerdio REST API client app
   in `01-platform`:
   ```hcl
   entra_app = {
     grant_admin_consent = true
     rest_api_federated_credentials = {
       servicenow = {
         issuer  = "https://contoso.service-now.com"
         subject = "nerdio-rest-client"
       }
     }
   }
   ```
2. **Additional `RestClient` service principals (`rest_api_additional_principal_object_ids`):**
   if ServiceNow authenticates through an existing Entra OAuth enterprise app or an Azure Logic App
   / Function managed identity, pass its service principal object ID in
   `entra_app.rest_api_additional_principal_object_ids` so Terraform assigns it the `RestClient`
   app role on `nerdio-nmw-app`.
