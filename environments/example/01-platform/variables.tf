variable "tenant_id" {
  description = "Entra tenant that hosts Nerdio Manager. Pinning it stops a stray az login from deploying into the wrong tenant."
  type        = string
}

variable "subscription_id" {
  description = "Subscription that hosts Nerdio Manager and AVD."
  type        = string
}

variable "prefix" {
  description = "Short naming prefix, e.g. \"contoso-nme\"."
  type        = string
}

variable "location" {
  description = "Azure region close to the admin team and the primary AVD users."
  type        = string
  default     = "eastus2"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "resource_groups" {
  description = "Resource group names keyed by role (nerdio, network, hostpools, storage, monitoring)."
  type        = map(string)
}

variable "network" {
  description = "AVD spoke network settings."
  type = object({
    address_space = list(string)
    subnets = object({
      session_hosts     = string
      private_endpoints = string
      app_integration   = string
    })
    dns_servers         = optional(list(string), [])
    hub_vnet_id         = optional(string)
    use_remote_gateways = optional(bool, false)
    create_nat_gateway  = optional(bool, true)
  })
}

variable "fslogix" {
  description = "FSLogix profile storage. Set to null to skip."
  type = object({
    storage_account_name   = string
    share_quota_gb         = optional(number, 1024)
    identity_source        = optional(string, "AADKERB")
    user_group_object_ids  = optional(list(string), [])
    admin_group_object_ids = optional(list(string), [])
  })
  default = null
}

variable "nerdio_install" {
  description = <<-EOT
    How Nerdio Manager gets installed:
    "terraform"   (default) builds it in Terraform (modules/nerdio-core) and deploys the app code
                  from an Automation job, so there's no install script to run.
    "marketplace" deploys an exported Marketplace template, then you run Nerdio's install script.
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
    package_version      = optional(string, "latest")
    app_service_plan_sku = optional(string, "B3")
    database_sku         = optional(string, "S1")
    name_suffix          = optional(string)
  })
  default = {}
}

variable "nerdio_template_file" {
  description = "Marketplace install only: path to the exported Nerdio Manager ARM template."
  type        = string
  default     = "../../../templates/nerdio-manager/template.json"
}

variable "nerdio_template_parameters" {
  description = "Marketplace install only: parameter values for the exported template."
  type        = any
  default     = {}
}

variable "create_entra_app" {
  description = "Pre-create the nerdio-nmw-app registration in Terraform (Nerdio's \"Use existing AD app\" install path). False leaves it to Nerdio's install script."
  type        = bool
  default     = true
}

variable "entra_app" {
  description = "Entra app settings when create_entra_app is true."
  type = object({
    display_name           = optional(string, "nerdio-nmw-app")
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
    condition     = var.nme_secret_store != "openbao" || (var.create_entra_app && var.entra_app.create_rest_api_client)
    error_message = "The openbao hand-off needs create_entra_app = true and entra_app.create_rest_api_client = true."
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
    is a free /28 in the AVD VNet. allowed_source_addresses limits who can reach it: CIDRs, or
    ["Internet"] for Cloud Shell and GitHub-hosted runners. login_object_ids are extra users
    allowed to sign in from Cloud Shell (you are always included).
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
