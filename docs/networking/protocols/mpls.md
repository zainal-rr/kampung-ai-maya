# MPLS Design Rules and Gotchas

## How Forwarding Actually Works

1. IGP gives every router a route to every PE loopback.
2. LDP assigns a label per IGP prefix and advertises it to neighbors; each router builds
   an LFIB (label in → label out + next hop).
3. For L3VPN, BGP adds a second (VPN) label per customer prefix.
4. Ingress PE pushes [IGP label][VPN label]; core swaps the top label only; the
   penultimate hop pops the top label (PHP, signalled as implicit-null); egress PE uses the
   VPN label to pick the VRF/next-hop.

If you can't explain a problem in terms of which of those four steps failed, gather more
state before changing anything.

## Design Rules

1. **LDP router-id must be a reachable loopback** (`mpls ldp router-id Loopback0 force`).
   LDP sessions form between RIDs; an unreachable RID means discovery works but the
   session never establishes.
2. **Label everything the IGP carries for loopbacks.** The LSP must be end-to-end: every
   hop needs a label for the egress PE's loopback. One unlabelled hop = broken VPN with
   perfect IGP routing. `show mpls forwarding-table <PE-loopback>` hop by hop.
3. **LDP-IGP sync** (`mpls ldp sync` under the IGP) — without it, the IGP converges before
   LDP and traffic blackholes for seconds after link recovery.
4. **LDP session protection** (`mpls ldp session protection`) keeps the session and its
   labels through short link flaps via targeted hellos.
5. **MTU.** Each label = 4 bytes. Core interfaces: `mpls mtu 1508` minimum for two labels,
   in practice set interface MTU 1600+ or jumbo. Symptom of failure: small pings work,
   real traffic (TCP with DF) dies.
6. **Loopback /32s must not be summarized** in the core IGP. Summarizing PE loopbacks
   breaks the label path (label for the summary ≠ label for the /32; FEC mismatch ends the
   LSP at the summarizing router).
7. **New builds: consider SR-MPLS** (segment routing). Removes LDP entirely — labels come
   from the IGP itself (prefix-SIDs), eliminating sync/session problems by design. Same
   data plane, simpler control plane. LDP knowledge remains required for brownfield.

## Gotchas (CCIE-tier)

- **PHP confusion:** seeing one label where you expected two (or "No Label"/"Pop Label" in
  the table) on the second-to-last hop is correct behaviour, not a fault.
- **`mpls ip` must be on every core interface** — a single missing one shows up as a
  one-way LSP. `show mpls interfaces` first.
- **TTL propagation** (`no mpls ip propagate-ttl`) hides the core from customer traceroutes —
  decide policy deliberately; mixed settings give confusing traceroute output.
- **LDP transport vs discovery:** discovery uses UDP 646 multicast, the session is TCP 646
  between RIDs. ACLs/CoPP blocking TCP 646 between loopbacks = "LDP discovered but not up".
- **VRFs don't need MPLS on PE-CE links.** `mpls ip` belongs on core-facing interfaces only;
  putting it on customer links is wrong and occasionally harmful (unexpected label exchange).

## First Commands When Broken

| Symptom | Command |
| --- | --- |
| VPN dead, IGP fine | `show mpls forwarding-table <egress-PE-loopback>` on every hop (find the label hole) |
| LDP not up | `show mpls ldp discovery` (hellos?), `show mpls ldp neighbor` (session?), RID reachability |
| Big packets dropped | `ping mpls ipv4 <PE/32> size 1500 df-bit` / check `show mpls interfaces detail` MTU |
| End-to-end LSP test | `ping mpls ipv4 <PE-loopback>/32`, `traceroute mpls ipv4` |
