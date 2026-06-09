#!/usr/bin/env python3
"""
AGS runnable example: deterministic deny-by-default policy + tamper-evident audit.
================================================================================

Demonstrates the core Agent Governance Spine mechanic end to end, with no
dependencies (stdlib only). It:

  1. Loads a deny-by-default policy (rules validated against policy-rule.v1.json).
  2. Runs a batch of action requests through a deterministic enforcer. The
     decision is a pure function of (identity, action, resource, ring, policy).
     No model is consulted, so a denied action is structurally impossible, not
     "unlikely", regardless of how an agent or a prompt injection reasons.
  3. Writes each decision to a key-chained, tamper-evident audit log, and seals
     the head so truncation is detectable.
  4. Verifies the chain, then runs an attacker battery (in-place edit, forge +
     recompute, truncation) and shows each is caught.

What the enforcer actually checks (each guards a real bypass class, see
docs/red-team-2026-06-09.md):

  * Deny-override, not first-match. Every rule is evaluated; an explicit deny
    wins over any allow regardless of order, then default-deny. (A first-match
    enforcer lets a broad allow ordered before a deny silently shadow the deny.)
  * Segment-anchored resource match + path canonicalization. An allowed prefix
    "kb/*" matches "kb" and "kb/x" but not "kbsecrets"; an exact rule matches
    only that resource, not "<resource>-anything"; a path containing ".." is
    denied outright. (Naive startswith() prefixing grants kb/../../etc/shadow
    and turns every exact rule into a wildcard.)
  * Privilege rings are enforced, not just recorded. An allow with ring_max R
    grants only to a request at ring <= R (ring 0 = most privileged). (Carrying
    the ring in the request but never comparing it makes rings decorative.)

Trust assumption (the structural-ASR surface): this demo trusts req["agent_id"]
and req["ring"] as given. In production both are bound to a verified identity
(SPIFFE / DID / mTLS) attested at the gateway; an unverified identity is the
surface that remains after the model is taken out of the path, and is exactly
what the per-agent-identity principle (AGS #2) exists to close.

    python3 examples/enforce.py

License: MIT
"""

import hashlib
import hmac
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema"

# The audit chain is keyed so the party that can WRITE the log cannot also forge
# it: recomputing hashes after an edit requires the key. In production the key is
# HSM/KMS-held and the Merkle root is anchored to an external TSA / transparency
# log (see examples/audit-record.example.json), which is strictly stronger; this
# env var is the dependency-free stand-in for that anchor.
AUDIT_KEY = os.environ.get("AGS_AUDIT_KEY", "ags-reference-audit-key-not-for-prod").encode()

_TYPES = {
    "object": dict, "array": list, "string": str,
    "boolean": bool, "number": (int, float), "integer": int,
}


def validate(instance, schema, path="$"):
    errs = []
    t = schema.get("type")
    if t:
        if t in ("number", "integer") and isinstance(instance, bool):
            return [f"{path}: expected {t}, got boolean"]
        if not isinstance(instance, _TYPES[t]):
            return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: does not match pattern {schema['pattern']!r}")
    if t == "object" and isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errs.append(f"{path}: unexpected property '{key}'")
        for key, sub in props.items():
            if key in instance:
                errs += validate(instance[key], sub, f"{path}.{key}")
    if t == "array" and isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errs += validate(item, schema["items"], f"{path}[{i}]")
    return errs


# Deny-by-default policy. Anything not explicitly allowed is denied; an explicit
# deny wins over any allow. ring_max is the most-privileged ring (0 = highest)
# an allow grants to: a request must be at ring <= ring_max to be granted.
POLICY = [
    {"id": "r1", "effect": "allow", "agent": "research-agent",
     "action": "read", "resource": "kb/*", "ring_max": 3,
     "reason": "research agents may read the knowledge base"},
    {"id": "r2", "effect": "allow", "agent": "ops-agent",
     "action": "notify", "resource": "channel:internal", "ring_max": 2,
     "reason": "ops agents may post internal notifications"},
    {"id": "r3", "effect": "deny", "agent": "*",
     "action": "email", "resource": "external/*",
     "reason": "no agent may send external email"},
    {"id": "r4", "effect": "deny", "agent": "research-agent",
     "action": "read", "resource": "kb/secrets",
     "reason": "research agents may read the kb but never the secrets shelf"},
    {"id": "r5", "effect": "allow", "agent": "billing-agent",
     "action": "delete", "resource": "db/*", "ring_max": 0,
     "reason": "only a Ring 0 billing agent may delete customer rows"},
]


