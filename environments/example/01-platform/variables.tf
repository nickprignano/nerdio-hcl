variable "tenant_id" {
  description = "Entra tenant that hosts Nerdio Manager. Pinning it stops a stray az login from deploying into the wrong tenant."
  type        = string
}

variable "subscription_id" {
  description = "Primary subscription that hosts Nerdio Manager and (by default) AVD spokes."
  type        = string
}

variable "prefix" {
  description = "Short naming prefix, e.g. \"contoso-nme\"."
  type        = string
}

variable "control_plane_location" {
  description = "Azure region that hosts the Nerdio Manager control plane (App Service, SQL, Key Vault, Automation, Monitoring)."
  type        = string
  default     = "eastus2"
}

variable "control_plane_dr_location" {
  description = "Optional paired Azure region for Nerdio control-plane disaster recovery metadata."
  type        = string
  default     = null
}

variable "cloud" {
  description = "Azure cloud environment: public (AzureCloud) or usgovernment (AzureUSGovernment)."
  type        = string
  default     = "public"

  validation {
    condition     = contains(["public", "usgovernment"], var.cloud)
    error_message = "cloud must be public or usgovernment."
  }
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "resource_groups" {
  description = "Control-plane resource group names keyed by role (nerdio, monitoring)."
  type        = map(string)
  validation {
    condition     = alltrue([for k in ["nerdio", "monitoring"] : contains(keys(var.resource_groups), k)])
    error_message = "resource_groups must contain at least the control-plane keys: nerdio and monitoring."
  }
}

variable "existing_resource_groups" {
  description = "Role keys in resource_groups (such as [\"nerdio\"]) that already exist in Azure, for example when Nerdio Manager was deployed from the Azure portal Marketplace before running Terraform."
  type        = set(string)
  default     = []
}

variable "existing_private_dns_zone_ids" {
  description = "Optional map of existing central hub Private DNS zone IDs (sql, vault, file, blob, web, automation, wvd). When empty, the kit creates them once in the primary/control-plane spoke and links all regional VNets."
  type        = map(string)
  default     = {}
}

variable "extra_private_dns_zones" {
  description = "Optional extra privatelink zones to create (automation, wvd)."
  type        = set(string)
  default     = []
}

variable "regions" {
  description = <<-EOT
    Peer map of AVD workload regions keyed by Azure region name (e.g. "eastus2", "westeurope").
    Each region gets its own spoke resource groups (network, hostpools, storage), spoke VNet
    (standalone NAT gateway, hub VNet peering, or Virtual WAN connection + optional firewall UDR),
    and optional FSLogix (Azure Files or Azure NetApp Files) profile storage.
  EOT
  type = map(object({
    location        = optional(string)
    subscription_id = optional(string)
    resource_groups = object({
      network   = string
      hostpools = string
      storage   = string
    })
    existing_resource_groups = optional(set(string), [])
    network = object({
      address_space = list(string)
      subnets = object({
        session_hosts     = string
        private_endpoints = string
        app_integration   = string
      })
      dns_servers                          = optional(list(string), [])
      connectivity_mode                    = optional(string, "standalone")
      hub_vnet_id                          = optional(string)
      use_remote_gateways                  = optional(bool, false)
      virtual_hub_id                       = optional(string)
      vwan_internet_security_enabled       = optional(bool, true)
      firewall_next_hop_ip                 = optional(string)
      bypass_avd_control_plane_on_internet = optional(bool, true)
      create_nat_gateway                   = optional(bool, true)
    })
    fslogix = optional(object({
      storage_account_name      = string
      share_quota_gb            = optional(number, 1024)
      app_attach_share_quota_gb = optional(number)
      identity_source           = optional(string, "AADKERB")
      user_group_object_ids     = optional(list(string), [])
      admin_group_object_ids    = optional(list(string), [])
      active_directory = optional(object({
        domain_name         = string
        domain_guid         = string
        domain_sid          = optional(string)
        forest_name         = optional(string)
        netbios_domain_name = optional(string)
        storage_sid         = optional(string)
      }))
    }))
    anf = optional(object({
      subnet_cidr        = string
      service_level      = optional(string, "Premium")
      pool_size_in_tb    = optional(number, 4)
      volume_quota_in_gb = optional(number, 1024)
      volume_path        = optional(string, "fslogix-profiles")
    }))
  }))
  validation {
    condition     = length(var.regions) > 0
    error_message = "regions must contain at least one workload region."
  }
}

variable "nerdio_install" {
  description = <<-EOT
    How Nerdio Manager gets installed:
    "terraform"   (default) builds it in Terraform (modules/nerdio-core) and deploys the app code
                  from an Automation job, so there's no install script to run.
    "marketplace" deploys Nerdio Manager from the Azure Marketplace (either directly in the Azure
                  portal with nerdio_template_file = null, or from an exported ARM template when
                  nerdio_template_file is set), discovers its resources in the nerdio resource
                  group, and runs Nerdio's install script.
  EOT
  type        = string
  default     = "terraform"
  validation {
    condition     = contains(["terraform", "marketplace"], var.nerdio_install)
    error_message = "nerdio_install must be \"terraform\" or \"marketplace\"."
  }
  validation {
    condition     = var.nerdio_install == "marketplace" || var.create_entra_app
    error_message = "The terraform install builds the Entra app itself, so it needs create_entra_app = true."
  }
}

variable "nerdio_core" {
  description = "Settings for the terraform install (see modules/nerdio-core)."
  type = object({
    package_version          = optional(string, "latest")
    app_service_plan_sku     = optional(string, "B3")
    database_sku             = optional(string, "S1")
    name_suffix              = optional(string)
    purge_protection_enabled = optional(bool, false)
    enable_staging_slot      = optional(bool, false)
    autoscale = optional(object({
      min_capacity          = optional(number, 1)
      default_capacity      = optional(number, 1)
      max_capacity          = optional(number, 3)
      scale_out_cpu_percent = optional(number, 75)
      scale_in_cpu_percent  = optional(number, 25)
    }))
  })
  default = {}
}

variable "automation_workers" {
  description = "Optional custom Hybrid Runbook Worker VM Scale Set inside the control-plane AVD VNet for private runbooks and scripted actions (null skips)."
  type = object({
    instances         = optional(number, 2)
    vm_size           = optional(string, "Standard_D2s_v5")
    ephemeral_os_disk = optional(bool, false)
    worker_group_name = optional(string, "nerdio-hybrid-workers")
  })
  default = null
}

variable "nerdio_template_file" {
  description = "Marketplace install only: optional path to an exported Nerdio Manager ARM template (for example \"../../../templates/nerdio-manager/template.json\"). Leave null (the default) when deploying Nerdio Manager directly from the Azure portal Marketplace."
  type        = string
  default     = null
}

variable "nerdio_template_parameters" {
  description = "Marketplace install only: parameter values when nerdio_template_file is set."
  type        = any
  default     = {}
}

variable "create_entra_app" {
  description = "Pre-create the nerdio-nmw-app registration in Terraform (Nerdio's \"Use existing AD app\" install path). False leaves it to Nerdio's Marketplace install script; set entra_app.existing_client_id afterwards so Terraform can still create the REST API client app for stage 2."
  type        = bool
  default     = true
}

variable "entra_app" {
  description = "Entra app settings. When create_entra_app is false (Nerdio's Marketplace install script created nerdio-nmw-app), set existing_client_id to that app's client ID so Terraform creates the REST API client app and Key Vault secret hand-off for stage 2."
  type = object({
    display_name           = optional(string, "nerdio-nmw-app")
    existing_client_id     = optional(string)
    owner_object_ids       = optional(list(string), [])
    wvd_admin_object_ids   = optional(list(string), [])
    grant_admin_consent    = optional(bool, false)
    enable_mail_send       = optional(bool, false)
    create_rest_api_client = optional(bool, true)
  })
  default = {}
}

variable "enable_hardening" {
  description = "Add private endpoints and VNet integration for the Nerdio core resources. Turn on in a second apply, once the Marketplace deployment exists."
  type        = bool
  default     = false
}

variable "hardening" {
  description = "Hardening options when enable_hardening is true."
  type = object({
    private_app_service   = optional(bool, false)
    disable_public_access = optional(bool, false)
  })
  default = {}
}

variable "image_gallery" {
  description = "Compute Gallery for Packer-built images. Set to null to skip and use Marketplace images in Nerdio."
  type = object({
    name                      = string
    build_resource_group_name = string
    packer_principal_id       = optional(string)
  })
  default = null
}

variable "nme_secret_store" {
  description = <<-EOT
    How stage 2 gets the Nerdio REST API client secret (decision 0015):
    "key_vault" (default) stage 1 stores it in its own Key Vault, and stage 2 reads it on the fly
                with your az sign-in or GitHub OIDC. Nobody copies or exports it.
    "openbao"   an OpenBao server mints a short-lived secret for each run, so no long-lived one
                exists. Needs the openbao settings.
    "output"    the old hand-off: export NME_CLIENT_SECRET from `terraform output`.
    Without a Terraform-built REST client app (create_entra_app or create_rest_api_client false)
    there's nothing to hand off, and key_vault behaves like output.
  EOT
  type        = string
  default     = "key_vault"
  validation {
    condition     = contains(["key_vault", "openbao", "output"], var.nme_secret_store)
    error_message = "nme_secret_store must be \"key_vault\", \"openbao\" or \"output\"."
  }
  validation {
    condition     = var.nme_secret_store != "openbao" || ((var.create_entra_app || var.entra_app.existing_client_id != null) && var.entra_app.create_rest_api_client)
    error_message = "The openbao hand-off needs (create_entra_app = true or entra_app.existing_client_id) and entra_app.create_rest_api_client = true."
  }
  validation {
    condition     = var.nme_secret_store != "openbao" || var.openbao != null
    error_message = "nme_secret_store = \"openbao\" needs the openbao settings (subnet_cidr and allowed_source_addresses)."
  }
}

variable "nme_secret" {
  description = <<-EOT
    Options for the key_vault hand-off. reader_object_ids are extra users, groups or service
    principals allowed to read the secret (you are always included). github_oidc creates an
    identity that a GitHub Actions job in "owner/name" and its environment can sign in as.
  EOT
  type = object({
    key_vault_name    = optional(string)
    reader_object_ids = optional(list(string), [])
    github_oidc = optional(object({
      repository  = string
      environment = optional(string, "sandbox")
    }))
  })
  default = {}
}

variable "openbao" {
  description = <<-EOT
    The optional OpenBao server for nme_secret_store = "openbao" (modules/openbao). subnet_cidr
    is a free /28 in the control-plane AVD VNet. allowed_source_addresses limits who can reach it:
    CIDRs, or ["Internet"] for Cloud Shell and GitHub-hosted runners. login_object_ids are extra
    users allowed to sign in from Cloud Shell (you are always included).
  EOT
  type = object({
    subnet_cidr              = string
    allowed_source_addresses = list(string)
    login_object_ids         = optional(list(string), [])
    name                     = optional(string)
    key_vault_name           = optional(string)
    credential_ttl           = optional(string, "2h")
    vm_size                  = optional(string, "Standard_B2als_v2")
  })
  default = null
}

variable "deployer_object_id" {
  description = "Object ID of the identity that applies this stage. Leave null in Cloud Shell (it's you). The deploy pipeline sets it to its apply identity, because it plans as a read-only one (decision 0016)."
  type        = string
  default     = null
}
