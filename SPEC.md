# Agent Governance Spine: Specification

> **Status:** v1.3 · Drew Mattie · 2026-07-12
> **License:** [CC BY 4.0](LICENSE-CC-BY-4.0)

This is the full technical specification for the Agent Governance Spine pattern. The [README](README.md) is the elevator pitch; this document is the build reference.

---

## 1. Context: what AGS solves

Production AI agent deployments today rely primarily on prompt-level safety as the control surface. *"Please follow the rules."* *"Don't drop tables."* *"Refuse unauthorized operations."* This is a polite request to a stochastic system.

The published empirical record closes this argument. On JailbreakBench (Chao et al., NeurIPS 2024), the standard open robustness benchmark for LLM jailbreaks, adaptive attacks reach **near-100% attack success rates** against frontier safety-aligned models. Andriushchenko et al. (ICLR 2025) report 100% ASR on GPT-4, GPT-3.5, Claude 3, Llama-3, Gemma-7B, and a dozen other frontier models using simple prompt-only attacks. Microsoft's AI Red Team, after red-teaming 100 generative AI products, concludes that *"AI red teaming is a continuous process that should adapt to the rapidly evolving risk landscape"*. Model-layer defenses are probabilistic by construction.

**AGS is the architectural discipline that moves agent governance from prompt-level hope to deterministic application-layer enforcement.** Every tool call, message send, and delegation is intercepted in deterministic code BEFORE the model's intent reaches the wire. Allowed actions execute in scoped sandboxes; denied actions never execute; every decision is recorded tamper-evidently.

Four failure modes recur across naive agent deployments:

1. **Prompt-layer trust collapse.** Relying on the model's compliance instead of deterministic policy. Empirical case is closed (above).
2. **Identity blur.** Multi-agent systems where five agents share a single API key. *"An agent did it"* is not an incident response.
3. **Audit gap.** No tamper-evident record of what policy was active, what the agent requested, and why it was allowed or denied. Auditors and regulators cannot sign off.
4. **Policy drift.** Policy lives in prose / tribal knowledge / stale config, not in versioned, lintable, testable code. The system's actual behavior diverges silently from approved behavior.

AGS is the implementation pattern that addresses all four.

---

## 2. The architectural layer

AGS is the protocol-layer substrate beneath the data and coordination layers (PDS / ACS / ESF / CRI). Every agent action, regardless of which higher layer initiated it, passes through the spine before reaching any backend, tool, or external system.

```
┌──────────────────────────────────────────────────────────────────┐
│ AGENT (any framework - Claude Code / Anthropic Agent SDK /        │
│  OpenAI Agents SDK / LangGraph / AutoGen / custom)                │
└────────────────────────────────────┬─────────────────────────────┘
                                     ↓ proposed action
┌──────────────────────────────────────────────────────────────────┐
│ AGENT GOVERNANCE SPINE                                            │
│                                                                   │
│   ┌────────────────────────────┐  ┌─────────────────────────┐    │
│   │ Identity Layer             │  │ Policy Engine            │    │
│   │ SPIFFE / DID / mTLS        │  │ OPA / Cedar / equivalent │    │
│   │ - verifiable per-agent ID  │  │ - deterministic decide   │    │
│   └────────────┬───────────────┘  └────────────┬────────────┘    │
│                ↓                                ↓                 │
│            ┌────────────────────────────────────┐                 │
│            │ Decision (allow / deny / escalate) │                 │
│            └────────────┬───────────────────────┘                 │
│                         ↓                                         │
│   ┌─────────────────────────────────┐  ┌──────────────────┐      │
│   │ Privilege-Ring Sandbox          │  │ Audit Log         │      │
│   │ - tiered execution environment  │  │ - tamper-evident  │      │
│   └─────────────────────────────────┘  └──────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
                         ↓ allowed action only
┌──────────────────────────────────────────────────────────────────┐
│ Backend · Tool · External API · Agent-to-Agent Delegation         │
└──────────────────────────────────────────────────────────────────┘
```

Denied actions are not "unlikely." They are **structurally impossible** because the deterministic policy gate ran and returned deny before the call reached anything stateful.

---

## 3. The 14 principles

### 3.1: Deterministic policy enforcement, not prompt-level safety

**Problem.** Prompt-level safety ("please follow these rules") is a polite request to a stochastic system. JailbreakBench, Andriushchenko et al., and the Microsoft Red Team's empirical record all show adaptive attacks reach near-100% ASR against frontier safety-aligned models.

**Pattern.** Every action (every tool call, every message, every delegation) passes through a deterministic policy gate written in code, BEFORE the model's intent reaches the wire. The gate returns one of three decisions: allow, deny, escalate-for-approval. There is no fourth option of "the model said no."

The enforcement point is the tool-mediation chokepoint, the same place tools are discovered and handed to the agent. The layer that surfaces a tool to an agent (the PDS gateway) is the natural and only place to enforce tool-call policy deterministically, because it sits on the single path every tool call must cross. One chokepoint does both jobs: discovery and governance. Scattering enforcement across individual agents, or asking each agent to self-police, reopens the prompt-layer hole this principle closes. AGS and PDS compose here: PDS describes the discovery discipline at that chokepoint, AGS describes the enforcement discipline at the same chokepoint. AWS Bedrock AgentCore demonstrates exactly this, enforcing AgentCore Policy at the AgentCore Gateway, the same gateway that turns APIs and MCP servers into agent-callable tools, intercepting every tool call before it runs and outside the LLM loop.

**Implementation.** A policy evaluator wraps every action, co-located at the tool-mediation gateway. The simplest shape:

