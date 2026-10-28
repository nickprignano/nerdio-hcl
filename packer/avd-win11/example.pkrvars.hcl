subscription_id      = "00000000-0000-0000-0000-000000000000"
tenant_id            = "00000000-0000-0000-0000-000000000000"
location             = "eastus2"
build_resource_group = "rg-contoso-avd-images-build"

gallery = {
  resource_group   = "rg-contoso-avd-images"
  name             = "gal_contoso_avd"
  image_definition = "win11-avd-m365"
  replica_regions  = ["eastus2"]
}

# Optional: Windows Desktop Optimization Tool profile and per-setting changes (see README.md).
# wdot_profile   = "avd-multisession"
# wdot_overrides = { Services = { SysMain = "Apply" } }

# Optional: Evergreen & VcRedist live vendor installers (see README.md).
# install_vcredist = true
# evergreen_apps   = [{ name = "7zip", install_args = "/S" }]
