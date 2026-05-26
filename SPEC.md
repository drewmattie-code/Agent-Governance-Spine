# Agent Governance Spine — Specification

> **Status:** v0.1-draft · Drew Mattie · 2026-05-26
> **License:** [CC BY 4.0](LICENSE-CC-BY-4.0)

This is the full technical specification for the Agent Governance Spine pattern. The [README](README.md) is the elevator pitch; this document is the build reference.

---

## 1. Context — what AGS solves

Production AI agent deployments today rely primarily on prompt-level safety as the control surface. *"Please follow the rules."* *"Don't drop tables."* *"Refuse unauthorized operations."* This is a polite request to a stochastic system.

The published empirical record closes this argument. On JailbreakBench (Chao et al., NeurIPS 2024), the standard open robustness benchmark for LLM jailbreaks, adaptive attacks reach **near-100% attack success rates** against frontier safety-aligned models. Andriushchenko et al. (ICLR 2025) report 100% ASR on GPT-4, GPT-3.5, Claude 3, Llama-3, Gemma-7B, and a dozen other frontier models using simple prompt-only attacks. Microsoft's AI Red Team, after red-teaming 100 generative AI products, concludes that *"AI red teaming is a continuous process that should adapt to the rapidly evolving risk landscape"* — model-layer defenses are probabilistic by construction.

**AGS is the architectural discipline that moves agent governance from prompt-level hope to deterministic application-layer enforcement.** Every tool call, message send, and delegation is intercepted in deterministic code BEFORE the model's intent reaches the wire. Allowed actions execute in scoped sandboxes; denied actions never execute; every decision is recorded tamper-evidently.

Four failure modes recur across naive agent deployments:

1. **Prompt-layer trust collapse.** Relying on the model's compliance instead of deterministic policy. Empirical case is closed (above).
2. **Identity blur.** Multi-agent systems where five agents share a single API key. *"An agent did it"* is not an incident response.
3. **Audit gap.** No tamper-evident record of what policy was active, what the agent requested, and why it was allowed or denied. Auditors and regulators cannot sign off.
4. **Policy drift.** Policy lives in prose / tribal knowledge / stale config — not in versioned, lintable, testable code. The system's actual behavior diverges silently from approved behavior.

AGS is the implementation pattern that addresses all four.

---

## 2. The architectural layer

AGS is the protocol-layer substrate beneath the data and coordination layers (PDS / ACS / ESF / CRI). Every agent action, regardless of which higher layer initiated it, passes through the spine before reaching any backend, tool, or external system.

```
┌──────────────────────────────────────────────────────────────────┐
│ AGENT (any framework — Claude Code / Anthropic Agent SDK /        │
│  OpenAI Agents SDK / LangGraph / AutoGen / custom)                │
└────────────────────────────────────┬─────────────────────────────┘
                                     ↓ proposed action
┌──────────────────────────────────────────────────────────────────┐
│ AGENT GOVERNANCE SPINE                                            │
│                                                                   │
│   ┌────────────────────────────┐  ┌─────────────────────────┐    │
│   │ Identity Layer             │  │ Policy Engine            │    │
│   │ SPIFFE / DID / mTLS        │  │ OPA / Cedar / equivalent │    │
│   │ — verifiable per-agent ID  │  │ — deterministic decide   │    │
│   └────────────┬───────────────┘  └────────────┬────────────┘    │
│                ↓                                ↓                 │
│            ┌────────────────────────────────────┐                 │
│            │ Decision (allow / deny / escalate) │                 │
│            └────────────┬───────────────────────┘                 │
│                         ↓                                         │
│   ┌─────────────────────────────────┐  ┌──────────────────┐      │
│   │ Privilege-Ring Sandbox          │  │ Audit Log         │      │
│   │ — tiered execution environment  │  │ — tamper-evident  │      │
│   └─────────────────────────────────┘  └──────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
                         ↓ allowed action only
┌──────────────────────────────────────────────────────────────────┐
│ Backend · Tool · External API · Agent-to-Agent Delegation         │
└──────────────────────────────────────────────────────────────────┘
```

