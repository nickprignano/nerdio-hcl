# Cloud-specific endpoints for this stage (decision 0034). The default, public, keeps today's
# behavior; usgovernment is for Azure Government, which GCC High tenants use.
locals {
  login_endpoint = {
    public       = "https://login.microsoftonline.com"
    usgovernment = "https://login.microsoftonline.us"
  }[var.cloud]
}

# The nerdio/nme provider signs in against login.microsoftonline.com and doesn't expose a way to
# change it, so it can't get a token from an Azure Government tenant. The restapi gap filler above
# can. Until Nerdio exposes a token URL or cloud setting in the provider, configure Nerdio objects
# in the console (or the restapi stopgap) in Azure Government. See docs/government.md.
check "nme_provider_cloud" {
  assert {
    condition     = var.cloud == "public"
    error_message = "cloud is usgovernment: the nerdio/nme provider can only sign in to the commercial cloud today, so its resources in this stage will fail to authenticate. See docs/government.md."
  }
}