```python
from agentmesh.governance import govern
safe_tool = govern(my_tool, policy="policy.yaml")
safe_tool(action="read", table="users")    # evaluated; allowed
safe_tool(action="drop", table="users")    # raises GovernanceDenied
```

The policy evaluator is OPA / Cedar / equivalent. The decision is a function of (action, principal, context, policy), not a function of the model's output text.

**Anti-pattern.** "We added a system-prompt rule asking the agent to refuse destructive operations." That is not enforcement. It is a wish.

---

### 3.2: Identity per agent, not per session

**Problem.** Multi-agent systems frequently share credentials. Five agents under one API key. When something goes wrong: *"an agent did it"* is not an incident response. Attribution is impossible.

**Pattern.** Every agent has a stable, verifiable cryptographic identity. SPIFFE workload identity, W3C DID, mTLS certificates with per-agent SANs. Pick one, but every agent is uniquely identifiable on every action.

The identity attests itself to the policy engine on every action. The policy engine includes the identity in the decision context. The audit log records the identity on every decision.

**Implementation.** Bootstrap an identity provider (SPIRE for SPIFFE, a DID registrar, an internal CA for mTLS). Every agent process loads its identity at startup. Every action carries the identity through to the spine.

**Anti-pattern.** Shared API keys across agents. Service-account credentials that don't distinguish individual agents. "We'll figure it out from the logs." There won't be enough information in the logs to figure it out.

---

### 3.3: Tamper-evident audit log

**Problem.** Auditors and regulators need provable answers to: *what policy was active, what did the agent request, why was it allowed or denied, when did this happen, who attested it.* A flat log file in a syslog destination doesn't survive serious audit.

**Pattern.** Every decision (allow, deny, escalate) writes to an append-only audit log. The log is cryptographically anchored: hash chain, Merkle tree, signed batches, or commitment anchoring to an external timestamp authority. Any tampering is detectable.

The audit record includes: timestamp, agent identity, requested action, full context that fed into the policy evaluation, policy version active at decision time, decision outcome, decision rationale (which rule fired). Customer-downloadable for their own retention.

**Implementation.** Append-only Postgres table with row-level hash chain (each row references hash of prior row), batched into Merkle roots written to a separate immutable store. Optional anchoring to a public chain or trusted timestamp service for the strongest tamper-evidence.

**Anti-pattern.** Logs to stdout. Logs to a writable file. Logs with no integrity protection. Logs that the agent itself can rotate. Audit data is not the agent's data. Separate it.

---

### 3.4: Policy as code, authored and validated, not as prose

**Problem.** Policy that lives in system prompts, in Notion documents, or in tribal knowledge has no version control, no linting, no testing, no rollback. The actual behavior of the deployed system silently diverges from the approved policy. A second, subtler problem sits on top of this: even when policy IS code, hand-writing a formal policy language is slow and error-prone, and a policy that compiles cleanly can still be over-permissive, over-restrictive, or unsatisfiable against the actual tool schema. Policy authorship and policy validation are governance surfaces in their own right, not just policy enforcement.

**Pattern.** Policy is code. YAML, OPA Rego, Cedar. Pick one, but the policy file is versioned in git, lintable (`agt lint-policy policies/` or equivalent), testable (every rule has a test case), and reviewable (PR-gated). The policy engine loads the policy from the code artifact, not from a prompt.

Authoring can be natural-language-front, formal-language-back. An author states the rule in natural language, the system compiles it to a formal policy language (Cedar or equivalent), and the compiled artifact is machine-verified before it is ever enforced. The verification pass uses automated reasoning over the compiled policy and the tool schema to catch over-permissive, over-restrictive, and unsatisfiable rules at author time, not at incident time. The natural-language statement is the human-reviewable intent, the compiled formal artifact is the thing that runs, and the verification result is the gate between the two. AWS Bedrock AgentCore Policy demonstrates this exact loop: rules authored in natural language, compiled to Cedar, validated against the tool schema with automated reasoning, then enforced deterministically. The discipline is the same regardless of vendor: the artifact that runs is formal and verified, the artifact a human reads and approves can be natural language.

**Implementation.** A `policies/` directory in the repo. CI gates: lint must pass, every rule must have at least one test, every PR touching policy requires reviewer approval from a designated owner. Where a natural-language-front toolchain is used, CI also gates on the compile step and the automated-reasoning verification pass: a policy that does not compile, or that the verifier flags as over-permissive, over-restrictive, or unsatisfiable, never reaches the pinned production version. Both the natural-language source and the compiled formal artifact are committed, so a reviewer reads intent and the engine runs the verified artifact. Production loads from a pinned policy version; emergency policy changes are themselves changes-as-code (no console hotfix).

**Anti-pattern.** Policy in the system prompt. Policy in a UI configurator with no export-to-git workflow. Policy in a Notion doc that no one updates. Compiling natural language to a formal policy and enforcing it without a verification pass on the compiled artifact, so an over-permissive or unsatisfiable rule ships unnoticed.

---

### 3.5: Privilege rings, not flat permissions

**Problem.** Flat permission models force a choice: either every agent can do everything (insecure) or every agent does nothing (useless). The reality is a graduated trust model: some agents are low-risk; some are high-risk.

**Pattern.** Tiered privilege rings. Ring 0 = trusted high-stakes operators (can modify production, can spend money). Ring 3 = sandboxed read-only researchers (network restricted, filesystem restricted, no state mutation). Rings 1-2 are in between. Microsoft's AGT ships with four rings as the reference; the exact count is per-deployment.

The policy engine maps the requesting agent's identity to a ring. Each ring has a known capability envelope. Cross-ring escalation is itself a policy-governed event.

