resource "azurerm_subnet" "this" {
  name                 = local.names.subnet
  resource_group_name  = var.virtual_network.resource_group_name
  virtual_network_name = var.virtual_network.name
  address_prefixes     = [var.subnet_cidr]
}

# Only HTTPS on 8200 is open, and only from allowed_source_addresses. No SSH rule: Azure's
# default rules deny other inbound traffic from the internet.
resource "azurerm_network_security_group" "this" {
  name                = local.names.nsg
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# One rule per source, because service tags such as "Internet" only work as a single prefix.
resource "azurerm_network_security_rule" "https" {
  for_each                    = { for i, source in var.allowed_source_addresses : source => 100 + i }
  name                        = "allow-openbao-https-${each.value}"
  priority                    = each.value
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "8200"
  source_address_prefix       = each.key
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.this.name
}

resource "azurerm_subnet_network_security_group_association" "this" {
  subnet_id                 = azurerm_subnet.this.id
  network_security_group_id = azurerm_network_security_group.this.id
}

resource "azurerm_public_ip" "this" {
  name                = local.names.public_ip
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = var.name
  tags                = var.tags
}

resource "azurerm_network_interface" "this" {
  name                = local.names.nic
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = azurerm_subnet.this.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.this.id
  }
}
