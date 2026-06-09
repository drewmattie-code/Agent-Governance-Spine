<div align="center">

# Agent Governance Spine

**The protocol-layer substrate where AI agents are governed deterministically, not asked to behave. Policy enforcement, per-agent identity, and tamper-evident audit applied to every agent action BEFORE the model's intent reaches the wire. Production patterns for agent systems that must survive an audit, a regulator, or a post-mortem.**

[![License: CC BY 4.0](https://img.shields.io/badge/spec-CC_BY_4.0-blue?style=flat-square)](LICENSE-CC-BY-4.0)
[![License: MIT](https://img.shields.io/badge/code-MIT-green?style=flat-square)](LICENSE-MIT)
[![Status: v1.2](https://img.shields.io/badge/status-v1.2-0F766E?style=flat-square)](SPEC.md)
[![Catalog: 5th spec](https://img.shields.io/badge/catalog-5th_spec-7C3AED?style=flat-square)](#catalog)

</div>

---

> **Draft:** Drew Mattie · SaaSquach AI Labs (a division of Charles & Roe Inc.) · 2026

# What this is

AGS is a pattern for the layer that **governs** AI agents: the protocol-layer substrate where every agent action passes through deterministic policy enforcement, carries verifiable per-agent identity, and lands in a tamper-evident audit log. Whether one agent or one hundred, whether one tool or one thousand: every action goes through the spine before it reaches anything that can change state in the world.

Most production agent systems today rely on prompt-level safety as their primary control surface. *"Please don't drop the table."* *"Only send emails to verified recipients."* *"Refuse unauthorized operations."* This is a polite request to a stochastic system.

The empirical record is unambiguous. On JailbreakBench (Chao et al., NeurIPS 2024), the standard open robustness benchmark, adaptive attacks reach **near-100% attack success rates** against frontier safety-aligned models. Andriushchenko et al. (ICLR 2025) report 100% ASR on GPT-4, GPT-3.5, Claude 3, Llama-3, Gemma-7B, and a dozen other frontier models using simple prompt-only attacks. Microsoft's own AI Red Team, after red-teaming 100 generative AI products, concludes that *"AI red teaming is a continuous process that should adapt to the rapidly evolving risk landscape"*. Model-layer defenses are probabilistic by construction.

AGS does not try to win that fight inside the prompt. Every tool call, message send, and delegation is intercepted in deterministic application code **before** the model's intent reaches the wire. Actions the spine denies are not "unlikely." They are **structurally impossible**.

That is the difference between asking an agent to behave and making it incapable of misbehaving.

# Why it exists

Four failure modes recur across production agent deployments. AGS addresses them by enforcing structurally rather than asking nicely.

1. **Prompt-layer trust collapse.** Relying on the model's compliance instead of deterministic policy. The empirical case is closed: prompt-layer defenses leak double-digit residual attack success rate on frontier models.
2. **Identity blur.** In a multi-agent system, five agents might share a single API key. When something goes wrong, *"an agent did it"* is not an incident response. You cannot improve what you cannot attribute.
3. **Audit gap.** No tamper-evident record of what policy was active, what the agent requested, and why it was allowed or denied. Auditors cannot certify. SOC 2 / ISO 27001 / regulators cannot sign off.
4. **Policy drift.** Policy lives in prose, in tribal knowledge, or in stale config files. Not in versioned, lintable, testable code. The actual behavior of the system diverges from what was approved, and no one notices until an incident.

AGS is the implementation pattern that addresses all four, by enforcing policy as code, anchoring identity per agent, recording every decision tamper-evidently, and treating governance as protocol-layer infrastructure rather than prompt-layer hope.

# Architecture

```mermaid
flowchart TD
    A[AI Agent]
    B[Policy Engine<br/>OPA · Cedar · custom]
    C[Identity Layer<br/>SPIFFE · DID · mTLS]
    D[Audit Log<br/>tamper-evident · commitment-anchored]
    E[Privilege Rings<br/>sandboxed execution]
    F[Tool / Action / Delegation]

    A -->|requested action| B
    A -.->|attested identity| C
    C --> B
    B -->|allow| E
    B -->|deny| G[GovernanceDenied]
    E --> F
    B --> D
    G --> D
    F --> D

    style B fill:#0F766E,color:#fff
    style C fill:#0F766E,color:#fff
    style D fill:#7C3AED,color:#fff
    style E fill:#0F766E,color:#fff
    style G fill:#DC2626,color:#fff
```

Every arrow into a tool, every message between agents, every delegation: routed through the spine. Allowed actions execute in scoped sandboxes. Denied actions never execute. Every decision is recorded.

# Where AGS fits in the catalog

AGS is the **fifth specification** in the SaaSquach AI Labs architectural catalog, which now spans nine specs. It sits as a peer governance-substrate alongside the data/coordination layers:

```
┌──────────────────────────────────────────────────────────┐
│ User · Product · Operator                                 │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│ ACS - Adversarial Coordination Spine                      │  ← multi-agent
└──────┬───────────────────────────────────┬───────────────┘
       ↓                                   ↓
┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│ PDS          │  │ ESF             │  │ CRI          │
│ tool         │  │ external signal │  │ composite    │
│ discipline   │  │ fabric          │  │ scoring      │
└──────┬───────┘  └──────┬──────────┘  └──────┬───────┘
       ↓                 ↓                    ↓
┌──────────────────────────────────────────────────────────┐
│ AGS - Agent Governance Spine                              │  ← THIS spec
│ deterministic policy · identity · tamper-evident audit   │
└──────────────────────────┬───────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│ DCS - Durable Context Spine                               │  ← durable state
│ state and memory across sessions and time                 │
└──────────────────────────┬───────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│ Model Context Protocol (MCP)                              │
└──────────────────────────┬───────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│ Backends · External APIs · Data Stores                    │
└──────────────────────────────────────────────────────────┘
```

PDS, ACS, ESF, CRI describe *how data and coordination flow through* an agent system; DCS describes *what persists across sessions and time*. AGS describes *what is allowed and recorded*. Every action that any of those layers initiate passes through the AGS spine before it can change anything in the world.

The catalog now spans nine specs. Three private/forthcoming siblings round it out: **GDS (Grounded Data Spine)**, a canonical semantic model (text-to-metric) plus data-level entitlements; **ARS (Agent Registry Spine)**, the system of record layer for every agentic asset that discovery reads from and governance enforces against; and **SRS (Sovereign Runtime Spine)**, the execution substrate, the sovereign first-party agent runtime that first-party agents run ON (outside agents and tools plug INTO the spine; first-party agents run on SRS). See the [Catalog](#catalog) section for the full nine-spec listing.

AGS composes directly with DCS, the durable-state sibling. The same per-agent identity AGS uses to authorize *actions* scopes DCS *memory* (identity-partitioned durable state), and the AGS tamper-evident audit log covers durable-memory writes, not just actions. Bad governance is an AGS failure; bad continuity is a DCS failure.

# The 13 principles

| # | Principle | The shift |
|---|---|---|
| 01 | **Deterministic policy enforcement at the tool-mediation chokepoint** | Every action is denied or allowed in application code BEFORE the model's intent reaches the wire. Not "the model said no." Not "the system prompt warns against it." Structurally impossible to execute. Enforced at the same chokepoint that discovers and hands tools to the agent (the PDS gateway), so discovery and governance share one point (AgentCore Policy at the AgentCore Gateway). |
| 02 | **Identity per agent, not per session** | Every agent has a stable cryptographic identity (SPIFFE / DID / mTLS). "An agent did it" is never an acceptable answer. |
| 03 | **Tamper-evident audit log** | Every decision (allow, deny, escalate) is recorded in an append-only, commitment-anchored audit log. SOC 2 / ISO 27001 / regulator-defensible. |
| 04 | **Policy as code, authored and validated, not as prose** | YAML / OPA / Cedar / equivalent. Versioned, lintable, testable, reviewable. Never in the system prompt; never in tribal knowledge. Authoring can be natural-language-front, formal-language-back: state the rule in natural language, compile it to a formal policy language, and machine-verify the compiled artifact (automated reasoning against the tool schema) before it is enforced (AgentCore Policy). |
| 05 | **Privilege rings, not flat permissions** | Agent execution is sandboxed in tiered privilege rings. Low-trust agents cannot reach high-trust resources by accident or by design. |
| 06 | **Kill switch + SLO monitoring + chaos testing** | Every deployed agent is monitored against an SLO and reachable by a human-operated kill switch. Chaos testing of the governance layer itself, not just the agents. |
| 07 | **Tool poisoning detection + drift monitoring** | The tool supply chain is itself a threat surface. Hidden instructions, typosquatting, drift between authored manifest and runtime behavior all detected at the spine. |
| 08 | **Shadow agent discovery** | Unregistered agents are a real production risk. The spine includes active discovery for processes, configs, and repos. |
| 09 | **Trust scoring for plugin marketplaces** | Composite agent-trust score at the marketplace level. Different from CRI's customer-decision-level scoring. This is agent-level reputation. |
| 10 | **Governance-aware training** | If you control post-training, the model is trained with violation penalties (RL-style). Agents that learn to respect the policy substrate are cheaper to govern at runtime. |
| 11 | **Cost and consumption governance** | Token consumption, spend, and data-flow volume are a first-class governance surface alongside policy, identity, and audit. Per-agent token budgets with hard ceilings, spend attributed to agent identity, cost-aware model routing, and runaway-loop alerting. |
| 12 | **Human-in-the-loop approval gates** | Deterministic policy can require human approval or escalation for an action class. The governed bridge between autonomous action and human judgment, sitting alongside allow and deny as a first-class decision. |
| 13 | **Purpose-based access control** | Beyond identity, role, attribute, and relationship, an entitlement can be granted to a declared purpose, with the rationale recorded per grant and evaluated against the requesting identity. Audit answers "why was this allowed," not just "who" (Palantir Foundry purpose-based access). |

Full discussion of each principle, with problems, patterns, and implementation notes, lives in [SPEC.md](SPEC.md).

# The failure attribution dictionary, now ten-way

As the catalog has grown to nine specs, the failure-attribution dictionary has grown with it. AGS owns the **bad governance** surface. The full dictionary is now **ten-way**:

| Attribution | Owned by | "Failure looked like..." |
|---|---|---|
| Bad customer / tool data | PDS | Wrong supplier ID, stale internal cache, missing record |
| Bad world data | ESF | Expired signal, mis-tagged advisory, broken adapter |
| Bad reasoning | ACS Planner | Plan unsupported by signals |
| Bad evaluation | ACS Evaluator | Rubber-stamped contract violation |
| Bad scoring | CRI | Confident score on insufficient inputs |
| **Bad governance** | **AGS** | **Policy gap (action wasn't denied because no rule covered it), identity ambiguity (we know an agent did it but not which), audit gap (no record exists), or policy drift (deployed policy differs from approved policy)** |
| Bad continuity | DCS | State or memory lost, stale, or mis-scoped across sessions and time |
| Bad grounding | GDS | Metric resolved to the wrong semantic definition, or an entitlement boundary leaked |
| Bad or missing registry | ARS | An agentic asset was never inventoried, so discovery could not surface it and governance could not enforce against it |
| Bad or unbounded execution | SRS | A first-party agent ran on an untrusted or unbounded runtime, so execution escaped sovereign control |

This ten-attribution dictionary is the meta-architectural contribution of the full SaaSquach AI Labs catalog. Build, measure, and own each surface separately.

# Industry context: convergence on the same pattern

AGS is not a novel invention. It is a formalization of a pattern that policy-engine vendors, identity-protocol authors, and major-vendor governance platforms have independently converged on. The pattern crystallized as agent deployments crossed the threshold where adversarial robustness became a customer-blocking concern. AGS synthesizes that convergence into a single referenceable specification.

## Foundational policy + identity layers (the building blocks AGS sits above)

**Open Policy Agent (CNCF graduated).** The canonical general-purpose policy engine: *"The Open Policy Agent (OPA, pronounced 'oh-pa') is an open source, general-purpose policy engine that unifies policy enforcement across the stack."* [Source](https://www.openpolicyagent.org/docs/)

**AWS Cedar Policy Language.** The canonical language for verified analyzable authorization: *"Cedar is a language for writing authorization policies and making authorization decisions based on those policies."* Peer-reviewed (Cedar paper, arXiv:2403.04651). [Source](https://docs.cedarpolicy.com/)

**Permit.io.** Commercial policy-as-code platform with explicit agent-governance framing: *"Permit.io unifies policy, delegation, approvals, trust, and audit into one action-time policy fabric, for humans, services, and AI agents."* [Source](https://www.permit.io/)

**SPIFFE (CNCF).** Workload identity standard: *"Systems that adopt SPIFFE can easily and reliably mutually authenticate wherever they are running."* [Source](https://spiffe.io/docs/latest/spiffe-about/overview/)

**W3C Decentralized Identifiers (DIDs) v1.0.** W3C Recommendation: *"DIDs are designed so that they may be decoupled from centralized registries, identity providers, and certificate authorities."* [Source](https://www.w3.org/TR/did-core/)

**OpenFGA (CNCF), a Zanzibar-style ReBAC alternative to OPA/Cedar.** CNCF-graduated relationship-based authorization engine implementing Google's Zanzibar paper. Adds a ReBAC architectural variant to AGS principle #1's existing OPA + Cedar (ABAC) citations: ReBAC maps more naturally to agent-acting-on-behalf-of-user delegation chains than attribute-based policy. [Source](https://github.com/openfga/openfga)

**Cerbos, a stateless ABAC PDP variant.** Stateless, language-agnostic policy decision point with first-class principal/resource/action model. A PDP-as-sidecar architectural variant for AGS principle #1 alongside OPA (stateful PDP) and AWS Cedar (in-process). [Source](https://github.com/cerbos/cerbos)

## Productized governance kernels (proof that the pattern is shippable)

**Microsoft, Agent Governance Toolkit.** Microsoft's MIT-licensed multi-language governance kernel for autonomous AI agents. Covers OWASP Agentic Top 10 10/10. Productizes deterministic policy enforcement, SPIFFE/DID/mTLS identity, tamper-evident audit: *"Actions the AGT kernel denies are not 'unlikely.' They are structurally impossible."* Microsoft anchors the empirical case in JailbreakBench and concludes that prompt-layer defenses leak double-digit residual ASR. [Source](https://github.com/microsoft/agent-governance-toolkit)

**MuleSoft Agent Fabric (Salesforce).** Salesforce's enterprise agent control plane productizes deterministic agent governance: the Agent Governance component (via Omni Gateway) applies policy, identity, and audit to every agent action with MCP and Agent2Agent protocol support, and an AI Gateway adds token/cost/data-flow governance for third-party models. A major-vendor instance of AGS at the gateway layer. [Source](https://www.mulesoft.com/ai/agent-fabric)

**UiPath AI Trust Layer + Automation Ops.** Centralized control, security, and observability for UiPath-managed and third-party LLM usage, plus program and agent governance policies, identity, and audit, with human-in-the-loop approvals via Action Center. A major-vendor instance of deterministic agent governance with first-class LLM-usage control. [Source](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/about-ai-trust-layer)

**AWS Bedrock AgentCore Policy + Identity (the most complete major-cloud productization).** AWS Bedrock AgentCore Policy compiles natural-language rules to Cedar, validates them against the tool schema with automated reasoning, and enforces them at the AgentCore Gateway by intercepting every tool call before it runs, outside the LLM reasoning loop, deterministically regardless of how an agent or malicious prompt reasons around the constraint. With AgentCore Identity (OAuth, IAM, custom claims) and Bedrock Guardrails, this is the most complete major-cloud productization of the deterministic-governance-outside-the-model thesis AGS describes (AWS, Policy GA 2026-03-03). [Source](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)

**Palantir Foundry + AIP, access scopes for humans and agents.** Palantir Foundry and AIP enforce access scopes "for both humans and agents" through mandatory and discretionary controls (Markings, Organizations, granular policies) connected to automated lineage and auditing, with purpose-based access recording the rationale for each grant. A major-vendor instance of deterministic, identity-scoped, auditable agent governance, including the rationale-recorded audit pattern. [Source](https://www.palantir.com/docs/foundry/security/overview)

**Composio, productized identity-per-tool.** Commercial tool platform with per-toolkit auth and sandboxed workbench. Productizes AGS principle #2 (identity per agent) and #5 (privilege rings) at the tool-platform layer: citable as the commercial example of identity-bound tool access that AGS prescribes at the protocol layer. [Source](https://github.com/ComposioHQ/composio)

## Sandbox and execution substrate (the resource-boundary building blocks)

**e2b, an OSS Firecracker-microVM sandbox for agent code.** Open-source execution runtime purpose-built for AI-agent-generated code, providing sub-second sandboxed environments with mTLS-identity hooks. The canonical OSS productization of AGS principle #5 (privilege rings): where Microsoft AGT supplies the four-ring reference architecture, e2b supplies the OSS execution substrate. [Source](https://github.com/e2b-dev/e2b)

**Daytona, a persistent-state sandbox sibling to e2b.** Elastic, secure infrastructure for AI-generated code with sub-second sandbox starts and persistent dev-environment state. The "dev-environment-grade" four-ring sandbox option for AGS principle #5 when agent workloads outlive a single execution. [Source](https://github.com/daytonaio/daytona)

**Anthropic, self-hosted sandboxes cookbook.** Per-session isolated sandboxes (Docker / Cloudflare / Modal / Daytona / Vercel variants) with environment-key credential isolation so no org API key reaches the runner. The sandbox-execution substrate for AGS principle #5 (resource boundaries). [Source](https://github.com/anthropics/claude-cookbooks/tree/main/managed_agents/self_hosted_sandboxes)

## Tool-surface and audit substrate (what AGS gates and what feeds its audit)

**modelcontextprotocol/servers, the protocol surface AGS gates.** The reference catalog of MCP servers; AGS principle #1 (deterministic policy at the tool boundary) operates on the protocol MCP defines. AGS-compliant deployments enforce policy on this registry's surface. [Source](https://github.com/modelcontextprotocol/servers)

**Langfuse, an OSS trace fabric feeding AGS audit.** OTel-native LLM/agent observability with trace storage, eval, and prompt management. AGS principle #3 (tamper-evident audit) consumes Langfuse-grade trace data as upstream input; Langfuse is the OSS substrate for the audit-log signal layer. [Source](https://github.com/langfuse/langfuse)

**Pydantic Logfire, a typed audit substrate.** Pydantic-validated OTel observability; the Pydantic-typed trace payload is a clean OSS implementation of the typed-audit-record contract AGS principle #3 specifies. [Source](https://github.com/pydantic/logfire)

## Empirical case for deterministic enforcement (why prompt-level is insufficient)

**JailbreakBench (Chao et al., NeurIPS 2024).** Standard open robustness benchmark: *"Jailbreak attacks cause large language models (LLMs) to generate harmful, unethical, or otherwise objectionable content."* Adaptive attacks against frontier safety-aligned models reach near-100% attack success rates. [arXiv:2404.01318](https://arxiv.org/abs/2404.01318)

**Andriushchenko, Croce, Flammarion (ICLR 2025).** Simple adaptive attacks against leading safety-aligned LLMs: *"we achieve 100% attack success rate... on Vicuna-13B, Mistral-7B, Phi-3-Mini, Nemotron-4-340B, Llama-2-Chat-7B/13B/70B, Llama-3-Instruct-8B, Gemma-7B, GPT-3.5, GPT-4o."* 100% on Claude via transfer or prefilling. [arXiv:2404.02151](https://arxiv.org/abs/2404.02151)

**Microsoft AI Red Team (Jan 2025).** After red-teaming 100 generative AI products: *"AI red teaming is a continuous process that should adapt to the rapidly evolving risk landscape."* Model-layer defenses are probabilistic by construction. [Source](https://www.microsoft.com/en-us/security/blog/2025/01/13/3-takeaways-from-red-teaming-100-generative-ai-products/)

**Promptfoo, the production red-teaming counterpart to academic AGS citations.** Used by OpenAI and Anthropic for prompt/agent eval, red-teaming, and vulnerability scanning. Complements AGS's academic empirical citations (JailbreakBench, Andriushchenko ICLR 2025) with the production-deployed eval and red-teaming framework that frontier labs actually use. [Source](https://github.com/promptfoo/promptfoo)

**Inspect (UK AI Security Institute).** Sovereign-grade LLM eval framework: the framework UK AISI and US AISI use for frontier-model assessments. Complements AGS's academic empirical citations (JailbreakBench, Andriushchenko ICLR 2025) with sovereign-government-agency-grade institutional credibility. [Source](https://github.com/UKGovernmentBEIS/inspect_ai)

**Microsoft eXecution Container (MXC).** A sandboxed code-execution system for running untrusted code (model output, plugins, tools) across Windows, Linux, and macOS, with policy-driven isolation (filesystem, network, UI) and pluggable backends (Windows Sandbox, LXC, Bubblewrap, macOS Seatbelt, VMs). A Microsoft-backed instance of AGS principle #5 (sandboxed execution as a resource boundary), alongside e2b and Daytona, from the same vendor that supplies AGS's Agent Governance Toolkit citation. [Source](https://github.com/microsoft/mxc)

**goose (Agentic AI Foundation / Linux Foundation).** The open-source agent runtime, now stewarded by the Linux Foundation's Agentic AI Foundation alongside MCP and AGENTS.md, ships runtime-level permission and approval controls (ask-before-execute, allowlists, mode gating). That is a permission-gating primitive at the "ask the human" altitude; AGS is the deterministic enterprise layer above any such runtime, formalizing it into deterministic policy, per-agent identity, and tamper-evident audit. The OSS local-runtime substrate AGS enforces against. [Source](https://github.com/aaif-goose/goose)

## Buyer-facing and practitioner convergence (the pattern stated by others)

**Anthropic, "Zero Trust for AI Agents" eBook (2026).** Anthropic's buyer-facing zero-trust framework for AI agents is, structurally, AGS articulated for the enterprise buyer. Its core design test, *"does this make the attack impossible, or just tedious?"*, is AGS's "structurally impossible, not unlikely." It lays out a three-tier maturity model (Foundation / Enterprise / Advanced) across agent identity and auth, service auth, access control (RBAC deny-by-default through ABAC to continuous authorization), privilege scoping (static through dynamic to just-in-time), resource boundaries (identity isolation through sandboxed-per-agent to hardware/confidential-compute/microVM), observability and audit, behavioral monitoring, automated response, input validation, integrity and recovery, and AI governance, with an eight-phase agent implementation workflow. The strongest single AGS convergence citation available. [Source](https://www.anthropic.com/)

**OpenAI Codex harness, mechanical invariant enforcement.** In a roughly 1M-line agent-generated codebase, architectural invariants (dependency directions, layer boundaries) are enforced by custom linters and structural tests with agent-readable remediation messages, not human review. AGS principle #1 (deterministic policy enforcement) rendered at the code-architecture layer: the constraint is mechanical, immediate, and at the point of violation. [Source](https://openai.com/index/harness-engineering/)

**Multi-agent workflows field guide (Av1d, 2026), Governance Layer.** A practitioner synthesis whose governance module independently codifies AGS: per-agent permission scoping (read-only vs path-scoped write), human-in-the-loop gates for irreversible actions, agent-ID-tagged replayable audit trails, and blast-radius limits, framed as *"the governance layer is what separates a demo from a production system."* Adds field-named failure modes (silent substitution, scope creep) and a deterministic error-handling rule (*"never substitute placeholder data; report and halt"*) as concrete instances of AGS deterministic enforcement. [Source: @Av1dlive, How to Build Multi-Agent Workflows]

## OWASP risk taxonomy

**OWASP LLM06:2025, Excessive Agency.** The canonical OWASP risk taxonomy entry for agent action-space governance: *"An LLM-based system is often granted a degree of agency by its developer, the ability to call functions or interface with other systems."* [Source](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) · Companion: [OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) (Feb 2025).

## What AGS contributes

The sources above document INDIVIDUAL implementations and isolated primitives. AGS contributes:

1. A unified set of **13 principles** mapped to documented failure modes
2. **Target SLAs** for production governance readiness
3. An **8-step build sequence** from skeleton to first reference deployment
4. **Anti-patterns** to avoid
5. A **portable, citable specification** under CC BY 4.0: adopt, adapt, build commercial products on top, with attribution
6. **Explicit composition with PDS, ACS, ESF, CRI, and DCS**: the ten-way failure attribution dictionary the nine-spec catalog enables

If your team is independently converging on this pattern (as Microsoft, Anthropic, MuleSoft, UiPath, OPA, Cedar, SPIFFE, Permit.io and others already have), AGS gives you a vocabulary, a checklist, and a published artifact you can hand to your regulators / auditors / customers.

# What good looks like (target SLAs)

| Metric | Target | Why it matters |
|---|---|---|
| Actions executed without policy evaluation | 0 | Non-negotiable: every action goes through the spine |
| Actions executed without verifiable agent identity | 0 | "An agent did it" is never acceptable |
| Audit log completeness (every decision recorded) | 100% | SOC 2 / ISO 27001 prerequisite |
| Audit log tamper-evidence | Cryptographic anchoring | Hash chain / Merkle proof / equivalent |
| Policy evaluation p95 latency | < 5 ms | Spine cannot be the latency bottleneck |
| Policy as code coverage | 100% of in-scope actions | If a tool isn't covered by policy, it shouldn't be reachable |
| Shadow agent discovery rate | All processes scanned weekly | Unregistered agents are a real production risk |
| Policy lint pass rate before deploy | 100% | No untested policy reaches production |
| Adversarial penetration test (red team) | < 1% structural ASR | Acknowledged: this is < model-layer ASR by an order of magnitude |
| Time from policy decision to audit-log record | < 1 s | Audit lag is an attack window |

# Reference build sequence

AGS is built in sequence: skeleton through to first production reference deployment. Each step depends on the previous one. Pace varies by team and tooling; the sequence does not.

| Step | Deliverable |
|---|---|
| 1 | Policy engine + first deterministic deny: one tool wrapped, one policy rule, one allow / deny path |
| 2 | Audit log: append-only, structured, written on every decision (allow + deny) |
| 3 | Agent identity: every action carries a verifiable agent-ID; cross-tenant identity isolation enforced |
| 4 | Tamper-evidence: commitment anchoring (hash chain / Merkle / signed batches) on the audit log |
| 5 | Privilege rings: sandboxed execution tiered by agent trust level |
| 6 | Kill switch + SLO monitoring: humans can stop a runaway agent in seconds; SLO breaches trigger alerts |
| 7 | Tool poisoning detection + shadow agent discovery: supply-chain governance |
| 8 | Spec / one-pager / case study |

See [SPEC.md](SPEC.md#5-build-sequence) for details.

# Who this is for

- **CTOs / CISOs / CIOs** deploying autonomous agents to production, when prompt-level safety stops being defensible
- **GRC / compliance / audit teams** that need to certify agent systems against SOC 2 / ISO 27001 / regulator standards
- **Enterprise platform teams** evaluating AGT, OPA, Cedar, Permit.io, SPIFFE. This gives you the vocabulary to ask the right questions
- **AI engineers** building agent systems that must survive a real adversarial environment
- **Buyers** of AI vendors: the questions to ask vendors who claim governance ("Do you enforce deterministically? Where is agent identity attested? Is the audit log tamper-evident? Where does the policy live?")

# What this is not

- Not a library you install. It's an architectural pattern with reference SLAs and examples.
- Not a replacement for any specific governance product (OPA, Cedar, Permit.io, AGT). The pattern is what they all implement; AGS describes the pattern.
- Not a substitute for red-teaming. Even with AGS, you red-team continuously. AGS narrows the attack surface from "prompt-layer ASR" (~100% on frontier models) to "structural ASR" (the policy + identity surface), which is orders of magnitude smaller. That structural surface is real and worth attacking: [`docs/red-team-2026-06-09.md`](docs/red-team-2026-06-09.md) red-teams the reference enforcer, names the bypass classes (resource-scope escape, deny shadowing, unenforced rings, self-asserted identity, forgeable audit), and is what the hardened `enforce.py` defends against.
- Not a substitute for PDS / ACS / ESF / CRI / DCS. AGS is the protocol-layer substrate that governs whatever those describe.

# Use it with Claude (or any AI coding agent)

AGS ships with a [Claude Code skill](dist/skills/ags/SKILL.md) that turns the spec into an active architectural consultant inside your AI coding session. Install:

```bash
mkdir -p ~/.claude/skills/ags
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Agent-Governance-Spine/main/dist/skills/ags/SKILL.md \
  -o ~/.claude/skills/ags/SKILL.md
```

After install, the skill auto-activates whenever you ask Claude about agent governance, policy enforcement, identity for agents, audit logs for AI systems, OWASP agentic risks, or any of the other triggering contexts. It diagnoses which of the four documented failure modes you're hitting and recommends which of the 13 principles to apply.

# Examples

The [`examples/`](examples/) directory has concrete artifacts:

- [`policy-yaml.example.md`](examples/policy-yaml.example.md): what a production-grade policy file looks like (allow/deny/require-approval rules with conditions)
- [`audit-record.example.json`](examples/audit-record.example.json): what an AGS audit-log entry looks like, with commitment anchoring
- [`privilege-rings.md`](examples/privilege-rings.md): four-ring sandboxing model worked through for a typical agent fleet
- [`enforce.py`](examples/enforce.py): a runnable, dependency-free demo of deterministic governance. It runs action requests through a deny-by-default policy (the decision is a pure function, no model) with **deny-override** (an explicit deny beats any allow regardless of order), **enforced privilege rings** (a Ring 1 agent is denied a Ring 0 action), and **path-traversal canonicalization** (an allowed `kb/*` scope cannot be escaped with `..`). It writes a key-chained, head-sealed audit log and runs an attacker battery (in-place edit, forge-and-recompute without the key, truncation), showing each is caught. Run it with `python3 examples/enforce.py`. The bypass classes it defends against are documented in [`docs/red-team-2026-06-09.md`](docs/red-team-2026-06-09.md).

Formal contracts live in [`schema/`](schema/): [`policy-rule.v1.json`](schema/policy-rule.v1.json) (the deny-by-default rule format) and [`policy-decision.v1.json`](schema/policy-decision.v1.json) (the tamper-evident audited decision record).

# Citing this work

If you reference AGS in a paper, talk, blog post, or vendor architecture, please cite it. A machine-readable citation file is in [CITATION.cff](CITATION.cff). Suggested citation:

> Mattie, D. (2026). *Agent Governance Spine: An architectural pattern for deterministic policy enforcement, per-agent identity, and tamper-evident audit for autonomous AI agents.* https://github.com/drewmattie-code/Agent-Governance-Spine

# Contributing

Issues, examples, implementation reports, and policy patterns welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

# License

- **Spec, documentation, diagrams**: [Creative Commons Attribution 4.0 (CC BY 4.0)](LICENSE-CC-BY-4.0). Use it, adapt it, build commercial products on top. Credit the source.
- **Code samples and examples**: [MIT](LICENSE-MIT).

# Catalog

AGS is the fifth specification in the SaaSquach AI Labs architectural catalog, which now spans nine specs:

- **[PDS: Progressive Discovery Spine](https://github.com/drewmattie-code/Progressive-Discovery-Spine)**, single-agent tool discovery
- **[ACS: Adversarial Coordination Spine](https://github.com/drewmattie-code/Adversarial-Coordination-Spine)**, multi-agent coordination
- **[ESF: External Signal Fabric](https://github.com/drewmattie-code/External-Signal-Fabric)**, external-world signal substrate
- **[CRI: Composite Risk Index](https://github.com/drewmattie-code/Composite-Risk-Index)**, composite risk scoring *(private)*
- **AGS: Agent Governance Spine** *(this spec)*, deterministic governance, identity, and audit
- **[DCS: Durable Context Spine](https://github.com/drewmattie-code/Durable-Context-Spine)**, durable state and memory across sessions and time
- **GDS: Grounded Data Spine** *(private)*, a canonical semantic model (text-to-metric) plus data-level entitlements
- **ARS: Agent Registry Spine** *(private)*, the system of record layer for every agentic asset that discovery reads from and governance enforces against
- **SRS: Sovereign Runtime Spine** *(private)*, the execution substrate, the sovereign first-party agent runtime that first-party agents run on (outside agents and tools plug into the spine; first-party agents run on SRS)

Together they form the ten-way failure attribution dictionary (bad customer/tool data / bad world data / bad reasoning / bad evaluation / bad scoring / bad governance / bad continuity / bad grounding / bad or missing registry / bad or unbounded execution) documented above. Each spec plants a flag at a different layer of the agent-architecture stack.

# Author

[Drew Mattie](https://www.linkedin.com/in/drew-mattie-88084826/) · SaaSquach AI Labs (a division of Charles & Roe Inc.) · 2026