**Implementation.** Container-level isolation (Docker / Kubernetes namespaces / gVisor / Firecracker) for high-risk rings; process-level isolation for lower-risk ones. The audit log records the ring at the time of each action.

**Anti-pattern.** All agents share the same execution environment. Permissions defined at the API-key level rather than the agent-process level. "We sandbox the model output." No, sandbox the execution.

---

### 3.6: Kill switch + SLO monitoring + chaos testing

**Problem.** Agents in production drift. Goals shift. Sometimes one breaks and starts behaving badly. Without runtime guarantees, the only response is "wait for someone to notice."

**Pattern.** Three runtime guarantees:

1. **Kill switch.** A human-reachable mechanism to immediately stop any agent, by ID, in seconds. Not "restart the cluster", a targeted stop.
2. **SLO monitoring.** Every deployed agent has an SLO (e.g., "no more than 0.1% denied actions per hour"). Breaches trigger alerts to humans.
3. **Chaos testing.** Of the governance layer itself, not just the agents. Inject identity-attestation failures; test policy-engine downtime behavior; verify the audit log remains intact under load.

**Implementation.** The kill switch is a separate control plane that can mutate the policy to "deny all" for a specific agent identity in O(seconds). SLO monitoring is OpenTelemetry-style. Chaos testing is scheduled (e.g., quarterly) and findings feed back into spec / harness updates.

**Anti-pattern.** "Stop the agent" means "restart the whole stack." No SLOs defined; "we'll know if something is wrong." No chaos testing; "the governance layer is too important to chaos-test", exactly backwards.

---

### 3.7: Tool poisoning detection + drift monitoring

**Problem.** The tool supply chain is itself a threat surface. An MCP server you trust today can be updated with hidden instructions tomorrow. A typosquatted tool can be installed by mistake. The tool's runtime behavior can drift from its authored manifest without anyone noticing.

**Pattern.** The spine includes active monitoring of the tool layer:

- **Hash pinning** of installed MCP servers / tools. Updates require explicit approval.
- **Hidden instruction scanning** of tool manifests, descriptions, and runtime responses. If a tool's response includes prompt-injection-style content directed at the model, the spine logs and (per policy) blocks.
- **Drift detection** comparing tool's manifest to its runtime behavior. If a tool advertised "read-only" starts writing, the spine flags.
- **Typosquatting detection** at install time: alert on tool names within edit-distance 1 of known tools.

**Implementation.** Microsoft AGT's MCP Security Gateway is a reference implementation. Custom implementations are straightforward: hash the manifest, scan the responses, compare advertised vs observed.

**Anti-pattern.** *"We trust all the tools in our marketplace."* Trust must be re-verified at every action, not assumed once at install.

---

### 3.8: Shadow agent discovery

**Problem.** Production AI agents are easy to spin up. Developers create them; teams adopt new frameworks; vendors install agents as part of their products. Unregistered agents, running in your infrastructure but unknown to your governance layer, are a real production risk.

**Pattern.** Active discovery of agent processes, configs, and repos. The spine periodically (e.g., daily) scans:

- Running processes for known agent-framework signatures
- Repo configs for `.claude/`, `.agents/`, `.mcp.json`, or framework-specific markers
- API gateway logs for agent-shaped user-agent strings / API call patterns

Any agent not registered with the spine is flagged for review.

**Implementation.** Microsoft AGT's Shadow AI Discovery is a reference. Custom implementations grep filesystem + process list + network flow logs against a known-agent signature set.

**Anti-pattern.** Relying on "all our agents are registered" as a manual process. The whole point of automation is that humans miss things.

---

### 3.9: Trust scoring for plugin marketplaces

**Problem.** Multi-agent systems aggregate trust from multiple sources: model provider trust, framework trust, plugin / tool / connector trust. When a new plugin is added, "trust the developer" is not a sufficient assessment.

**Pattern.** Composite agent-level trust score. Inputs include:
- Code provenance (signed releases, reproducible builds, CVE history)
- Contributor reputation (social-engineering risk per contributor)
- Runtime behavior history (drift incidents, denied actions, audit anomalies)
- Marketplace metadata (downloads, time in production, review breadth)

The composite score is consumable by policy: *"plugins with trust score below X cannot reach Ring 0 actions."*

**Implementation.** Microsoft AGT's Agent Marketplace ships this. The C&R catalog's CRI framework *(private)* is the architectural pattern; AGS principle #9 is one of its applications, at the agent / plugin / tool layer rather than the customer-decision layer.

**Anti-pattern.** Allow-listing plugins manually with no re-evaluation. Trust isn't a one-time vote; it's a continuous signal.

---

### 3.10: Governance-aware training

**Problem.** Agents trained without exposure to the policy substrate must learn at runtime what they can and can't do. Every learning-at-runtime episode is a denied-action event in production, which is friction.

**Pattern.** If you control post-training, include the governance signal in the loss. RL with violation penalties: when the trained agent attempts a policy-forbidden action during training, the reward function penalizes. The deployed agent has internalized the policy substrate as a prior, not just as runtime denial.

