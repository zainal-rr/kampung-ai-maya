# Cloud Networking Fundamentals

How the virtual network layer works across AWS (VPC), GCP (VPC), and Azure
(VNet) — the substrate every design sits on. (Device-level routing protocols —
OSPF, BGP on physical routers — live in `docs/networking/`; this doc is the
cloud-side abstraction.)

## The Building Blocks

- **VPC / VNet:** an isolated private address space (RFC1918 CIDR) inside the
  provider. AWS VPCs are regional; GCP VPCs are GLOBAL (subnets are regional);
  Azure VNets are regional. GCP's global VPC is the structural odd one out and
  changes multi-region design.
- **Subnets:** carve the CIDR per AZ/zone and per tier (public vs private).
  Plan CIDR generously up front — re-addressing later is painful. Never overlap
  ranges you may one day need to peer or VPN together.
- **Public vs private:** a "public" subnet routes to an internet gateway;
  private subnets reach out via NAT gateway only. Default posture: everything
  private; expose only the entry tier.
- **Security layers:** stateful instance/NIC-level firewalls (AWS security
  groups, Azure NSGs, GCP firewall rules) + optional stateless subnet ACLs.
  Default-deny inbound; allow narrowly by source.

## Connecting Networks

- **Peering:** private connectivity between two VPCs/VNets. Non-transitive
  almost everywhere — A↔B and B↔C does not give A↔C. Peering meshes do not
  scale past a handful of networks.
- **Hub-and-spoke / transit:** the scalable answer — AWS Transit Gateway,
  Azure Virtual WAN / hub VNet, GCP Network Connectivity Center. Shared
  services (inspection, egress, DNS) live in the hub; workloads in spokes.
- **Hybrid (to on-prem):** site-to-site VPN (fast to set up, internet-borne) or
  dedicated circuits — Direct Connect / Cloud Interconnect / ExpressRoute —
  for bandwidth and consistency. BGP runs the route exchange.
- **Private service access:** reach managed services without the internet —
  VPC endpoints / PrivateLink (AWS), Private Service Connect (GCP), Private
  Endpoints (Azure). Default for production data paths.

## Design Rules Of Thumb

1. CIDR plan first, for the whole org, before the first VPC exists.
2. Default-private: NAT for egress, load balancer or CDN as the only ingress.
3. Hub-and-spoke once you pass ~3 networks or need central inspection.
4. Data to managed services goes over private endpoints, not public IPs.
5. DNS strategy (private zones, resolution across spokes/on-prem) is part of
   the network design, not an afterthought — most hybrid outages are DNS.
