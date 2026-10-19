---
title: "AVD Hybrid and Nerdio Manager"
summary: "Azure Virtual Desktop Hybrid (on-premises session hosts via Azure Arc): support status, what Nerdio Manager adds on Nutanix AHV, and the minimum viable lab kit and hardware to test it"
topic: nerdio
status: partial
last_reviewed: 2026-10-19
---

# AVD Hybrid and Nerdio Manager

Shared from the AVD project's lab research (2026-10-19). The Nerdio Manager section is the part
specific to this kit; the rest is the general AVD Hybrid picture it depends on. AVD platform facts
belong to the AVD knowledge base ([family.yaml](../family.yaml)); when that KB is linked, point the
general sections there instead of keeping a copy.

Research only, checked against Microsoft Learn, Nerdio and vendor pages on 2026-10-19. Nothing was deployed, bought or changed. Azure prices are pay-as-you-go list prices for northcentralus and are estimates; hardware prices are as listed on 2026-10-19 unless dated otherwise.

## The short answer

You don't need VMware or Nutanix to test AVD Hybrid itself. Microsoft's integration lives entirely inside the guest: the Azure Arc agent plus the "Azure Virtual Desktop Hybrid" extension on a Windows VM. The hypervisor underneath is invisible to it. VMware or Nutanix only matter when you want to test what Microsoft leaves out: provisioning, image conversion and power management against their APIs.

So the kit is:

| | Kit | What it proves | Cost |
|---|---|---|---|
| **Primary** | Nested Hyper-V inside one Azure VM (D8s_v5), with a lab DC and two on-prem-style session hosts | The real AVD Hybrid flow end to end: Arc onboarding, the extension, AD DS or hybrid join, FSLogix on an on-prem share, image import, Windows App sign-in | About **$3.50 per 4-hour session**, plus about $10 for one Hybrid user license for a month. Roughly **$25-30** for three sessions. |
| **Cheaper fallback** | One small Azure VM made to look on-prem using Microsoft's Arc evaluation steps | Arc onboarding, the extension, host pool registration, the host showing Available | About **$0.20/hour** (D2s_v5) plus the user license. Under **$15** total. |
| **Hardware, only when you need a real host** | NUC-style: Beelink SER9 Max 64 GB (Hyper-V/ESXi), or a 96 GB mini PC (GTi15 Ultra or MS-A2) if Nutanix or Nerdio is in scope (see "Hardware builds for you") | Running the lab at home with no hourly bill, hypervisor-API automation, and Nerdio Manager's AVD Hybrid on Nutanix | About **$1,400** (64 GB) or **$2,080-2,400** (96 GB) one time. A refurbished 128 GB workstation is about $1,640 if size doesn't matter. |

Everything in the "free first" section below should happen before any of these.

**If the goal includes Nerdio Manager:** its AVD Hybrid support is documented for Nutanix AHV only, needs Prism Central and AOS 7.3 / AHV 10.3, needs a VPN from Azure to Prism, and refuses session hosts on any cloud. So the Azure-only kits above can't test it; only the hardware path can, and even that is at risk on Nutanix Community Edition. Details in "Nerdio Manager and AVD Hybrid".

## What is GA, preview or unsupported (as of 2026-10-19)