Denied actions are not "unlikely." They are **structurally impossible** because the deterministic policy gate ran and returned deny before the call reached anything stateful.

---

## 3. The 10 principles

### 3.1 — Deterministic policy enforcement, not prompt-level safety

**Problem.** Prompt-level safety ("please follow these rules") is a polite request to a stochastic system. JailbreakBench, Andriushchenko et al., and the Microsoft Red Team's empirical record all show adaptive attacks reach near-100% ASR against frontier safety-aligned models.

**Pattern.** Every action — every tool call, every message, every delegation — passes through a deterministic policy gate written in code, BEFORE the model's intent reaches the wire. The gate returns one of three decisions: allow, deny, escalate-for-approval. There is no fourth option of "the model said no."

**Implementation.** A policy evaluator wraps every action. The simplest shape:

```python
from agentmesh.governance import govern
safe_tool = govern(my_tool, policy="policy.yaml")
safe_tool(action="read", table="users")    # evaluated; allowed
safe_tool(action="drop", table="users")    # raises GovernanceDenied
```

The policy evaluator is OPA / Cedar / equivalent. The decision is a function of (action, principal, context, policy) — not a function of the model's output text.

**Anti-pattern.** "We added a system-prompt rule asking the agent to refuse destructive operations." That is not enforcement. It is a wish.

---

### 3.2 — Identity per agent, not per session

**Problem.** Multi-agent systems frequently share credentials. Five agents under one API key. When something goes wrong: *"an agent did it"* is not an incident response. Attribution is impossible.

**Pattern.** Every agent has a stable, verifiable cryptographic identity. SPIFFE workload identity, W3C DID, mTLS certificates with per-agent SANs — pick one, but every agent is uniquely identifiable on every action.

The identity attests itself to the policy engine on every action. The policy engine includes the identity in the decision context. The audit log records the identity on every decision.

**Implementation.** Bootstrap an identity provider (SPIRE for SPIFFE, a DID registrar, an internal CA for mTLS). Every agent process loads its identity at startup. Every action carries the identity through to the spine.

**Anti-pattern.** Shared API keys across agents. Service-account credentials that don't distinguish individual agents. "We'll figure it out from the logs" — there won't be enough information in the logs to figure it out.

---

### 3.3 — Tamper-evident audit log

**Problem.** Auditors and regulators need provable answers to: *what policy was active, what did the agent request, why was it allowed or denied, when did this happen, who attested it.* A flat log file in a syslog destination doesn't survive serious audit.

**Pattern.** Every decision (allow, deny, escalate) writes to an append-only audit log. The log is cryptographically anchored — hash chain, Merkle tree, signed batches, or commitment anchoring to an external timestamp authority. Any tampering is detectable.

The audit record includes: timestamp, agent identity, requested action, full context that fed into the policy evaluation, policy version active at decision time, decision outcome, decision rationale (which rule fired). Customer-downloadable for their own retention.

**Implementation.** Append-only Postgres table with row-level hash chain (each row references hash of prior row), batched into Merkle roots written to a separate immutable store. Optional anchoring to a public chain or trusted timestamp service for the strongest tamper-evidence.

**Anti-pattern.** Logs to stdout. Logs to a writable file. Logs with no integrity protection. Logs that the agent itself can rotate. Audit data is not the agent's data — separate it.

---

### 3.4 — Policy as code, not as prose

**Problem.** Policy that lives in system prompts, in Notion documents, or in tribal knowledge has no version control, no linting, no testing, no rollback. The actual behavior of the deployed system silently diverges from the approved policy.

**Pattern.** Policy is code. YAML, OPA Rego, Cedar — pick one, but the policy file is versioned in git, lintable (`agt lint-policy policies/` or equivalent), testable (every rule has a test case), and reviewable (PR-gated). The policy engine loads the policy from the code artifact, not from a prompt.

**Implementation.** A `policies/` directory in the repo. CI gates: lint must pass, every rule must have at least one test, every PR touching policy requires reviewer approval from a designated owner. Production loads from a pinned policy version; emergency policy changes are themselves changes-as-code (no console hotfix).