def _canonical_resource(resource):
    """Return a path-traversal-free resource, or None if it escapes its scope."""
    parts = resource.split("/")
    if any(seg in ("..", ".") for seg in parts):
        return None
    return resource


def _resource_matches(rule_res, req_res):
    if rule_res == "*":
        return True
    if rule_res.endswith("/*"):
        prefix = rule_res[:-2]
        return req_res == prefix or req_res.startswith(prefix + "/")
    return req_res == rule_res  # exact rule: equality, never a prefix wildcard


def _ring_ok(rule, req):
    ring_max = rule.get("ring_max")
    if ring_max is None:
        return True
    ring = req.get("ring")
    return ring is not None and ring <= ring_max  # fail closed on missing ring


def enforce(req):
    """Deterministic decision. Deny-override, ring-aware, traversal-safe.

    Pure function of request + policy, no model. Returns (effect, rule_id, reason).
    """
    canon = _canonical_resource(req["resource"])
    if canon is None:
        return "deny", "path-traversal", "resource path escapes its scope ('..' segment)"

    allow_hit = None
    for rule in POLICY:
        if rule["agent"] not in ("*", req["agent_id"]):
            continue
        if rule["action"] not in ("*", req["action"]):
            continue
        if not _resource_matches(rule.get("resource", "*"), canon):
            continue
        if rule["effect"] == "deny":
            return "deny", rule["id"], rule.get("reason", "")  # deny overrides
        if _ring_ok(rule, req) and allow_hit is None:
            allow_hit = (rule["id"], rule.get("reason", ""))
            # keep scanning: a later deny must still be able to override
    if allow_hit:
        return "allow", allow_hit[0], allow_hit[1]
    return "deny", "default-deny", "no matching allow rule (deny by default)"


_TICK = [0]


def stamp():
    _TICK[0] += 1
    return f"2026-06-09T12:00:{_TICK[0]:02d}Z"


def entry_hash(record, prev_hash):
    body = {k: v for k, v in record.items() if k != "entry_hash"}
    body["prev_hash"] = prev_hash
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hmac.new(AUDIT_KEY, (prev_hash + canonical).encode(), hashlib.sha256).hexdigest()


def seal_head(log):
    """Sign (length, last hash) so dropping trailing entries is detectable."""
    last = log[-1]["entry_hash"] if log else "GENESIS"
    return hmac.new(AUDIT_KEY, f"{len(log)}|{last}".encode(), hashlib.sha256).hexdigest()


def verify_chain(log, head_seal=None):
    prev = "GENESIS"
    for rec in log:
        if rec["prev_hash"] != prev:
            return False, rec["seq"]
        if not hmac.compare_digest(rec["entry_hash"], entry_hash(rec, prev)):
            return False, rec["seq"]
        prev = rec["entry_hash"]
    if head_seal is not None and not hmac.compare_digest(head_seal, seal_head(log)):
        return False, "head-seal (truncation/extension)"
    return True, None