| Item | Status | Source |
|---|---|---|
| AVD Hybrid (session hosts on any hypervisor or physical Windows Server, via Arc) | **GA, September 2026.** Public preview was May 2026, limited preview November 2025. | [What's new](https://learn.microsoft.com/en-us/azure/virtual-desktop/whats-new), [Hybrid overview](https://learn.microsoft.com/en-us/azure/virtual-desktop/hybrid-overview), [GA blog](https://techcommunity.microsoft.com/blog/azurevirtualdesktopblog/microsoft-azure-virtual-desktop-hybrid-is-now-generally-available/4550523) |
| Platforms named for Hybrid | Hyper-V, VMware vSphere, Nutanix AHV, physical Windows Server, "anywhere Arc-enabled servers can be deployed" | Same, and [Nutanix GA note, 2026-09-14](https://www.intelligentcio.com/me/?p=139350) |
| Hybrid OS: Windows Server 2016-2025 | Supported (VMs and headless physical servers) | [Hybrid overview](https://learn.microsoft.com/en-us/azure/virtual-desktop/hybrid-overview) |
| Hybrid OS: Windows 10/11 Enterprise single-session | Supported (VMs; physical only as dedicated headless hosts) | Same |
| Hybrid OS: Windows 10/11 Enterprise **multi-session** | **Not supported** on Hybrid. Azure and Azure Local only. | Same |
| Hybrid identity | Windows client hosts: Entra join, AD DS join or hybrid join. Windows Server hosts: AD DS or hybrid join only (RDS licensing dependency). | [Deploy AVD Hybrid](https://learn.microsoft.com/en-us/azure/virtual-desktop/deploy-azure-virtual-desktop-hybrid) |
| Hybrid: autoscale, Start VM on Connect, power management, session host configuration | **Not supported.** You provision and power hosts yourself. | [Hybrid overview](https://learn.microsoft.com/en-us/azure/virtual-desktop/hybrid-overview) |
| AVD on Azure Local | GA (Azure Government is preview). Multi-session supported. Billed per active vCPU plus the Azure Local per-core fee. Cannot mix Azure and Azure Local hosts in one pool. | [AVD on Azure Local](https://learn.microsoft.com/en-us/azure/virtual-desktop/azure-local-overview) |
| Azure Local virtual (nested) deployment | Exists, "for educational and demonstration purposes only", not supported by Microsoft Support | [Virtual deployment](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-virtual?view=azloc-2609) |
| Arc-enabled VMware vSphere (resource bridge) | GA; needs **vCenter 8**; bridge VM is 4 vCPU / 8 GB. **Not required** for AVD Hybrid, which only needs the guest Arc agent. | [Support matrix](https://learn.microsoft.com/en-us/azure/azure-arc/vmware-vsphere/support-matrix-for-arc-enabled-vmware-vsphere) |
| Arc agent on an Azure VM | Evaluation and testing only, never production | [Evaluate Arc on an Azure VM](https://learn.microsoft.com/en-us/azure/azure-arc/servers/plan-evaluate-on-azure-virtual-machine) |
| FSLogix for cloud-only and external identities | GA, May 2026 | [What's new](https://learn.microsoft.com/en-us/azure/virtual-desktop/whats-new) |
| App Attach on Windows Server 2022/2025, including Hybrid | Available, April 2026 | Same |
| Image Builder output as VHD (for export on-prem) | Supported distribution target | [Image Builder overview](https://learn.microsoft.com/en-us/azure/virtual-machines/image-builder-overview) |

Not documented anywhere I found: RDP Shortpath behavior on Hybrid hosts, and whether the Hybrid extension accepts an Azure VM onboarded with the Arc evaluation workaround. Both are things the lab would answer.

## What each scenario really needs

| Scenario | Testable how | Needs VMware/Nutanix? |
|---|---|---|
| Hybrid session hosts (Server and Win11 single-session) | Primary kit | No |
| Arc onboarding at scale (service principal, scripted) | Primary or fallback | No |
| Hybrid join vs Entra join | Primary kit (lab DC + Entra Connect Cloud Sync for one test user; Win11 can be Entra-only) | No |
| FSLogix on an on-prem SMB share | Primary kit (share on the lab DC or a small file server VM) | No |
| Image pipeline: build in Azure, run on-prem | Image Builder VHD output, imported into Hyper-V in the primary kit | Only to test VMDK (vSphere) or AHV conversion |
| Provisioning and power management (Microsoft's gap) | Your own scripts against the hypervisor API | **Yes.** Free ESXi's API is effectively read-only, so you need vCenter or Prism. |
| Azure Local + AVD | Certified hardware, or nested Azure Local (48 GB+ host RAM, 1 TB SSD) | No, but see skip list |
| Liquidware tier on on-prem hosts | Same primary kit later, if you want it | No |

## Primary kit in detail: nested Hyper-V in one Azure VM

- **Host:** Standard_D8s_v5 (8 vCPU, 32 GB, nested virtualization supported per the [Dsv5 page](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dsv5-series)), Windows Server 2025 Datacenter, Hyper-V role, NAT switch. $0.752/hour in northcentralus.
- **Guests:** DC + file share (2 vCPU / 4 GB), Windows Server 2025 session host (2 vCPU / 8 GB), Windows 11 Enterprise session host (2 vCPU / 8 GB), leaving about 8 GB for the host. Step up to D16s_v5 ($1.504/hour, 64 GB) only if you add more hosts.
- **Guest OS media:** evaluation ISOs from the [Microsoft Evaluation Center](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise) (Windows 11 Enterprise 90 days, Windows Server 180 days). For a Server session host, RDS licensing runs on its built-in grace period during the lab.
- **Gotcha to plan for (inferred, verify):** NAT traffic from the guests leaves through the Azure VM, so the Arc installer in a guest may reach Azure IMDS (169.254.169.254) and refuse, thinking it is on an Azure VM. Block that address for the NAT subnet on the host.
- **Azure side, all free:** host pool (standard, with managed identity), Reader for the host pool identity on the Arc resource group, workspace, app group. Arc agent and basic Arc servers are free.
- **Cost per 4-hour session:** VM about $3.00, disks and public IP about $0.40 (estimate). Delete the resource group at the end of each session, or keep only the disk if you want to resume.
- **License:** each user needs an OS entitlement plus the AVD Hybrid user license. A reseller lists it at $10/user/month month-to-month ([o365hq, not a Microsoft page](https://o365hq.com/subscriptions/azure-virtual-desktop-hybrid)); it mentions a trial SKU but gives no terms. Microsoft's pricing page shows no number yet. The Win11 host also needs a Microsoft 365 E3/E5/Business Premium or Windows Enterprise license for the test user, so if you don't have one, test with the Windows Server host only (RDS CAL route).
- **Touches your tenant:** Cloud Sync for one lab user and the AVD resources. Both are removed by the cleanup.

## Cheaper fallback: Arc evaluation on one Azure VM

One D2s_v5 Windows Server VM (about $0.19/hour), with Microsoft's documented evaluation steps: set `MSFT_ARC_TEST`, remove extensions, disable the guest agent, block IMDS, then onboard with the Arc script ([steps](https://learn.microsoft.com/en-us/azure/azure-arc/servers/plan-evaluate-on-azure-virtual-machine)). Then add the Hybrid extension and check the host goes Available. It proves the Arc and registration path and nothing about real on-prem networking, join types or images, and it may simply fail if the extension rejects an Azure VM. Use it for a quick smoke test of automation scripts.

## Hypervisor software for a real host

Only for provisioning or image-conversion automation, or for Nerdio Manager.

- **Nutanix:** Community Edition 2.1 is free and ships AOS 6.8.1. Roughly 4+ cores with VT-x/AMD-V, 32 GB RAM, about 200 GB SSD across boot, CVM and data drives ([install guide](https://techygeekshome.info/installing-nutanix-community-edition/)). Community members report LCM upgrades to AOS 7.0.x, but also failed AHV 10.3 upgrades and advice not to go to AHV 10.3+ on CE ([Nutanix community thread](https://next.nutanix.com/installation-configuration-23/where-to-download-nutanix-community-edition-ce-v7-1-or-newer-e-g-v7-3-45060)). Prism gives you a real API.
- **VMware:** free ESXi 8.0 U3e is back since April 2025, but it can't join vCenter and its API is effectively read-only ([summary](https://www.gigenet.com/blog/what-is-vmware-esxi-2026/)), so it can host session hosts but not test automation. Automation needs vCenter, which means the vSphere evaluation or VMUG Advantage, and VMUG home lab licenses now require passing a VCP exam ([VMware guide](https://blogs.vmware.com/code/2025/03/19/vmug-advantage-home-lab-license-guide/)).
- **Hyper-V:** Windows Server 2025 evaluation (180 days) on the same box costs nothing and runs the primary kit's design at home with no hourly Azure bill.

## Hardware builds for you

**The thing that decides everything right now is RAM.** New DDR5 prices are extreme in October 2026: the Crucial 128 GB DDR5 SODIMM kit is $2,099 at [Best Buy](https://www.bestbuy.com/product/crucial-128gb-kit-2x64gb-ddr5-5600mhz-c46-sodimm-laptop-memory-black/JX8PSKCPWR) and $2,340 on Amazon per [pricehistory.app](https://pricehistory.app/p/crucial-128gb-kit-2x64gb-ddr5-ram-5600mhz-UtfnchQ2) (its low was $279.99), and the cheapest 64 GB DDR5 desktop kit is $814.99 on Amazon per [pgrid](https://www.pgrid.app/us/advice/compare-64gb-ddr5-ram). Refurbished DDR4 ECC server memory is far cheaper, about $160-235 per 32 GB in June 2026 ([PCSP](https://pcserverandparts.com/news/refurbished-ddr4-server-memory-2026-server-ram-price-crisis/)). So the minimum viable box is a used DDR4 workstation that already has its RAM, not a new mini PC.

**How much RAM:** Hyper-V or ESXi with a DC and two session hosts fits in 64 GB. Nutanix CE adds a controller VM (about 20-32 GB) and Nerdio's AHV path needs Prism Central on top, so plan **128 GB** if Nutanix or Nerdio is in scope.

**About Amazon:** Amazon blocks automated page reads, so I couldn't open listings directly. Amazon prices below come through review and price-tracker sites that link to the Amazon listing (dated October 2026); confirm on the listing before buying.

You asked for a NUC-style mini PC, so those come first. The catch is that a mini PC with enough RAM costs more than a used workstation right now, because the RAM is the expensive part.

### Mini PC 1 (recommended): Beelink SER9 Max, 64 GB / 1 TB

| | |
|---|---|
| Price | **$1,149** on Amazon, per [smarthomecompared](https://smarthomecompared.com/mini-pcs/beelink-ser9-max-64gb-1tb) (updated October 2026). [Amazon search](https://www.amazon.com/beelink-ser9/s?k=beelink+ser9) |
| CPU | AMD Ryzen 7 H 255, 8 cores / 16 threads. AMD's cores are all the same type, which avoids the ESXi trouble Intel's mixed P/E cores cause. |
| RAM | 64 GB DDR5 in two SO-DIMM slots (not soldered), 128 GB max later |
| Storage | 1 TB installed, second M.2 2280 PCIe 4.0 slot free |
| Network | 10GbE (chip not named on the spec pages, so check ESXi driver support before choosing ESXi) |
| Add | Crucial P310 2 TB NVMe for the free slot, **$251** on Amazon per [cheapestssd.vip](https://cheapestssd.vip/) (2026-10-19) |
| **Total** | **about $1,400 plus tax** |

- Covers: Hyper-V with Windows Server eval (the primary kit's design at home, no hourly Azure bill), or ESXi with a DC and two or three session hosts.
- Doesn't cover: Nutanix CE plus Prism Central, so it can't test Nerdio's AVD Hybrid path. Upgrading to 128 GB later means buying 2x64 GB DDR5 SO-DIMMs, which cost about $2,100-2,340 today, so treat 64 GB as final unless prices fall.

### Mini PC 2 (if Nutanix or Nerdio is in scope): 96 GB

| Option | Price | Notes |
|---|---|---|
| **Beelink GTi15 Ultra**, Intel Core Ultra 9 285H, **96 GB** DDR5 SO-DIMM, 2 TB, dual Intel 10GbE | **$2,399**, Amazon-linked, per [smarthomecompared](https://smarthomecompared.com/mini-pcs/beelink-gti15-ultra-96gb-2tb). [Amazon listing](https://www.amazon.com/Beelink-GTi15-Mini-Intel-Ultra/dp/B0FW4KG9GW) | Available on Amazon now. Two M.2 slots, both filled in this bundle. 128 GB possible with 64 GB modules ([ServeTheHome](https://www.servethehome.com/beelink-gti15-ultra-review-a-dual-10gbe-mini-pc-with-a-pcie-gpu-dock-option-intel-amd/2/)). Intel's mixed P/E cores need workarounds on ESXi; fine for Hyper-V. |
| **Minisforum MS-A2**, Ryzen 9, **96 GB**, 2 TB, two Intel X710 10G SFP+ + Intel i226 | **$2,079** sale at the [Minisforum store](https://store.minisforum.com/products/minisforum-ms-a2-workstation), out of stock, shipping estimated mid-November | $320 cheaper and AMD (ESXi 8.0.3 installs unmodified per [sdn-warrior](https://sdn-warrior.org/posts/ms-a2/)). Three M.2 slots, which suits Nutanix CE's three drives. The Realtek port has no ESXi driver. Not sold through Amazon in the listing I found. |

- Pick the **MS-A2 if you can wait** for stock; the **GTi15 Ultra if you want it from Amazon now**.
- 96 GB fits Nutanix CE's controller VM, a small Prism Central and a couple of session hosts, but it's tight. Nutanix CE also expects separate boot, CVM and data drives; with two M.2 slots (GTi15) the usual community workaround is booting the hypervisor from a USB SSD, which I haven't verified.

### Skip: 128 GB "AI" mini PCs

The Ryzen AI Max+ 395 boxes (GMKtec EVO-X2, Beelink GTR9 Pro, Minisforum MS-S1 Max) have 128 GB but cost **$3,500-4,349** on Amazon as of 2026-10-10 ([comparison](https://computingforgeeks.com/ryzen-ai-max-395-mini-pc-comparison/)), the RAM is soldered, and most use Realtek NICs that ESXi doesn't support. Buyers also report the GTR9 Pro's 10GbE ports dropping under load ([starryhope](https://www.starryhope.com/minipcs/models/beelink-gtr9-pro/)).

### Best value if size and noise don't matter: refurbished Lenovo ThinkStation P520, 128 GB

| Part | Pick | Price | Source |
|---|---|---|---|
| Workstation | ThinkStation P520, Xeon W-2133 (6 cores / 12 threads), **128 GB DDR4 ECC**, 1 TB NVMe, Quadro K620, Windows 11, 1-year warranty | $1,218.94 (63 in stock today) | [PCSP P520 page](https://pcserverandparts.com/workstations/lenovo-workstations/lenovo-p520-thinkstation/) |
| Data drive | Crucial P310 2 TB NVMe | $251 | Amazon, via [cheapestssd.vip](https://cheapestssd.vip/) |
| Third drive for Nutanix CE | WD Blue SN5100 1 TB NVMe, or any small SATA SSD | $167 | Amazon, via [cheapestssd.vip](https://cheapestssd.vip/) |
| **Total** | | **about $1,640 plus tax** | |

- Twice the RAM of Mini PC 2 for about $750 less, and it runs Hyper-V, ESXi or Nutanix CE by swapping boot drives. The trade-off is a tower's size, noise and power draw.
- Check before buying (not verified here): M.2 slot and SATA bay count on the P520 board, and the Broadcom compatibility guide for the Xeon W-2100 CPU and onboard Intel NIC on ESXi 8.
- Cheaper still: the P520c with **64 GB** is **$785.50** at the same seller, with the same 64 GB limits as Mini PC 1.

### What not to buy

New DDR5 RAM on its own, Azure Local certified hardware (the skip list explains why), or a second node. One box is enough for every scenario here.

## Nerdio Manager and AVD Hybrid

Nerdio Manager for Enterprise (NME) 8.2, released September 2026, made its AVD Hybrid support generally available ([Nerdio blog](https://getnerdio.com/blog/nerdio-manager-now-supports-microsoft-azure-virtual-desktop-hybrid-one-platform-for-every-windows-cloud-deployment/)).

| Item | What Nerdio documents | Source |
|---|---|---|
| Hypervisors | **Nutanix AHV** (Prism Element or Prism Central). Nerdio's marketing page also lists VMware vSphere, but there is no help article for it and the 8.2 announcement names only Nutanix, so treat VMware as unconfirmed. No Hyper-V, no physical hosts. | [AVD Hybrid Support](https://nmehelp.getnerdio.com/hc/en-us/articles/45272022792461-AVD-Hybrid-Support), [Nerdio AVD Hybrid page](https://getnerdio.com/avd-hybrid/) |
| What NME adds over plain AVD Hybrid | Provisions session hosts from generalized (sysprepped) Prism Central templates, runs the Arc onboarding script during the unattended specialize pass, domain-joins, creates the host pool's managed identity and grants it Reader, sizes and places VMs, and manages images and updates. It mentions power management but documents no details; autoscale isn't mentioned. | [AVD Hybrid on Nutanix AHV](https://nmehelp.getnerdio.com/hc/en-us/articles/45272005917197-AVD-Hybrid-on-Nutanix-AHV) |
| Tested minimum versions | Nutanix API v4.1, **AOS 7.3, AHV 10.3, Prism Central pc.7.3** | Same |
| Credentials | Prism Central service account (Prism Admin, full scope) with an API key; an Entra app registration with a client secret holding **Azure Connected Machine Onboarding** on the Arc resource group; User Access Administrator or Owner to grant the Reader role; NME Admin role | Same |
| Network | NME (running in Azure) must reach Prism on **TCP 9440 over VPN or ExpressRoute**. Public internet access to Prism isn't supported. Session hosts need outbound access to the AVD and Arc endpoints. | Same |
| Identity | Session hosts must be domain-joined before the Arc extension installs; a domain controller synced to Entra is required | Both help articles |
| OS | Windows Server (VM and physical), Windows 11 Enterprise single-session (VM only); no multi-session | [AVD Hybrid Support](https://nmehelp.getnerdio.com/hc/en-us/articles/45272022792461-AVD-Hybrid-Support) |
| Hard limit | **Session hosts on any cloud provider (Azure, AWS, GCP, Alibaba) are not supported**, so nested hypervisors inside Azure can't stand in | Same |
| Known issue | Guest Reboot or Shutdown commands on AHV may fail silently | [AVD Hybrid on Nutanix AHV](https://nmehelp.getnerdio.com/hc/en-us/articles/45272005917197-AVD-Hybrid-on-Nutanix-AHV) |

What this means for your lab:

- **Only the hardware path can test NME's AVD Hybrid**, and only with Nutanix (Mini PC 2 at 96 GB, or the 128 GB workstation).
- **Nutanix CE is the weak link.** NME's tested minimum is AOS 7.3 / AHV 10.3, CE 2.1 ships AOS 6.8.1, and the community reports failed upgrades to AHV 10.3 and advises against it. Whether Prism Central runs on CE at those versions is unconfirmed. Plan for the chance that NME's Nutanix flow won't work on CE at all; if a real Nutanix cluster is ever reachable through work or a partner lab, that's the reliable route.
- **You need a site-to-site VPN from home to Azure** for NME to reach Prism: an Azure VPN Gateway plus a home router or firewall that does IPsec. The VpnGw1 SKU is about $0.19/hour from memory (Microsoft's pricing page wouldn't load for northcentralus, so price it in the calculator first).
- **NME's own Azure footprint** is about $248/month list (App Service B3 $219, SQL S1 $29) per [Nerdio](https://nmehelp.getnerdio.com/hc/en-us/articles/26124345260941-Nerdio-Manager-Default-Deployment-Resources-and-Costs), about $0.34/hour. Deploy it for the test window and remove it after. Nerdio offers a free trial; I couldn't load its terms.
- **Rough cost of one 8-hour NME hybrid test day:** NME about $2.70 plus VPN gateway about $1.50, so about $4-5 in Azure, plus the AVD Hybrid user license, after the one-time hardware.
- **For nerdio-hcl:** the client secret on the app registration conflicts with that kit's "no long-lived secrets where an identity works" guardrail. Note it as an accepted risk or an upstream ask, not something to automate around.

## Skip list

- **Azure Local.** Needs certified hardware with 32 GB ECC per node, or a nested host with 48 GB+ RAM and 1 TB SSD. After a 60-day trial it bills per physical core, and AVD bills per active vCPU on top. The Jumpstart LocalBox sandbox runs on a large E-series VM (E32-class is about $3.50/hour on Windows, estimate). Only worth it if a customer runs Azure Local.
- **Arc-enabled VMware vSphere (resource bridge).** Needs vCenter 8 and isn't required for AVD Hybrid.
- **Windows 11 multi-session on Hybrid.** Unsupported.
- **Testing autoscale, Start VM on Connect or session host configuration on Hybrid.** Unsupported. That gap is your own automation's job.
- **Free ESXi for automation work.** Read-only API.
- **Cloud bare-metal hypervisor services** (Azure VMware Solution, Nutanix on Azure). Bare-metal pricing is far beyond a personal sandbox.

## Free first, before any spend

1. Check D-series quota in your region (`az vm list-usage -l <region>`), and any region-restriction policy on the sandbox subscription.
2. Write the Azure side (host pool with managed identity, Reader role assignment, workspace, app group) as Bicep and run `what-if`. No cost.
3. Script the Arc onboarding and extension deployment, and test it offline with Pester fixtures, the way the Liquidware tier does.
4. Confirm the Hybrid license trial terms in the Microsoft 365 admin center before buying a seat.
5. Then run the primary kit once, with a written estimate, `Cleanup` right after and teardown evidence.

## Sources

- [Azure Virtual Desktop Hybrid overview](https://learn.microsoft.com/en-us/azure/virtual-desktop/hybrid-overview)
- [Deploy Azure Virtual Desktop Hybrid](https://learn.microsoft.com/en-us/azure/virtual-desktop/deploy-azure-virtual-desktop-hybrid)
- [Troubleshoot Azure Virtual Desktop Hybrid](https://learn.microsoft.com/en-us/azure/virtual-desktop/troubleshoot-azure-virtual-desktop-hybrid)
- [What's new in Azure Virtual Desktop](https://learn.microsoft.com/en-us/azure/virtual-desktop/whats-new)
- [Azure Virtual Desktop on Azure Local](https://learn.microsoft.com/en-us/azure/virtual-desktop/azure-local-overview)
- [Azure Local virtual deployment](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-virtual?view=azloc-2609)
- [Azure Local system requirements](https://learn.microsoft.com/en-us/azure/azure-local/concepts/system-requirements-small-23h2?view=azloc-2601)
- [Azure Local billing](https://learn.microsoft.com/en-us/azure/azure-local/concepts/billing?view=azloc-2609)
- [Arc-enabled VMware vSphere support matrix](https://learn.microsoft.com/en-us/azure/azure-arc/vmware-vsphere/support-matrix-for-arc-enabled-vmware-vsphere)
- [Evaluate Arc-enabled servers on an Azure VM](https://learn.microsoft.com/en-us/azure/azure-arc/servers/plan-evaluate-on-azure-virtual-machine)
- [Dsv5 sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dsv5-series)
- [Image Builder overview](https://learn.microsoft.com/en-us/azure/virtual-machines/image-builder-overview)
- [Azure Virtual Desktop pricing](https://azure.microsoft.com/en-us/pricing/details/virtual-desktop/)
- VM prices: [cloudprice.net D8s_v5](https://cloudprice.net/vm/Standard_D8s_v5), [azurespeed E32s_v5](https://www.azurespeed.com/AzureVmPricing/Standard_E32s_v5)
- [Nutanix AVD Hybrid GA note](https://www.intelligentcio.com/me/?p=139350)
- [Free ESXi in 2026](https://www.gigenet.com/blog/what-is-vmware-esxi-2026/), [VMUG Advantage home lab license guide](https://blogs.vmware.com/code/2025/03/19/vmug-advantage-home-lab-license-guide/)
- Nerdio: [AVD Hybrid Support](https://nmehelp.getnerdio.com/hc/en-us/articles/45272022792461-AVD-Hybrid-Support), [AVD Hybrid on Nutanix AHV](https://nmehelp.getnerdio.com/hc/en-us/articles/45272005917197-AVD-Hybrid-on-Nutanix-AHV), [NME 8.2 announcement](https://getnerdio.com/blog/nerdio-manager-now-supports-microsoft-azure-virtual-desktop-hybrid-one-platform-for-every-windows-cloud-deployment/), [default deployment costs](https://nmehelp.getnerdio.com/hc/en-us/articles/26124345260941-Nerdio-Manager-Default-Deployment-Resources-and-Costs)
- Nutanix CE versions: [community thread](https://next.nutanix.com/installation-configuration-23/where-to-download-nutanix-community-edition-ce-v7-1-or-newer-e-g-v7-3-45060)
- Hardware: [Beelink SER9 Max](https://smarthomecompared.com/mini-pcs/beelink-ser9-max-64gb-1tb), [Beelink GTi15 Ultra](https://smarthomecompared.com/mini-pcs/beelink-gti15-ultra-96gb-2tb), [GTi15 Ultra on ServeTheHome](https://www.servethehome.com/beelink-gti15-ultra-review-a-dual-10gbe-mini-pc-with-a-pcie-gpu-dock-option-intel-amd/2/), [Minisforum MS-A2](https://store.minisforum.com/products/minisforum-ms-a2-workstation), [MS-A2 ESXi review](https://sdn-warrior.org/posts/ms-a2/), [Ryzen AI Max+ 395 mini PC comparison](https://computingforgeeks.com/ryzen-ai-max-395-mini-pc-comparison/), [Lenovo P520 at PCSP](https://pcserverandparts.com/workstations/lenovo-workstations/lenovo-p520-thinkstation/), [SSD prices](https://cheapestssd.vip/)
- RAM prices: [Best Buy 128 GB SODIMM kit](https://www.bestbuy.com/product/crucial-128gb-kit-2x64gb-ddr5-5600mhz-c46-sodimm-laptop-memory-black/JX8PSKCPWR), [pricehistory.app](https://pricehistory.app/p/crucial-128gb-kit-2x64gb-ddr5-ram-5600mhz-UtfnchQ2), [pgrid 64 GB DDR5](https://www.pgrid.app/us/advice/compare-64gb-ddr5-ram), [PCSP on refurbished DDR4](https://pcserverandparts.com/news/refurbished-ddr4-server-memory-2026-server-ram-price-crisis/)