**Anti-pattern.** Policy in the system prompt. Policy in a UI configurator with no export-to-git workflow. Policy in a Notion doc that no one updates.

---

### 3.5 — Privilege rings, not flat permissions

**Problem.** Flat permission models force a choice: either every agent can do everything (insecure) or every agent does nothing (useless). The reality is a graduated trust model — some agents are low-risk; some are high-risk.

**Pattern.** Tiered privilege rings. Ring 0 = trusted high-stakes operators (can modify production, can spend money). Ring 3 = sandboxed read-only researchers (network restricted, filesystem restricted, no state mutation). Rings 1-2 are in between. Microsoft's AGT ships with four rings as the reference; the exact count is per-deployment.

The policy engine maps the requesting agent's identity to a ring. Each ring has a known capability envelope. Cross-ring escalation is itself a policy-governed event.

**Implementation.** Container-level isolation (Docker / Kubernetes namespaces / gVisor / Firecracker) for high-risk rings; process-level isolation for lower-risk ones. The audit log records the ring at the time of each action.

**Anti-pattern.** All agents share the same execution environment. Permissions defined at the API-key level rather than the agent-process level. "We sandbox the model output" — no, sandbox the execution.

---

### 3.6 — Kill switch + SLO monitoring + chaos testing

**Problem.** Agents in production drift. Goals shift. Sometimes one breaks and starts behaving badly. Without runtime guarantees, the only response is "wait for someone to notice."

**Pattern.** Three runtime guarantees:

1. **Kill switch.** A human-reachable mechanism to immediately stop any agent, by ID, in seconds. Not "restart the cluster" — a targeted stop.
2. **SLO monitoring.** Every deployed agent has an SLO (e.g., "no more than 0.1% denied actions per hour"). Breaches trigger alerts to humans.
3. **Chaos testing.** Of the governance layer itself, not just the agents. Inject identity-attestation failures; test policy-engine downtime behavior; verify the audit log remains intact under load.

**Implementation.** The kill switch is a separate control plane that can mutate the policy to "deny all" for a specific agent identity in O(seconds). SLO monitoring is OpenTelemetry-style. Chaos testing is scheduled (e.g., quarterly) and findings feed back into spec / harness updates.

**Anti-pattern.** "Stop the agent" means "restart the whole stack." No SLOs defined; "we'll know if something is wrong." No chaos testing; "the governance layer is too important to chaos-test" — exactly backwards.

---

### 3.7 — Tool poisoning detection + drift monitoring

**Problem.** The tool supply chain is itself a threat surface. An MCP server you trust today can be updated with hidden instructions tomorrow. A typosquatted tool can be installed by mistake. The tool's runtime behavior can drift from its authored manifest without anyone noticing.

**Pattern.** The spine includes active monitoring of the tool layer:

- **Hash pinning** of installed MCP servers / tools. Updates require explicit approval.
- **Hidden instruction scanning** of tool manifests, descriptions, and runtime responses. If a tool's response includes prompt-injection-style content directed at the model, the spine logs and (per policy) blocks.
- **Drift detection** comparing tool's manifest to its runtime behavior. If a tool advertised "read-only" starts writing, the spine flags.
- **Typosquatting detection** at install time — alert on tool names within edit-distance 1 of known tools.

**Implementation.** Microsoft AGT's MCP Security Gateway is a reference implementation. Custom implementations are straightforward — hash the manifest, scan the responses, compare advertised vs observed.

**Anti-pattern.** *"We trust all the tools in our marketplace."* Trust must be re-verified at every action, not assumed once at install.

---

### 3.8 — Shadow agent discovery

**Problem.** Production AI agents are easy to spin up. Developers create them; teams adopt new frameworks; vendors install agents as part of their products. Unregistered agents — running in your infrastructure but unknown to your governance layer — are a real production risk.

**Pattern.** Active discovery of agent processes, configs, and repos. The spine periodically (e.g., daily) scans:

- Running processes for known agent-framework signatures
- Repo configs for `.claude/`, `.agents/`, `.mcp.json`, or framework-specific markers
- API gateway logs for agent-shaped user-agent strings / API call patterns