This applies to teams with frontier-lab capability (we don't, today). Most teams will live entirely with principle #1-#9 as runtime enforcement. That's fine; this principle is what unlocks the next-level deployment.

**Implementation.** Microsoft AGT's Agent Lightning package is the reference. Moonshot's PARL (Kimi K2.5) is a parallel architectural reference (multi-agent coordination penalties). Both ship "train with a governance signal" mechanics.

**Anti-pattern.** Training an agent to be maximally compliant with the user, then expecting the runtime policy substrate to be sufficient defense. The two should be designed together.

---

### 3.11: Cost and consumption governance

**Problem.** Policy, identity, and audit cover *what* an agent is allowed to do and *who* did it, but not *how much it consumed*. Token consumption, spend, and data-flow volume are ungoverned by default. An agent that retries without backoff is simultaneously a reliability incident and a cost incident. A concrete instance from our own systems: an ingestion adapter with an empty API key hit a 429, retried with no backoff, and produced 15.6M errors and a 5GB log before the process was killed. The same loop that burns reliability burns money, and neither was bounded.

**Pattern.** Treat token consumption, spend, and data-flow volume as a first-class governance surface alongside policy, identity, and audit:

- **(a) Token budgets.** Per-agent and per-task budgets with hard ceilings and graceful degradation at the limit, not a silent stall and not an unbounded retry. The ceiling is enforced deterministically at the spine, the same way a deny is.
- **(b) Per-agent spend attribution.** Every token is traceable to an agent identity, reusing the same SPIFFE / DID / mTLS identity AGS already uses for action authorization (principle #2). "An agent spent it" is not cost accounting, the same way "an agent did it" is not incident response.
- **(c) Cost-aware model routing.** Route to the cheapest model that clears the task's quality bar; escalate model tiers only when the task demands it.
- **(d) Spend visibility and alerting.** Real-time budget burn, per-agent and per-task dashboards, and anomaly detection on runaway loops, with alerting to humans before the budget is exhausted.

This is the deterministic counterweight to "tokenmaxxing." Cost governance closes the loop between the safety posture of principles #1-#10 and operational economics: a runaway loop is caught by the same governance surface whether you frame it as a reliability problem or a spend problem.

**Implementation.** A consumption meter wraps the model and tool boundaries, attributing usage to the requesting agent identity and decrementing the per-agent and per-task budget on every call. Budget exhaustion is a policy outcome (deny or escalate), not an application-level exception swallowed by a retry loop. Spend and burn-rate metrics emit on the same OpenTelemetry path as the audit log; anomaly detection (sudden burn-rate spike, retry storm) triggers the same alerting and kill-switch machinery as an SLO breach (principle #6).

**Anti-pattern.** Treating cost as a billing-system afterthought reconciled monthly. Retry-without-backoff loops with no ceiling. A shared spend pool with no per-agent attribution. "We'll notice on the invoice." By then the runaway loop has already run.

Source convergence: MuleSoft's AI Gateway LLM Governance and UiPath's AI Trust Layer both treat token, cost, and data-flow as a governance surface, not a billing afterthought.

---

### 3.12: Human-in-the-loop approval gates

**Problem.** The deterministic gate of principle #1 returns allow, deny, or escalate. The escalate path implies a human, but explicit human-in-the-loop approval is not a first-class governance primitive in most deployments. Some action classes (irreversible operations, spend above a threshold, production mutations) should neither auto-execute nor be flatly denied. They should pause for human judgment. Without a named primitive for this, teams either over-deny (and the agent is useless) or auto-allow (and the agent is dangerous).

**Pattern.** Human-in-the-loop (HITL) approval gates are a first-class policy outcome alongside allow and deny. Deterministic policy can encode *"this action class requires human approval"* for an identified action class, principal, or context. The action is held, a human is notified, and the action executes only on explicit approval (or expires / is rejected). This is the governed bridge between autonomous action and human judgment: the machinery that lets an agent operate autonomously on the routine path while routing the irreversible, the expensive, and the high-blast-radius to a person.

The gate is policy-as-code (principle #4): the set of action classes requiring approval is versioned, lintable, testable, and PR-reviewed, not a hardcoded prompt or an operator's tribal memory. The approval, the approver's identity, and the latency to decision are all recorded in the tamper-evident audit log (principle #3).

**Implementation.** The policy engine returns a third decision, `require-approval`, in addition to allow and deny. The spine holds the action in a pending state, notifies the configured approver channel (a control-plane UI, a ticket, a chat approval), and resumes or aborts on the human's decision. The audit record captures who approved, when, and against which policy version. Approval timeouts default to deny. Examples of productized HITL gates: UiPath's Action Center, and the approval-gate layer practitioners describe as the top of the agent-harness oversight stack ("leave the branch for my morning review").

**Anti-pattern.** Encoding approval requirements in the system prompt ("ask the user before doing anything destructive"), which is principle-#1 trust collapse wearing a different hat. Approval gates with no audit of who approved. Approval timeouts that default to allow. A single global approver with no per-action-class scoping.

---

### 3.13: Purpose-based access control

**Problem.** Identity-based, role-based, attribute-based, and relationship-based access all answer *who* may do *what*. None of them record *why*. An agent acting on behalf of a user may be entitled to a tool or a dataset for one legitimate purpose and have no business touching it for another, yet a grant keyed only to identity and role cannot distinguish the two. When an auditor asks "why was this agent allowed to read this," the honest answer under identity-only access control is "because its role had the permission," which is not a justification, it is a tautology. The rationale for the grant is unrecorded, so the audit log can show *who* had access to *what* but never *why*.

**Pattern.** Access can be granted to a stated purpose, not only to a principal. A purpose is a declared, named reason for access (for example "supplier-risk-review" or "quarterly-close-reconciliation"), with the rationale recorded at grant and approval time. The agent or user requests access against a purpose, and the policy engine evaluates the requesting identity against that purpose: is this identity entitled to act for this purpose, and is the action it is taking consistent with the purpose it claimed. The purpose, the recorded rationale, and the identity it was evaluated against all land in the tamper-evident audit log (principle #3), so audit answers "why was this allowed," not just "who can see what." Purpose-based access is an additional dimension layered on top of identity (principle #2), not a replacement for it: identity still establishes *who*, purpose adds *why*, and the decision is conditioned on both.

This is the Palantir Foundry purpose-based-access pattern, where a user applies for access to a Purpose rather than to an individual dataset, the rationale is recorded at grant time, and access scopes are enforced for both humans and agents under automated lineage and auditing. The principle generalizes beyond any one platform: any access decision can be conditioned on, and audited against, a declared purpose.

**Implementation.** A purpose is a first-class object in the policy model: it has a name, an owner, a recorded rationale, and a set of identities entitled to act for it. The policy engine takes the purpose as part of the decision context (action, principal, purpose, context, policy), and a grant is the tuple of identity plus purpose plus rationale, not identity alone. Purpose definitions and grants are policy-as-code (principle #4): versioned, lintable, testable, PR-reviewed, with the same compile-and-verify discipline as the rest of the policy. Every decision records the purpose claimed, the rationale on file for the grant, and the identity it was evaluated against, on the same tamper-evident audit path as every other decision.

**Anti-pattern.** Access keyed to identity and role only, so the audit log can never answer "why." Purpose recorded as a free-text note the agent supplies at request time with no grant-time rationale to evaluate it against (the agent can claim any purpose). Purpose-based access that is not enforced for agents, only for humans, so the agent inherits a broad human grant with no purpose narrowing. Treating purpose as a label for reporting rather than a condition the policy engine actually evaluates.

---

### 3.14: Activation-layer defense-in-depth

**Problem.** Principle #1 moves governance from prompt-level hope to a deterministic gate, but that gate sits at the *output boundary*: it intercepts an action after the model has already formed the intent to take it. Two things live below that boundary, outside the gate's reach. First, the model's own safety alignment, its learned tendency to refuse, is not a property of the deterministic substrate; it is a direction in the model's weights, and on open-weight models it is cheaply removable. Refusal-direction ablation ("abliteration") strips a model's learned refusals with a rank-one weight edit and no retraining; an ordinary fine-tune can erode the same alignment as a side effect. Second, the deterministic gate sees *what* an agent requested, never the internal state that produced the request. A model whose safety directions have been ablated still transacts freely through the gate for every action the policy does not explicitly deny, and nothing in the substrate reads, measures, or governs the model's interior.

**Pattern.** Govern the model's activation space as a defense-in-depth layer *beneath* the deterministic gate, in two moves. **(a) Steer.** At inference, add a control vector, a direction in activation space extracted from behavior-contrast pairs, that clamps the model toward the compliant region so the denied intent is less likely to form in the first place (representation engineering; control vectors). **(b) Attest.** Before a model is promoted, measure whether its safety-relevant directions are intact: does it still refuse a known probe battery, is the refusal direction present and of expected magnitude, or has it been ablated. This is explicitly a *probabilistic* hardening and detection layer; it does **not** replace principle #1. The deterministic gate remains the floor, denied actions stay structurally impossible, and activation-layer control sits under it, lowering the rate at which the model reaches for a denied action and catching a model whose own floor has been removed. It is the missing position between "trust the model's compliance" (principle #1 rejects this) and "gate the output" (principle #1 does this): shape and verify the model's interior instead of only refereeing its outputs.

**Implementation.** Control vectors are extracted offline from a few dozen behavior-contrast pairs and applied at serve time with no retraining (repeng; the control-vector hooks in llama.cpp and comparable runtimes). Integrity attestation runs as a promotion check: the candidate model is probed for refusal on a fixed battery, and the presence and magnitude of the safety-relevant directions are recorded as a signed precondition for production. The attestation result threads into the risk substrate as a model-integrity signal (CRI) and is the natural white-box extension of a conformance battery (the Spine Gate), which otherwise tests only black-box input and output. This principle is the inference-time sibling of principle #10: governance-aware training bakes the policy prior into the weights; activation-layer defense-in-depth enforces and measures it at serve time, including on models whose training you did not control.

**Anti-pattern.** Assuming an open-weight or third-party model retains the alignment its lab shipped: abliteration is a weekend, and a fine-tune can strip it unintentionally. Treating activation steering as a *replacement* for the deterministic gate; it is stochastic, and betting the floor on a stochastic nudge is the same mistake as prompt-level safety (principle #1). Shipping a fine-tuned or externally-sourced model to production with no check that its safety directions survived training. Reading the model's interior for enforcement but never recording the integrity result where the risk index and the audit log can see it.

Source convergence: the refusal-direction result (a single mediating direction governs refusal across open-weight models) and the abliteration technique built on it; representation engineering and activation steering as a control surface; open control-vector tooling (repeng). The measure-and-hold framing composes with CRI (model integrity as a fused risk signal) and with the Spine Gate conformance battery (activation attestation as its white-box tier).

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
| Actions executed without consumption attribution | 0 | Every token is traceable to an agent identity. |
| Per-agent / per-task token budget enforcement | Hard ceiling, no unbounded retry | A runaway loop is a cost incident as well as a reliability one. |
| Runaway-loop / burn-rate anomaly detection | Alert before budget exhaustion | The invoice is too late. |
| Approval-required action classes auto-executed | 0 | HITL action classes pause for human judgment, never auto-allow. |
| Approval-gate timeout default | Deny | A pending approval that expires must not fall through to allow. |
| Compiled policy artifacts deployed without a verification pass | 0 | A natural-language rule compiled to formal policy is automated-reasoning-verified against the tool schema before it can be pinned to production. |
| Purpose-conditioned grants with no recorded rationale | 0 | Every purpose-based grant records why, so audit answers "why was this allowed," not just "who." |

---

## 5. Build sequence

AGS is built in the following sequence from skeleton to first reference deployment. Each step depends on the previous one. Pace varies by team and tooling; the sequence does not.

| Step | Deliverable | Why |
|---|---|---|
| 1 | Policy engine + first deterministic deny | One tool wrapped; one policy rule; allow / deny path exercised end-to-end |
| 2 | Audit log | Append-only, structured, written on every decision; queryable for post-hoc forensic |
| 3 | Agent identity | Every action carries verifiable agent-ID; cross-tenant identity isolation enforced |
| 4 | Tamper-evidence | Commitment anchoring on the audit log: hash chain or Merkle or signed batches |
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
| Flat permissions ("every agent can do everything if authorized") | Insecure or useless; binary choice | Privilege rings: tiered execution environments (principle #5) |
| No kill switch | Runaway agent stops when humans get around to it | Targeted O(seconds) stop for any agent ID (principle #6) |
| "We trust all tools in the marketplace" | Tool supply chain is a real threat surface | Hash pinning + hidden-instruction scanning + drift detection (principle #7) |
| Manual agent registration | Humans miss things; unregistered agents accumulate silently | Active discovery via process / config / repo scanning (principle #8) |
| One-time plugin trust vote | Trust degrades over time without continuous signal | Composite trust score with continuous inputs (principle #9) |
| Training agents to be compliant with users only | Runtime policy bears the full load; learning-at-runtime is friction | Governance-aware training where feasible (principle #10) |
| Ungoverned token spend reconciled on the invoice | A retry-without-backoff loop is a cost incident no one bounded | Per-agent budgets with hard ceilings and burn-rate alerting (principle #11) |
| Approval requirements encoded in the system prompt | Principle-#1 trust collapse wearing a different hat | Deterministic require-approval as a first-class policy outcome (principle #12) |
| Compiling natural-language rules to formal policy and enforcing without a verification pass | An over-permissive or unsatisfiable rule ships unnoticed | Automated-reasoning verification of the compiled artifact against the tool schema before deploy (principle #4) |
| Access keyed to identity and role only, with no recorded reason | Audit can answer "who" but never "why" | Purpose-based access: grant to a declared purpose with recorded rationale, evaluated against identity (principle #13) |

---

## 7. Compatibility with existing standards

AGS is compatible with, and built on top of, these standards:

- **OPA (Open Policy Agent)**: CNCF general-purpose policy engine; the reference implementation for principle #4
- **AWS Cedar**: verified analyzable authorization language; alternative for principle #4
- **OpenFGA (CNCF)**: Zanzibar-style relationship-based (ReBAC) authorization engine; a ReBAC variant for principle #1, suited to acting-on-behalf-of delegation chains
- **Cerbos**: stateless, language-agnostic policy decision point; a PDP-as-sidecar variant for principle #1
- **Permit.io**: commercial policy-as-code with explicit agent-governance framing
- **SPIFFE / SPIRE**: CNCF workload identity; reference for principle #2
- **W3C Decentralized Identifiers (DIDs) v1.0**: W3C Recommendation; alternative identity model for principle #2
- **e2b / Daytona**: OSS sandbox runtimes for agent-generated code; execution substrate for principle #5 (e2b for ephemeral microVMs, Daytona for persistent dev-environment state)
- **Anthropic self-hosted sandboxes cookbook**: per-session isolated sandboxes with environment-key credential isolation; substrate for principle #5
- **MCP server registry (modelcontextprotocol/servers)**: the tool-surface registry whose protocol principle #1 gates
- **Langfuse / Pydantic Logfire**: OTel-native trace fabrics feeding the principle #3 audit-log signal layer
- **Promptfoo / Inspect (UK AISI)**: production and sovereign-grade red-teaming and eval frameworks complementing the academic empirical case
- **OWASP LLM06:2025 (Excessive Agency)**: risk taxonomy framing
- **OWASP Agentic AI Threats and Mitigations** (Feb 2025): companion taxonomy
- **Microsoft Agent Governance Toolkit (AGT)**: the most mature productized implementation of the core principles
- **Anthropic "Zero Trust for AI Agents"**: buyer-facing zero-trust framework structurally equivalent to AGS; three-tier maturity model across identity, access, privilege scoping, resource boundaries, audit, and governance
- **MuleSoft Agent Fabric (Salesforce) / UiPath AI Trust Layer + Automation Ops**: major-vendor agent control planes productizing deterministic governance, identity, audit, LLM-usage / cost control (principle #11), and human-in-the-loop approval (principle #12, via Action Center)
- **AWS Bedrock AgentCore Policy + Identity**: AgentCore Policy compiles natural-language rules to Cedar, validates them against the tool schema with automated reasoning, and enforces them at the AgentCore Gateway by intercepting every tool call before it runs, outside the LLM loop; with AgentCore Identity (OAuth, IAM, custom claims) and Bedrock Guardrails, the most complete major-cloud productization of deterministic governance outside the model (Policy GA 2026-03-03)
- **Palantir Foundry + AIP**: enforces access scopes "for both humans and agents" through mandatory and discretionary controls (Markings, Organizations, granular policies) connected to automated lineage and auditing, with purpose-based access recording the rationale for each grant; a major-vendor instance of deterministic, identity-scoped, auditable agent governance, including the rationale-recorded audit pattern

AGS is also compatible with the companion specifications in the catalog:

- **[PDS (Progressive Discovery Spine)](https://github.com/drewmattie-code/Progressive-Discovery-Spine)**: single-agent tool discovery; PDS gateway sits on top of AGS substrate.
- **[ACS (Adversarial Coordination Spine)](https://github.com/drewmattie-code/Adversarial-Coordination-Spine)**: multi-agent coordination; every cross-agent handoff is governed by AGS.
- **[ESF (External Signal Fabric)](https://github.com/drewmattie-code/External-Signal-Fabric)**: external signals; AGS governs which agents can subscribe to which signal classes.
- **CRI (Composite Risk Index)**: composite risk scoring (private); AGS principle #9 (plugin trust scoring) is a CRI-shaped fusion at the agent / tool layer.
- **[DCS (Durable Context Spine)](https://github.com/drewmattie-code/Durable-Context-Spine)**: durable state and memory across sessions and time. The same per-agent identity AGS uses to authorize *actions* scopes DCS *memory* (identity-partitioned durable state), and the AGS tamper-evident audit log covers durable-memory writes, not just actions.
- **GDS (Grounded Data Spine)** *(private)*: a canonical semantic model (text-to-metric) plus data-level entitlements.
- **ARS (Agent Registry Spine)** *(private)*: the system of record layer for every agentic asset that discovery reads from and governance enforces against.
- **SRS (Sovereign Runtime Spine)** *(private)*: the execution substrate, the sovereign first-party agent runtime that first-party agents run on (outside agents and tools plug into the spine; first-party agents run on SRS).

---

## 8. The ten-way failure attribution principle

AGS owns the **bad governance** surface in the catalog's failure-attribution dictionary. As the catalog has grown to nine specs (PDS, ACS, ESF, CRI, AGS, DCS, GDS, ARS, SRS), the dictionary has grown to **ten** attribution surfaces:

| Attribution | Owned by | "Failure looked like..." |
|---|---|---|
| Bad customer / tool data | PDS | Wrong supplier ID, stale internal cache, missing record |
| Bad world data | ESF | Expired signal, mis-tagged advisory, broken adapter |
| Bad reasoning | ACS Planner | Plan unsupported by signals |
| Bad evaluation | ACS Evaluator | Rubber-stamped contract violation |
| Bad scoring | CRI | Confident score on insufficient inputs |
| **Bad governance** | **AGS** | **Policy gap (action wasn't denied because no rule covered it), identity ambiguity (we know an agent did it but not which), audit gap (no record exists), policy drift (deployed policy differs from approved policy)** |
| Bad continuity | DCS | State or memory lost, stale, or mis-scoped across sessions and time |
| Bad grounding | GDS | Metric resolved to the wrong semantic definition, or an entitlement boundary leaked |
| Bad or missing registry | ARS | An agentic asset was never inventoried, so discovery could not surface it and governance could not enforce against it |
| Bad or unbounded execution | SRS | A first-party agent ran on an untrusted or unbounded runtime, so execution escaped sovereign control |

Within AGS itself, bad governance decomposes further: policy-coverage gap, identity-attestation gap, audit-tamper failure, tool-supply-chain compromise, shadow-agent presence, unbounded consumption, a missing approval gate, an unverified compiled-policy artifact, and a purpose-unrecorded access grant. The ten-attribution model makes any catalog-grade system failure locatable to a single ownable layer.

---

## 9. References

### Policy + identity foundations
- Open Policy Agent (CNCF): [openpolicyagent.org/docs](https://www.openpolicyagent.org/docs/)
- AWS Cedar: [docs.cedarpolicy.com](https://docs.cedarpolicy.com/) · Cedar paper [arXiv:2403.04651](https://arxiv.org/pdf/2403.04651)
- OpenFGA (CNCF): [github.com/openfga/openfga](https://github.com/openfga/openfga)
- Cerbos: [github.com/cerbos/cerbos](https://github.com/cerbos/cerbos)
- Permit.io: [permit.io](https://www.permit.io/)
- SPIFFE / SPIRE (CNCF): [spiffe.io](https://spiffe.io/docs/latest/spiffe-about/overview/)
- W3C Decentralized Identifiers (DIDs) v1.0: [w3.org/TR/did-core](https://www.w3.org/TR/did-core/)

### Sandbox + execution substrate
- e2b: [github.com/e2b-dev/e2b](https://github.com/e2b-dev/e2b)
- Daytona: [github.com/daytonaio/daytona](https://github.com/daytonaio/daytona)
- Anthropic, *self-hosted sandboxes cookbook*: [github.com/anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks/tree/main/managed_agents/self_hosted_sandboxes)

### Tool surface + audit substrate
- MCP server registry: [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- Langfuse: [github.com/langfuse/langfuse](https://github.com/langfuse/langfuse)
- Pydantic Logfire: [github.com/pydantic/logfire](https://github.com/pydantic/logfire)

### Productized governance kernels and control planes
- Microsoft, *Agent Governance Toolkit*: [github.com/microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)
- Composio: [github.com/ComposioHQ/composio](https://github.com/ComposioHQ/composio)
- Anthropic, *Zero Trust for AI Agents* (2026): [anthropic.com](https://www.anthropic.com/)
- MuleSoft Agent Fabric (Salesforce): [mulesoft.com/ai/agent-fabric](https://www.mulesoft.com/ai/agent-fabric)
- UiPath AI Trust Layer: [docs.uipath.com](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/about-ai-trust-layer)
- AWS Bedrock AgentCore Policy: [docs.aws.amazon.com](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
- Palantir Foundry security overview: [palantir.com/docs/foundry/security/overview](https://www.palantir.com/docs/foundry/security/overview)

### Empirical case for deterministic enforcement
- Chao et al., *JailbreakBench* (NeurIPS 2024): [arXiv:2404.01318](https://arxiv.org/abs/2404.01318)
- Andriushchenko, Croce, Flammarion, *Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks* (ICLR 2025): [arXiv:2404.02151](https://arxiv.org/abs/2404.02151)
- Microsoft AI Red Team, *3 Takeaways from Red Teaming 100 Generative AI Products* (Jan 2025): [microsoft.com](https://www.microsoft.com/en-us/security/blog/2025/01/13/3-takeaways-from-red-teaming-100-generative-ai-products/)
- Promptfoo: [github.com/promptfoo/promptfoo](https://github.com/promptfoo/promptfoo)
- Inspect (UK AI Security Institute): [github.com/UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai)

### Practitioner convergence
- OpenAI, *Codex harness engineering*: [openai.com](https://openai.com/index/harness-engineering/)
- Av1d, *How to Build Multi-Agent Workflows* (2026): [@Av1dlive]

### OWASP risk taxonomy
- OWASP LLM06:2025, *Excessive Agency*: [genai.owasp.org](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- OWASP, *Agentic AI Threats and Mitigations* (Feb 2025): [genai.owasp.org](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)

### Catalog peers
- Progressive Discovery Spine: [github.com/drewmattie-code/Progressive-Discovery-Spine](https://github.com/drewmattie-code/Progressive-Discovery-Spine)
- Adversarial Coordination Spine: [github.com/drewmattie-code/Adversarial-Coordination-Spine](https://github.com/drewmattie-code/Adversarial-Coordination-Spine)
- External Signal Fabric: [github.com/drewmattie-code/External-Signal-Fabric](https://github.com/drewmattie-code/External-Signal-Fabric)
- Composite Risk Index: *(private — normative summary available on request)*
- Durable Context Spine: [github.com/drewmattie-code/Durable-Context-Spine](https://github.com/drewmattie-code/Durable-Context-Spine)
- Grounded Data Spine *(private)*: a canonical semantic model (text-to-metric) plus data-level entitlements
- Agent Registry Spine *(private)*: the system of record layer for every agentic asset that discovery reads from and governance enforces against
- Sovereign Runtime Spine *(private)*: the execution substrate, the sovereign first-party agent runtime that first-party agents run on (outside agents and tools plug into the spine; first-party agents run on SRS)

---

## 10. Versioning

This specification follows semantic versioning. Breaking changes to the conceptual model bump the major version; new principles or refinements bump the minor. Editorial fixes bump the patch.

- **v0.1-draft**: initial draft (2026-05-26). Triggered by Microsoft Agent Governance Toolkit release. Internal review.
- **v1.0**: first public release under CC BY 4.0 + MIT (2026-05-28).
- **v1.1** (2026-06-02): added four principles across three same-day consolidations, bringing the count from ten to thirteen: #11 (cost and consumption governance), #12 (human-in-the-loop approval gates), #13 (purpose-based access control, the Palantir Foundry purpose-based-access pattern: an entitlement granted to a declared purpose with recorded rationale, evaluated against the requesting identity and audited against the purpose). Enriched principle #1 (deterministic enforcement co-located with the tool-mediation chokepoint, the same point PDS uses for discovery — AgentCore Policy enforced at the AgentCore Gateway) and principle #4 (natural-language-front, formal-language-back policy authoring with an automated-reasoning verification pass on the compiled artifact before deploy). Added SRS (Sovereign Runtime Spine) as the ninth spec — the private/forthcoming execution substrate that first-party agents run ON (outside agents and tools plug INTO the spine) — taking the catalog to nine specs and the failure-attribution dictionary to ten-way ("bad or unbounded execution → SRS"). Added convergence citations: Anthropic "Zero Trust for AI Agents", MuleSoft Agent Fabric, UiPath AI Trust Layer, OpenFGA, Cerbos, e2b, Daytona, Composio, MCP server registry, Langfuse, Pydantic Logfire, Promptfoo, Inspect (UK AISI), the OpenAI Codex harness, the Anthropic self-hosted sandboxes cookbook, the Av1d multi-agent workflows field guide, AgentCore Policy, and Palantir purpose-based access. Added the DCS composition cross-reference. *(Editorial note, 2026-07-16: three same-day v1.1 entries consolidated into this one per the semver policy above; content unchanged.)*
- **v1.2** (2026-06-08): added two convergence citations to the README industry-context section. Microsoft eXecution Container (MXC), a Microsoft-backed instance of principle #5 (sandboxed execution as a resource boundary, alongside e2b and Daytona), from the same vendor as the Agent Governance Toolkit citation. And goose, the open-source agent runtime now stewarded by the Linux Foundation's Agentic AI Foundation, as the OSS local-runtime permission-gating substrate AGS enforces against. No principle changes; catalog stays nine specs, attribution ten-way.
- **v1.3** (2026-07-12): added principle #14 (activation-layer defense-in-depth), bringing the count to fourteen. Governs the model's activation space as a probabilistic hardening and integrity-attestation layer beneath the deterministic gate of principle #1: control-vector steering toward the compliant region at inference, and refusal-direction integrity attestation as a promotion precondition. Motivated by the refusal-direction / abliteration result that a model's learned safety is a cheaply-removable direction in open weights, which the output-boundary gate cannot see. Composes with principle #10 (train-time governance prior) as its inference-time sibling, threads a model-integrity signal into CRI, and defines the white-box tier of the Spine Gate conformance battery. Added refusal-direction ablation, representation engineering, and control-vector tooling to the convergence citations. Catalog stays nine specs; principle count fourteen.

---

## 11. Author

[Drew Mattie](https://www.linkedin.com/in/drew-mattie-88084826/) · SaaSquach AI Labs (a division of Charles & Roe Inc.) · 2026

AGS was developed at SaaSquach AI Labs (a division of Charles & Roe Inc.) as the fifth specification in the agent-architecture catalog alongside PDS, ACS, ESF, and CRI. This specification is released as open documentation under [CC BY 4.0](LICENSE-CC-BY-4.0) so the pattern can be adopted, adapted, and built upon, with attribution.
