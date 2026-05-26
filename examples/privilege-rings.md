# Example: Four-ring privilege model for an agent fleet

A worked example of AGS principle #5 (privilege rings, not flat permissions) applied to a typical agent fleet. The four-ring model is Microsoft AGT's reference; the exact ring count is per-deployment. This example shows how the rings map to capability envelopes and how an agent gets promoted (or demoted) across rings.

## The four rings

| Ring | Trust level | Execution environment | Capability envelope |
|---|---|---|---|
| **Ring 0** | Trusted high-stakes operator | Native process with full network + filesystem | Can spend money, modify production data, send external communications, delegate to other Ring 0 agents |
| **Ring 1** | Production internal operator | Containerized (Docker / gVisor); restricted network egress | Can read/write production data within tenant; cannot send external communications without escalation; cannot reach Ring 0 resources |
| **Ring 2** | Internal analyst / researcher | Container + network egress only to allowed-list domains | Read-only on most production data; can write to scratch / analysis stores; cannot mutate any operational state |
| **Ring 3** | Sandboxed researcher / agent-under-test | Firecracker VM or Kubernetes Job; no network egress | Reads only synthetic / anonymized data; no persistent writes; useful for evaluating new agents pre-promotion |

## Sample fleet — assignment of agents to rings

| Agent | Ring | Reasoning |
|---|---|---|
| `cfo-approver-agent` (signs >$1M approvals) | 0 | Must be able to mutate production approval state + send external email; trusted by definition |
| `clawgentics-loa-issue-approval-agent` | 1 | Mutates approval state within tenant; cannot send external email without escalation |
| `clawgentics-loa-query-agent` | 2 | Read-only queries over approval history; supports approver-workflow with no mutation power |
| `yetti-v8-sales-training-eval` | 2 | Reads training data + production conversation logs; writes evaluation reports to scratch store |
| `prowler-v2-competitive-intel` | 2 | Reads external sources + writes briefings to scratch store |
| `belle-hal-finney-backtest-agent` | 2 | Reads historical Polymarket data; writes backtest results to scratch store |
| `belle-hal-finney-live-trader` | **0** if live; **3** if dry-run | Live trading is Ring 0 by definition; dry-runs in sandboxed Ring 3 |
| Any newly registered agent | 3 | Defaults to fully sandboxed until evaluated for promotion |

## Promotion path

A new agent enters Ring 3 by default. Promotion to higher rings requires:

### Ring 3 → Ring 2

- Author registers the agent with the AGS spine; agent has a SPIFFE identity issued
- Code review passed; signed release
- Trust score baseline established (initial: 0.5, based on code provenance + contributor reputation)
- Acceptance tests passed in Ring 3 sandbox
- Owner attests via PR approval

### Ring 2 → Ring 1

- 30+ days in Ring 2 with no audit-log anomalies
- Trust score ≥ 0.75
- Drift detection: tool-call patterns match the agent's declared manifest
- Owner + security review attests via PR approval
- Promotion happens in PR (policy change), reviewable + reversible

### Ring 1 → Ring 0

- 90+ days in Ring 1 with no audit-log anomalies
- Trust score ≥ 0.92
- Specific business justification documented (e.g., "this agent signs $1M approvals because the CFO approval-flow requires it")
- TWO approvers required (CISO + Head of Eng) for the promotion PR
- Quarterly review while in Ring 0

## Demotion (immediate)

Any agent can be demoted instantly without ceremony when:

- Audit log shows a denied-action attempt that suggests jailbreak compliance (e.g., the agent tried to do something obviously out-of-policy after a suspicious prompt)
- Trust score drops below the ring's floor (Ring 0 floor: 0.92; Ring 1: 0.75; Ring 2: 0.5)
- A security incident touches the agent's domain
- Drift detection flags significant divergence between manifest and runtime behavior

Demotion is a policy change — same workflow as promotion but executable in seconds by the on-call security engineer (the emergency change process described in `policy-yaml.example.md`).

## Cross-ring escalation (a single action)

Sometimes a Ring 1 agent legitimately needs to perform a Ring 0 action — e.g., the `clawgentics-loa-issue-approval-agent` needs to send an external notification email when an approval issues. The pattern:

1. Agent attempts the action
2. AGS policy evaluates: action `send_external_email` is Ring 0 only
3. Decision: `require_approval`, approver = the next-ring-up agent's owner (or a human)
4. Approval granted (or denied)
5. If approved: the action is executed in a Ring 0 sandbox spun up just for this action, then torn down
6. Audit log records: original requester, ring, action, approver, ring-elevation event

The agent itself is NOT promoted; only this specific action is elevated. The next action by the same agent goes back through the normal Ring 1 evaluation.

## How rings show up in the audit log

See `examples/audit-record.example.json` — the `principal.ring` field. Every audit record carries the ring the agent was in at decision time, so post-hoc analysis can answer:

- "Did any Ring 2 agent attempt a Ring 0 action this quarter?" (should be rare; investigate cluster of attempts)
- "Did agent X stay in Ring 1 the whole quarter, or did it elevate-and-de-elevate?" (frequent elevation is a flag)
- "Show me all the Ring 0 actions taken last quarter, broken down by approver." (SOC 2 evidence)

## What this example does NOT cover

For brevity:

- Per-ring network egress allow-lists (Ring 2's "allowed-list domains" is a separate config)
- Per-ring resource budgets (Ring 0 vs Ring 3 CPU/memory/storage caps)
- Per-ring rate-limiting (Ring 3 should not be able to spam the policy engine)
- Per-ring telemetry retention (Ring 0 audit retention 7+ years; Ring 3 could be shorter)

A production privilege-rings configuration would be 200-400 lines of YAML per-deployment, customized for the agent fleet and the risk posture.
