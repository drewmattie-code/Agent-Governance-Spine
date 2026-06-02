# Example: Production-grade AGS policy file

A worked policy file showing all three decision types (allow / deny / require-approval), per-agent identity conditions, multi-tenant isolation, and audit-log requirements. This is what AGS principle #4 (policy as code) looks like in practice.

The shape is OPA-Rego-compatible and Cedar-translatable; the YAML wrapper is for human readability. Most policy engines accept this shape natively.

---

## File: `policies/clawgentics-loa-production.yaml`

```yaml
apiVersion: governance.toolkit/v1
kind: Policy
metadata:
  name: clawgentics-loa-production
  version: 1.3.0
  owner: security-team@charlesandroe.com
  approved_by: ["ciso@charlesandroe.com", "head-of-eng@charlesandroe.com"]
  approved_at: "2026-05-26T14:00:00Z"
  audit_class: SOC2_TypeII

defaults:
  action: deny           # Default-deny posture. Every action requires explicit allow.
  audit: true            # Every decision (allow + deny) is recorded.

# Identity requirements applied to every action
identity_requirements:
  attested: required     # Action MUST carry verifiable agent identity (SPIFFE / DID / mTLS)
  tenant_scoped: required # Identity MUST include tenant_id; cross-tenant denied at this layer

rules:

  # Allow: read-only data access for any identified agent
  - name: allow-readonly-supplier-queries
    description: "Read-only supplier scorecard / contract queries are allowed for any authenticated agent in the same tenant."
    priority: 100
    when:
      action.type: in: [query_supplier, get_scorecard, get_contract, list_open_approvals]
      principal.identity.tenant_id: matches: target.tenant_id
      principal.ring: in: [0, 1, 2, 3]  # any ring; read-only is broadly safe
    decision: allow
    audit:
      retention_days: 2555  # 7 years for SOC 2

  # Require approval: any approval issuance over $100K
  - name: require-approval-large-value-approvals
    description: "Issuing an LOA approval over $100K requires human-in-the-loop sign-off."
    priority: 50
    when:
      action.type: issue_approval
      action.value_usd: greater_than: 100000
    decision: require_approval
    approvers:
      - role: vp_finance
      - role: cfo
    approval_timeout_minutes: 60
    on_timeout: escalate
    audit:
      retention_days: 2555
      tamper_evidence: required

  # Deny: destructive operations always denied (ClawGentics LOA never modifies historical approvals)
  - name: deny-destructive-history-operations
    description: "ClawGentics LOA is append-only. No agent - at any ring - can delete or modify historical approval records."
    priority: 1
    when:
      action.type: in: [delete_approval, modify_approval_history, truncate_audit, drop_audit_table]
    decision: deny
    audit:
      retention_days: 2555
      severity: critical
      alert: ["security-team", "ciso"]

  # Deny: cross-tenant identity attempts (defense in depth)
  - name: deny-cross-tenant-access
    description: "Identity layer already enforces tenant scoping. This rule is defense-in-depth - explicit deny on any action where principal tenant != target tenant."
    priority: 1
    when:
      principal.identity.tenant_id: not_equals: target.tenant_id
    decision: deny
    audit:
      retention_days: 2555
      severity: critical
      alert: ["security-team", "tenant-isolation-incident"]

  # Allow: governance-aware-trained agents have a higher trust score and broader read access
  - name: allow-trusted-agent-read-broadly
    description: "Agents with composite trust score > 0.9 can read across tenants in their assigned governance domain (e.g., ClawGentics-LOA-as-a-product team)."
    priority: 75
    when:
      action.type: in: [query_supplier, get_scorecard]
      principal.trust_score: greater_than: 0.9
      principal.governance_domain: equals: "clawgentics-loa-platform"
    decision: allow
    audit:
      retention_days: 2555

  # Require approval: any send_email to an external recipient
  - name: require-approval-external-email
    description: "All emails to recipients outside @charlesandroe.com require approver review."
    priority: 60
    when:
      action.type: send_email
      action.recipient_domain: not_in: ["charlesandroe.com", "saasquach.ai"]
    decision: require_approval
    approvers:
      - role: comms_lead
    approval_timeout_minutes: 30
    audit:
      retention_days: 2555

  # Deny: any tool not on the registered tool manifest
  - name: deny-unregistered-tools
    description: "Tool poisoning detection: only tools in the signed manifest can be invoked. Anything outside the manifest is denied."
    priority: 5
    when:
      action.tool_name: not_in_manifest: "policies/tool-manifest-v3.signed.json"
    decision: deny
    audit:
      retention_days: 2555
      severity: high
      alert: ["security-team"]
```

---

## What every rule must include

Every rule in a production AGS policy file MUST declare:

1. **`name`**: human-readable; goes into audit-log entries
2. **`priority`**: lower number = higher precedence; `defaults` is lowest
3. **`when`**: match conditions (action attributes, principal attributes, target attributes)
4. **`decision`**: `allow` | `deny` | `require_approval`
5. **`audit`**: retention period and any severity / alert routing

Highly recommended:
- **`description`**: why this rule exists; reviewable
- **`approvers`** for `require_approval` rules: who can sign off
- **`approval_timeout_minutes`** + **`on_timeout`**: what happens if no approver acts
- **`severity`** + **`alert`** for high-impact deny rules

## How the policy is deployed

The policy file lives in git, in the `policies/` directory of the deploying project. CI gates:

1. **Lint**: `agt lint-policy policies/` (or the OPA/Cedar equivalent) must pass.
2. **Test**: every rule has at least one allow + one deny test case. Test fixture inputs cover the rule's match conditions.
3. **PR review**: every change touching `policies/` requires reviewer approval from a designated security owner.
4. **Signed commit**: production deployment loads only signed commits (GPG / Sigstore).
5. **Version pinning**: production loads policy version `1.3.0` (or whatever's tagged); not "latest." Changing what's deployed requires a deploy event, which itself is audited.

## When the policy can be changed in an emergency

Emergency policy changes are themselves changes-as-code. No production console hotfix. The emergency change process:

1. Author files a PR with the emergency change + an incident ticket reference.
2. Two approvers (instead of one) sign off. Both must be in the `incident_response` group.
3. CI runs the full lint + test suite (faster fast-path acceptable; tests must still pass).
4. Deploy.
5. The emergency change is reviewed at the next routine security review (e.g., weekly), and either confirmed as a permanent change or rolled back.

## Audit-log expectation

Every decision produced by evaluating this policy writes an audit record. See `examples/audit-record.example.json` for the shape.

Critical: the audit log records the **policy version** active at decision time. Auditing the system five years later must be able to recover the exact policy that produced any historical decision. The `metadata.version` field in the policy file flows through to the audit record.

## What this example does NOT include

For brevity, this example omits:

- Custom decision context attributes (e.g., business-hours window, customer-tier-specific rules)
- Privilege-ring-specific carve-outs (Ring 0 agents have different rules than Ring 3; see `examples/privilege-rings.md`)
- Tool-poisoning-detection trigger rules (covered by AGS principle #7)
- Shadow-agent-discovery rules (covered by AGS principle #8)

A production AGS policy for ClawGentics LOA Software would be 200-400 rules across multiple files, partitioned by domain.