Any agent not registered with the spine is flagged for review.

**Implementation.** Microsoft AGT's Shadow AI Discovery is a reference. Custom implementations grep filesystem + process list + network flow logs against a known-agent signature set.

**Anti-pattern.** Relying on "all our agents are registered" as a manual process. The whole point of automation is that humans miss things.

---

### 3.9 — Trust scoring for plugin marketplaces

**Problem.** Multi-agent systems aggregate trust from multiple sources: model provider trust, framework trust, plugin / tool / connector trust. When a new plugin is added, "trust the developer" is not a sufficient assessment.

**Pattern.** Composite agent-level trust score. Inputs include:
- Code provenance (signed releases, reproducible builds, CVE history)
- Contributor reputation (social-engineering risk per contributor)
- Runtime behavior history (drift incidents, denied actions, audit anomalies)
- Marketplace metadata (downloads, time in production, review breadth)

The composite score is consumable by policy: *"plugins with trust score below X cannot reach Ring 0 actions."*

**Implementation.** Microsoft AGT's Agent Marketplace ships this. The C&R catalog's [CRI](https://github.com/drewmattie-code/Composite-Risk-Index) framework is the architectural pattern; AGS principle #9 is one of its applications — at the agent / plugin / tool layer rather than the customer-decision layer.

**Anti-pattern.** Allow-listing plugins manually with no re-evaluation. Trust isn't a one-time vote; it's a continuous signal.

---

### 3.10 — Governance-aware training

**Problem.** Agents trained without exposure to the policy substrate must learn at runtime what they can and can't do. Every learning-at-runtime episode is a denied-action event in production, which is friction.

**Pattern.** If you control post-training, include the governance signal in the loss. RL with violation penalties: when the trained agent attempts a policy-forbidden action during training, the reward function penalizes. The deployed agent has internalized the policy substrate as a prior, not just as runtime denial.

This applies to teams with frontier-lab capability (we don't, today). Most teams will live entirely with principle #1-#9 as runtime enforcement — that's fine; this principle is what unlocks the next-level deployment.

**Implementation.** Microsoft AGT's Agent Lightning package is the reference. Moonshot's PARL (Kimi K2.5) is a parallel architectural reference (multi-agent coordination penalties). Both ship "train with a governance signal" mechanics.

**Anti-pattern.** Training an agent to be maximally compliant with the user, then expecting the runtime policy substrate to be sufficient defense. The two should be designed together.

---

## 4. SLAs and success metrics

| Metric | Target | Rationale |
|---|---|---|
| Actions executed without policy evaluation | 0 | Non-negotiable. Every action is policy-gated. |
| Actions executed without verifiable agent identity | 0 | "An agent did it" is never acceptable. |
| Audit log completeness | 100% | Every decision (allow + deny + escalate) is recorded. SOC 2 / ISO 27001 prerequisite. |
| Audit log tamper-evidence | Cryptographic anchoring | Hash chain / Merkle / signed batches / external timestamp. |
| Policy evaluation p95 latency | < 5 ms | The spine cannot be the latency bottleneck. |
| Policy as code coverage | 100% of in-scope actions | If a tool isn't covered by policy, it shouldn't be reachable. |
| Shadow agent discovery cadence | Weekly minimum | Unregistered agents are a real risk. |
| Policy lint pass rate before deploy | 100% | No untested policy reaches production. |
| Adversarial penetration test (red team) ASR | < 1% structural ASR | Acknowledged: this is < model-layer ASR by orders of magnitude. |
| Time from policy decision to audit-log record | < 1 s | Audit lag is an attack window. |
| Kill-switch activation time | < 10 s | A runaway agent must be stoppable in seconds. |

---

## 5. Build sequence

AGS is built in the following sequence from skeleton to first reference deployment. Each step depends on the previous one. Pace varies by team and tooling; the sequence does not.

| Step | Deliverable | Why |
|---|---|---|
| 1 | Policy engine + first deterministic deny | One tool wrapped; one policy rule; allow / deny path exercised end-to-end |
| 2 | Audit log | Append-only, structured, written on every decision; queryable for post-hoc forensic |
| 3 | Agent identity | Every action carries verifiable agent-ID; cross-tenant identity isolation enforced |
| 4 | Tamper-evidence | Commitment anchoring on the audit log — hash chain or Merkle or signed batches |
| 5 | Privilege rings | Sandboxed execution tiered by agent trust level |
| 6 | Kill switch + SLO monitoring | Human-operated stop mechanism; SLO breaches trigger alerts |
| 7 | Tool poisoning detection + shadow agent discovery | Supply-chain governance |
| 8 | Spec / one-pager / case study | Compounds future adoption |

---

## 6. Anti-patterns to avoid

| Anti-pattern | Why it breaks | What to do instead |
|---|---|---|
| Prompt-level safety as the primary control surface | Adaptive attacks reach ~100% ASR; you're a polite request away from breach | Deterministic policy enforcement at the application layer (principle #1) |
| Shared API keys across agents | "An agent did it" is uninvestigable | Per-agent identity with cryptographic attestation (principle #2) |
| Unsigned log file as the audit record | Auditors cannot certify; regulators cannot accept | Tamper-evident append-only log with commitment anchoring (principle #3) |
| Policy in the system prompt | No version control; no testing; silent drift between approved and deployed | Policy as code, lintable + testable + PR-reviewed (principle #4) |
| Flat permissions ("every agent can do everything if authorized") | Insecure or useless; binary choice | Privilege rings — tiered execution environments (principle #5) |
| No kill switch | Runaway agent stops when humans get around to it | Targeted O(seconds) stop for any agent ID (principle #6) |
| "We trust all tools in the marketplace" | Tool supply chain is a real threat surface | Hash pinning + hidden-instruction scanning + drift detection (principle #7) |
| Manual agent registration | Humans miss things; unregistered agents accumulate silently | Active discovery via process / config / repo scanning (principle #8) |
| One-time plugin trust vote | Trust degrades over time without continuous signal | Composite trust score with continuous inputs (principle #9) |
| Training agents to be compliant with users only | Runtime policy bears the full load; learning-at-runtime is friction | Governance-aware training where feasible (principle #10) |

---

## 7. Compatibility with existing standards

AGS is compatible with — and built on top of — these standards:

- **OPA (Open Policy Agent)** — CNCF general-purpose policy engine; the reference implementation for principle #4
- **AWS Cedar** — verified analyzable authorization language; alternative for principle #4
- **Permit.io** — commercial policy-as-code with explicit agent-governance framing
- **SPIFFE / SPIRE** — CNCF workload identity; reference for principle #2
- **W3C Decentralized Identifiers (DIDs) v1.0** — W3C Recommendation; alternative identity model for principle #2
- **OWASP LLM06:2025 (Excessive Agency)** — risk taxonomy framing
- **OWASP Agentic AI Threats and Mitigations** (Feb 2025) — companion taxonomy
- **Microsoft Agent Governance Toolkit (AGT)** — the most mature productized implementation of all 10 principles

AGS is also compatible with the four companion specifications in the catalog:

- **[PDS (Progressive Discovery Spine)](https://github.com/drewmattie-code/Progressive-Discovery-Spine)** — single-agent tool discipline; PDS gateway sits on top of AGS substrate.
- **[ACS (Adversarial Coordination Spine)](https://github.com/drewmattie-code/Adversarial-Coordination-Spine)** — multi-agent coordination; every cross-agent handoff is governed by AGS.
- **[ESF (External Signal Fabric)](https://github.com/drewmattie-code/External-Signal-Fabric)** — external signals; AGS governs which agents can subscribe to which signal classes.
- **CRI (Composite Risk Index)** — composite scoring (private); AGS principle #9 (plugin trust scoring) is a CRI-shaped fusion at the agent / tool layer.

---

## 8. The six-way failure attribution principle

AGS extends the catalog's failure-attribution dictionary from five (PDS+ESF+ACS-planner+ACS-evaluator+CRI) to **six** by adding the governance-attribution surface:

| Attribution | Owned by | "Failure looked like..." |
|---|---|---|
| Bad customer data | PDS | Wrong supplier ID, stale internal cache, missing record |
| Bad world data | ESF | Expired signal, mis-tagged advisory, broken adapter |
| Bad reasoning | ACS Planner | Plan unsupported by signals |
| Bad evaluation | ACS Evaluator | Rubber-stamped contract violation |
| Bad scoring | CRI | Confident score on insufficient inputs |
| **Bad governance** | **AGS** | **Policy gap (action wasn't denied because no rule covered it), identity ambiguity (we know an agent did it but not which), audit gap (no record exists), policy drift (deployed policy differs from approved policy)** |

Within AGS itself, bad governance decomposes further: policy-coverage gap, identity-attestation gap, audit-tamper failure, tool-supply-chain compromise, shadow-agent presence. The six-attribution model makes any catalog-grade system failure locatable to a single ownable layer.

---

## 9. References

### Policy + identity foundations
- Open Policy Agent (CNCF) — [openpolicyagent.org/docs](https://www.openpolicyagent.org/docs/)
- AWS Cedar — [docs.cedarpolicy.com](https://docs.cedarpolicy.com/) · Cedar paper [arXiv:2403.04651](https://arxiv.org/pdf/2403.04651)
- Permit.io — [permit.io](https://www.permit.io/)
- SPIFFE / SPIRE (CNCF) — [spiffe.io](https://spiffe.io/docs/latest/spiffe-about/overview/)
- W3C Decentralized Identifiers (DIDs) v1.0 — [w3.org/TR/did-core](https://www.w3.org/TR/did-core/)

### Productized governance kernels
- Microsoft — *Agent Governance Toolkit* — [github.com/microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)

### Empirical case for deterministic enforcement
- Chao et al., *JailbreakBench* (NeurIPS 2024) — [arXiv:2404.01318](https://arxiv.org/abs/2404.01318)
- Andriushchenko, Croce, Flammarion, *Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks* (ICLR 2025) — [arXiv:2404.02151](https://arxiv.org/abs/2404.02151)
- Microsoft AI Red Team — *3 Takeaways from Red Teaming 100 Generative AI Products* (Jan 2025) — [microsoft.com](https://www.microsoft.com/en-us/security/blog/2025/01/13/3-takeaways-from-red-teaming-100-generative-ai-products/)

### OWASP risk taxonomy
- OWASP LLM06:2025 — *Excessive Agency* — [genai.owasp.org](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- OWASP — *Agentic AI Threats and Mitigations* (Feb 2025) — [genai.owasp.org](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)

### Catalog peers
- Progressive Discovery Spine — [github.com/drewmattie-code/Progressive-Discovery-Spine](https://github.com/drewmattie-code/Progressive-Discovery-Spine)
- Adversarial Coordination Spine — [github.com/drewmattie-code/Adversarial-Coordination-Spine](https://github.com/drewmattie-code/Adversarial-Coordination-Spine)
- External Signal Fabric — [github.com/drewmattie-code/External-Signal-Fabric](https://github.com/drewmattie-code/External-Signal-Fabric)
- Composite Risk Index — [github.com/drewmattie-code/Composite-Risk-Index](https://github.com/drewmattie-code/Composite-Risk-Index) *(private)*

---

## 10. Versioning

This specification follows semantic versioning. Breaking changes to the conceptual model bump the major version; new principles or refinements bump the minor. Editorial fixes bump the patch.

- **v0.1-draft** — initial draft (2026-05-26). Triggered by Microsoft Agent Governance Toolkit release. Awaiting field feedback before v1.0 lock.

---

## 11. Author

[Drew Mattie](https://www.linkedin.com/in/drew-mattie-88084826/) · SaaSquach AI Labs (a division of Charles & Roe Inc.) · 2026

AGS was developed at SaaSquach AI Labs (a division of Charles & Roe Inc.) as the fifth specification in the agent-architecture catalog alongside PDS, ACS, ESF, and CRI. This specification is released as open documentation under [CC BY 4.0](LICENSE-CC-BY-4.0) so the pattern can be adopted, adapted, and built upon — with attribution.