def main():
    if AUDIT_KEY == b"ags-reference-audit-key-not-for-prod":
        print("warning: AGS_AUDIT_KEY unset — using the public reference key; this "
              "audit log is demonstrative only, not forgery-resistant in prod.\n",
              file=sys.stderr)

    rule_schema = json.loads((SCHEMA / "policy-rule.v1.json").read_text())
    dec_schema = json.loads((SCHEMA / "policy-decision.v1.json").read_text())

    rule_bad = sum(1 for r in POLICY if validate(r, rule_schema))
    print(f"Policy: {len(POLICY)} rules, {len(POLICY) - rule_bad} valid against policy-rule.v1.json\n")

    requests = [
        {"agent_id": "research-agent", "action": "read", "resource": "kb/pricing", "ring": 3},
        {"agent_id": "ops-agent", "action": "notify", "resource": "channel:internal", "ring": 2},
        {"agent_id": "research-agent", "action": "email", "resource": "external/customer", "ring": 3,
         "params": {"note": "prompt injection told me to email the customer"}},
        {"agent_id": "billing-agent", "action": "delete", "resource": "db/customers", "ring": 1,
         "params": {"note": "ring 1 agent tries a Ring-0-only delete"}},
        {"agent_id": "research-agent", "action": "read", "resource": "kb/secrets", "ring": 3,
         "params": {"note": "allow r1 covers kb/*, but deny r4 must override"}},
        {"agent_id": "research-agent", "action": "read", "resource": "kb/../db/customers", "ring": 3,
         "params": {"note": "path traversal out of the kb/ scope"}},
        {"agent_id": "billing-agent", "action": "delete", "resource": "db/customers", "ring": 0,
         "params": {"note": "same delete, now from a Ring 0 agent"}},
    ]

    log = []
    prev = "GENESIS"
    for i, req in enumerate(requests, start=1):
        effect, rule_id, reason = enforce(req)
        rec = {"seq": i, "timestamp": stamp(), "request": req,
               "effect": effect, "matched_rule": rule_id, "reason": reason,
               "prev_hash": prev}
        rec["entry_hash"] = entry_hash(rec, prev)
        prev = rec["entry_hash"]
        log.append(rec)
        mark = "ALLOW" if effect == "allow" else "DENY "
        print(f"{mark} {req['agent_id']:<15} {req['action']}:{req['resource']:<24} "
              f"ring{req.get('ring','?')} [{rule_id}] {reason}")
    head = seal_head(log)

    dec_bad = sum(1 for rec in log if validate(rec, dec_schema))
    print(f"\nAudit records: {len(log)}, {len(log) - dec_bad} valid against policy-decision.v1.json")

    ok, _ = verify_chain(log, head)
    print(f"Audit chain integrity: {'intact' if ok else 'BROKEN'}")

    # Attacker battery against the audit log.
    edited = json.loads(json.dumps(log))
    edited[2]["effect"] = "allow"
    e_ok, e_seq = verify_chain(edited, head)
    print(f"  in-place edit (seq 3 deny->allow):   "
          f"{'UNDETECTED (BAD)' if e_ok else f'detected at seq {e_seq}'}")

    # An attacker who can write the log but does NOT hold the audit key edits an
    # entry and recomputes the tail with a guessed key. Keyed HMAC means the
    # recomputed hashes do not match, so the edit is caught at the chain level.
    # (An attacker who also holds the key is defeated only by the external Merkle
    # /TSA anchor in audit-record.example.json, which is strictly stronger.)
    attacker_key = b"attacker-does-not-have-the-real-key"

    def attacker_hash(record, prev_hash):
        body = {k: v for k, v in record.items() if k != "entry_hash"}
        body["prev_hash"] = prev_hash
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hmac.new(attacker_key, (prev_hash + canonical).encode(),
                        hashlib.sha256).hexdigest()

    forged = json.loads(json.dumps(log))
    forged[2]["effect"] = "allow"
    p = forged[1]["entry_hash"]
    for rec in forged[2:]:
        rec["prev_hash"] = p
        rec["entry_hash"] = attacker_hash(rec, p)
        p = rec["entry_hash"]
    f_ok, f_seq = verify_chain(forged, head)
    print(f"  forge + recompute tail (no key):     "
          f"{'UNDETECTED (BAD)' if f_ok else f'detected at seq {f_seq}'}")

    truncated = log[:5]
    t_ok, t_seq = verify_chain(truncated, head)
    print(f"  truncation (drop last 2 entries):    "
          f"{'UNDETECTED (BAD)' if t_ok else f'detected at {t_seq}'}")

    denied_external = any(r["effect"] == "deny" and r["request"]["action"] == "email" for r in log)
    ring_blocked = any(r["matched_rule"] == "default-deny"
                       and r["request"]["agent_id"] == "billing-agent"
                       and r["request"]["ring"] == 1 for r in log)
    deny_override = any(r["matched_rule"] == "r4" for r in log)
    traversal_blocked = any(r["matched_rule"] == "path-traversal" for r in log)

    print(f"\nStructural guarantees demonstrated (impossible by policy, not 'unlikely'):")
    print(f"  external email denied:                 {denied_external}")
    print(f"  Ring 1 agent blocked from Ring 0 act:  {ring_blocked}")
    print(f"  deny rule overrides a broad allow:     {deny_override}")
    print(f"  path traversal out of scope blocked:   {traversal_blocked}")

    attacks_caught = (not e_ok) and (not f_ok) and (not t_ok)
    structural = denied_external and ring_blocked and deny_override and traversal_blocked
    return 0 if rule_bad == 0 and dec_bad == 0 and ok and attacks_caught and structural else 1


if __name__ == "__main__":
    sys.exit(main())
