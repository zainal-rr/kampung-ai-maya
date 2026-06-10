# Recipe: Spanning-Tree Hardening (IOS-XE)

## Intent
Make the L2 domain deterministic and loop-resistant: deliberate root placement, fast edge
ports, and guards against rogue switches and unidirectional links.

## Design Context
Mode: Rapid-PVST+ (default-compatible, fine to a few hundred VLANs); MST only when VLAN
count × trunk count gets large. Root placement must match the HSRP active switch per VLAN
(`campus_l3_boundary_hsrp.md`). The guards have distinct jobs: portfast+BPDU guard on
host ports (kill rogue switches), root guard on ports toward access (no one usurps root),
loop guard or Bridge Assurance on trunks (unidirectional failures).

## Prerequisites
- VLAN plan and the HSRP active/standby split per VLAN.

## Topology Assumption
D1/D2 distribution pair (D1 root for odd VLANs, D2 for even), access switches downstream,
host ports on access.

## Configuration

Distribution — mode and deterministic root:

```
spanning-tree mode rapid-pvst
spanning-tree extend system-id
! D1:
spanning-tree vlan 1,11,21,31 priority 4096
spanning-tree vlan 10,20,30 priority 8192
! D2 mirrors: even VLANs 4096, odd VLANs 8192
```

(Priorities, not `root primary` macro — the macro picks a value relative to today's root
and can be out-bid later; explicit 4096/8192 is deterministic.)

Distribution ports toward access — root guard:

```
interface range TenGigabitEthernet1/0/1 - 24
 spanning-tree guard root
```

Access switch — global edge defaults + guards:

```
spanning-tree mode rapid-pvst
spanning-tree portfast edge default
spanning-tree portfast edge bpduguard default
errdisable recovery cause bpduguard
errdisable recovery interval 300
```

Access host ports (explicit, beats relying on globals):

```
interface range GigabitEthernet1/0/1 - 44
 switchport mode access
 switchport access vlan 10
 spanning-tree portfast edge
 spanning-tree bpduguard enable
```

Access uplinks (trunks) — loop guard + UDLD:

```
udld enable
!
interface range TenGigabitEthernet1/0/47 - 48
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
 spanning-tree guard loop
 udld port aggressive
```

Never enable portfast/BPDU guard on trunks; never put root guard on upstream-facing ports
(it would block your real root).

## Verification

```
show spanning-tree summary               ! mode, portfast/bpduguard defaults, root counts
show spanning-tree vlan 10               ! root = D1? port roles as designed?
show spanning-tree interface Te1/0/47 detail   ! loop guard active
show udld neighbors                      ! bidirectional state
show interfaces status err-disabled      ! BPDU guard victims
! Live test: plug a switch into a host port -> port must err-disable
```

Root check per VLAN must match the HSRP plan exactly.

## Rollback

```
interface GigabitEthernet1/0/5
 no spanning-tree bpduguard enable
 no spanning-tree portfast edge
no spanning-tree portfast edge bpduguard default
spanning-tree vlan 10 priority 32768
```

Re-enable an err-disabled port: `shutdown` / `no shutdown` after removing the offender.

## Failure Modes

| Break | First command |
| --- | --- |
| Port err-disabled | `show interfaces status err-disabled`, `show errdisable recovery` — BPDU guard did its job; find what was plugged in |
| Root is an access switch (default priorities) | `show spanning-tree vlan X root` — fix priorities as above |
| Loop guard blocks a healthy port | `%SPANTREE-2-LOOPGUARD_BLOCK` — upstream stopped sending BPDUs; investigate upstream, not the guard |
| Unidirectional fiber loops the network | UDLD aggressive missing on the trunk; `show udld <int>` |
| Convergence slow despite RPVST+ | non-edge ports flapping through proposals: check `show spanning-tree interface X detail` for link-type point-to-point on trunks |
