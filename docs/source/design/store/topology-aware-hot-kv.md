# Topology-Aware Hot KV Replication and Read Selection

This document records the current Mooncake Store hot-KV path and the
topology-aware replication / read strategy that builds on it. It extends
[RFC #1100](https://github.com/kvcache-ai/Mooncake/issues/1100) (dynamic
replica management) and [issue #2516](https://github.com/kvcache-ai/Mooncake/issues/2516)
(topology- and load-aware remote replica selection).

## Why this exists

LLM serving traffic is highly skewed. A small set of prefixes, system prompts,
and popular sessions generate most KV-cache reads. Those hot objects currently
sit on whatever segments `Put` happened to choose. When many decode or prefill
workers miss the local segment, they all RDMA the same remote replica, which:

- inflates tail latency on the hot path
- congests a single NIC / rack uplink
- leaves DRAM on the reader hosts unused

The goal is: **detect heat, place extra MEMORY replicas near the readers that
generate it, and pick the closest healthy replica on every Get.**

## Current progress

Mooncake already has most of the control-plane machinery. Topology is only
partially wired into placement and read selection.

### What already works

| Layer | Mechanism | Status |
|-------|-----------|--------|
| Static multi-replica Put | `ReplicateConfig.replica_num` plus best-effort slice placement on distinct segments | Production |
| Preferred / local-first write | `preferred_segment(s)`, `host_id`, `allocation_strategy=local_first` | Production; `local_first` is `replica_num == 1` only |
| Client-local hot cache | `LocalHotCache` + CountMinSketch admission (`MC_STORE_LOCAL_HOT_*`) | Production; **process-local DRAM**, not a cluster replica |
| SSD promotion-on-hit | Master CountMinSketch; `--promotion_on_hit` copies SSD-only objects back to DRAM | Production; **tier promotion**, not extra MEMORY fanout |
| Dynamic MEMORY fanout | `--dynamic_replication_mode={off,observe,enforce}` | Implemented; default `off` |
| Replica copy two-phase | `DynamicReplicaCopyStart/End/Revoke` leases, worker `FetchTasks` | Implemented |
| Read replica ranking | `SelectBestReplica`: local endpoint MEMORY, then local NOF, then first remote MEMORY | Production |
| Opt-in remote scoring | `SetRemoteReplicaScorer` / `MC_STORE_REPLICA_SCORING=1`; builtin prefers RDMA over TCP | Merged ([#2781](https://github.com/kvcache-ai/Mooncake/pull/2781)); **no topology scorer is injected in production** |
| Transfer-engine locality | TENT `DeviceSelector` (`predicted_time * numa_penalty`); `segmentHost()` for same-host IPC | Production for **NIC pick after a replica is chosen**, not for replica pick |
| Domain fields on proposals | `ReplicaActionProposal.requester_domain` / `target_domain` | **Reserved**; previously rejected with `INVALID_PARAMS` |

### Dynamic replication as implemented

On `GetReplicaList` / `BatchGetReplicaList`, if a key already has at least one
readable MEMORY replica and fewer than
`--dynamic_replication_max_memory_replicas` (default 2), the master records a
hit in a sliding window (`--dynamic_replication_heat_window_seconds`, default
10s). Crossing
`--dynamic_replication_admission_qps_threshold` (default 0.8 QPS) enqueues an
`ADD` proposal.

`SelectDynamicReplicaPlan` then picks:

1. A stable source segment (lowest `hash(key, segment)`).
2. A target segment that is allocatable, under 85% utilization after the copy,
   **on a different `host_id` when possible**, then lowest utilization, then a
   stable hash.

This spreads load across hosts. It does **not** place the extra replica on the
host that is actually reading. `GetReplicaList` does not carry reader identity,
so auto-fanout cannot yet aim at the requester.

`observe` logs the would-propose decision without copying. `enforce` submits
the copy task. Cooldowns (30s action, 60s recreate) limit thrash.

### Read path as implemented

```
Get(key)
  ├─ LocalHotCache hit?  return local DRAM (no network)
  └─ Query master replica list
        └─ SelectBestReplica
              1. MEMORY whose transport_endpoint is an exact local mount
              2. NOF whose transport_endpoint is an exact local mount
              3. first remote MEMORY  (or scored remote MEMORY if opt-in)
              4. remote NOF, LOCAL_DISK, DFS, DISK
```

Exact `transport_endpoint` match is **same process / same mounted segment**,
which enables local memcpy. Two clients on the same host with different ports
are treated as remote, even though the path is intra-host RDMA.

Dummy clients (`global_segment_size=0`) mount nothing, so
`GetLocalEndpoints()` is empty. Locality for those readers is invisible unless
`host_id` is used.

### Gaps this design closes

1. **Reader locality is endpoint-exact, not host/rack/zone-aware.**
2. **Hot replica placement spreads away from existing copies and ignores who
   is reading.**
3. **Heat is global per key**, not per `(key, topology domain)`.
4. **TENT NIC-role / load scores are not composed into replica ranking**
   (explicitly deferred by #2516 after #2781).
5. **Local hot cache, SSD promotion, and cluster MEMORY fanout are three
   independent heat systems** with different thresholds and no shared policy.

## Topology model

Keep the model small and aligned with identifiers Mooncake already stores.

```
zone
  └─ rack
       └─ host_id          (ResolveMooncakeHostId(local_hostname))
            └─ segment     (name + te_endpoint = host:port)
                 └─ NIC / NUMA   (Transfer Engine Topology / TENT)
```

| Attribute | Source today | Used for |
|-----------|--------------|----------|
| `host_id` | Client `local_hostname`; mounted on `Segment.host_id` | write local-first, dynamic replica spread |
| `te_endpoint` | Transfer Engine listen address | exact local memcpy / mount match |
| `protocol` | Replica buffer descriptor | RDMA vs TCP scoring |
| NIC / NUMA matrix | `SegmentDesc.topology` in the metadata server | TENT path pick; not yet replica pick |
| rack / zone | **not in master metadata** | Phase 3 cluster topology map |

**Domain** on a replica-action proposal is a topology key. Phase 1 treats it as
`host_id`. Later phases may pass `rack:<id>` or `zone:<id>` once a cluster map
exists. Unknown or empty domain falls back to the current different-host spread.

Do not invent a second topology database. Rack/zone membership should be a
master config (JSON host inventory) that only labels existing `host_id`s.

## Read strategy

Every Get still asks the master for the replica list. Ranking stays on the
client so it can use local mounts, `host_id`, and (later) TENT scores without
an extra RPC.

### Ranking

Lower rank wins. Scan every COMPLETE replica; master order is only a tie
break.

1. **Local-endpoint MEMORY** — `transport_endpoint` is a locally mounted
   segment. Enables memcpy (`MC_STORE_MEMCPY`).
2. **Same-host MEMORY** — `segmentHost(endpoint)` equals the reader's
   `host_id`, even if the port/process differs. Intra-host RDMA / IPC.
3. **Local-endpoint NOF**, then **same-host NOF**.
4. **Remote MEMORY** — if `MC_STORE_REPLICA_SCORING=1` or a scorer is injected,
   pick the lowest score; otherwise keep master order.
5. **Remote NOF**, then **LOCAL_DISK**, **DFS**, **DISK**.

Same-host MEMORY outranks local NOF: DRAM over the node interconnect is the
hot path, NVMe-oF is the capacity path.

When `host_id` is empty (loopback / unset hostname), step 2 and same-host NOF
are skipped and behavior matches the historical type+locality policy.

### Remote score composition (later phases)

Issue #2516 splits the remote score across layers so store does not depend on
TENT at build time:

```
total_score(replica)
  = local_score     // TENT: inflight/ewma_bw * nic_role_weight + small NUMA term
  + remote_score    // store: rack/zone distance + reported NIC load
  + media_penalty   // MEMORY << NOF << DISK
```

H20 / ConnectX-7 measurements in #2516 showed NIC **role** (head VF vs tail
bonded) dominating PCIe PIX-vs-NODE distance. The NUMA term should stay modest
for network transfers; do not reuse TENT's large cross-socket penalty as a
remote-replica weight.

Until `ReportNicLoadStats` and a TENT `scoreReplicas` hook land, the builtin
store scorer remains protocol-only (RDMA before TCP). Operators can inject a
custom `ReplicaScorer`.

### Local hot cache vs cluster replica

| | Local hot cache | Cluster MEMORY replica |
|--|-----------------|------------------------|
| Scope | One real-client process | Visible to every client via master metadata |
| Admission | Client CountMinSketch | Master sliding-window QPS |
| Helps dummy clients on the same node | Only via shm (`MC_STORE_LOCAL_HOT_CACHE_USE_SHM`) | Yes, once a replica exists on that `host_id` |
| Survives process restart | No | Until eviction |

Keep both. Local hot cache absorbs repeated hits inside one engine. Cluster
fanout is for cross-instance sharing (PD disaggregation, multiple DP ranks).

## Replication strategy

### When to add a replica

Keep the existing admission window. Extend the key of the window from
`tenant/key` to `tenant/key/domain` once reader identity is available:

- A key that is hot in one rack and cold elsewhere gets a replica **in that
  rack**, not a second copy in a random remote host.
- Global QPS still caps `dynamic_replication_max_memory_replicas`.

`observe` stays the safe rollout mode: log the domain-aware plan without
copying.

### Where to place it

`SelectDynamicReplicaPlan` scoring, highest first:

1. **Explicit `preferred_target_segment`** if still allocatable.
2. **Domain match** — `segment.host_id` (later rack/zone) equals
   `target_domain`, or `requester_domain` when target is empty, **and that
   domain does not already hold a MEMORY replica**.
3. **Different host** from existing MEMORY replicas (today's spread rule).
4. **Lower utilization**, with the 85% post-copy watermark.
5. **Stable `hash(key, segment)`** tie break.

If the preferred domain is full or already has a replica, fall back to 3–5
rather than failing the proposal. Replication remains best-effort.

Copy still uses the two-phase `PROCESSING` → `COMPLETE` protocol. The new
replica is invisible to Get until `CopyEnd`.

### What we do not do in v1

- Automatic scale-down / `ReplicaMove` when heat cools (RFC #1100 listed it;
  eviction already reclaims cold MEMORY).
- Changing `GetReplicaList` wire format in the same change as ranking.
- Requiring TENT or a cluster JSON map for host-level locality.

## Phased rollout

### Phase 1 — host locality (this change)

- Read: same-host MEMORY / NOF using reader `host_id` and `segmentHost()`.
- Placement: honor `requester_domain` / `target_domain` as `host_id` on
  `SubmitReplicaActionProposal`. Auto-Get fanout still uses different-host
  spread because Get does not yet name the reader.
- Docs and tests for the ranking / domain placement rules.

### Phase 2 — reader-aware auto-fanout

- Carry reader `host_id` (or `client_id`) on Get without breaking older
  clients — new RPC field or a parallel request struct.
- Per-`(key, host)` heat windows.
- Auto-proposal sets `requester_domain` to the reader's host so the extra
  replica lands beside the traffic.

### Phase 3 — rack/zone map + load

- Master cluster topology JSON labeling `host_id` → rack → zone.
- Domain strings `rack:` / `zone:`.
- `ReportNicLoadStats` plus TENT local_score injection into
  `SetRemoteReplicaScorer`.
- Soft-pin dynamically replicated hot keys so eviction does not immediately
  undo fanout.

## Failure and safety

- Incomplete copies stay `PROCESSING` and are never selected.
- Lease / cooldown limits prevent replica storms on a flash crowd.
- If the domain has no spare DRAM, skip fanout; reads keep using the existing
  replica.
- Same-host ranking never overrides an exact local-endpoint MEMORY hit
  (memcpy must remain the fastest path).
- Loopback `host_id` is empty by design (`ResolveMooncakeHostId`); same-host
  ranking is then a no-op so single-node tests stay deterministic.

## Related work

- [Mooncake Store design](mooncake-store.md) — allocation, pin, eviction.
- [SSD offload](ssd-offload.md) — promotion-on-hit is complementary tier
  movement.
- Transfer Engine topology-aware NIC selection
  ([transfer-engine](../transfer-engine/index.md)).
- Draft cost-aware routing ([PR #2013](https://github.com/kvcache-ai/Mooncake/pull/2013))
  and NIC-load reporting ([PR #3033](https://github.com/kvcache-ai/Mooncake/pull/3033))
  are the likely Phase 3 inputs; this design does not depend on them.
