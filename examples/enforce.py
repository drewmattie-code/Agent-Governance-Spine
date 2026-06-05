#!/usr/bin/env python3
"""
AGS runnable example: deterministic deny-by-default policy + tamper-evident audit.
================================================================================

Demonstrates the core Agent Governance Spine mechanic end to end, with no
dependencies (stdlib only). It:

  1. Loads a deny-by-default policy (rules validated against policy-rule.v1.json).
  2. Runs a batch of action requests through a deterministic enforcer. The
     decision is a pure function of (identity, action, resource, policy). No
     model is consulted, so a denied action is structurally impossible, not
     "unlikely", regardless of how an agent or a prompt injection reasons.
  3. Writes each decision to a hash-chained, tamper-evident audit log (each
     entry validated against policy-decision.v1.json).
  4. Verifies the chain, then tampers with one entry and shows the chain
     detects it.

The point: governance is a hard gate outside the model, and the audit log can
prove what happened. Run:

    python3 examples/enforce.py

License: MIT
"""

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema"

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


# Deny-by-default policy. Anything not explicitly allowed is denied.
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
]


def enforce(req):
    """Deterministic decision. Pure function of request + policy, no model."""
    for rule in POLICY:
        if rule["agent"] not in ("*", req["agent_id"]):
            continue
        if rule["action"] not in ("*", req["action"]):
            continue
        res = rule.get("resource", "*")
        if res != "*":
            prefix = res[:-1] if res.endswith("*") else res
            if not req["resource"].startswith(prefix):
                continue
        return rule["effect"], rule["id"], rule.get("reason", "")
    return "deny", "default-deny", "no matching allow rule (deny by default)"


_TICK = [0]


def stamp():
    _TICK[0] += 1
    return f"2026-06-05T12:00:{_TICK[0]:02d}Z"


def entry_hash(record, prev_hash):
    body = {k: v for k, v in record.items() if k != "entry_hash"}
    body["prev_hash"] = prev_hash
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def verify_chain(log):
    prev = "GENESIS"
    for rec in log:
        if rec["prev_hash"] != prev:
            return False, rec["seq"]
        if rec["entry_hash"] != entry_hash(rec, prev):
            return False, rec["seq"]
        prev = rec["entry_hash"]
    return True, None


def main():
    rule_schema = json.loads((SCHEMA / "policy-rule.v1.json").read_text())
    dec_schema = json.loads((SCHEMA / "policy-decision.v1.json").read_text())

    # validate the policy itself
    rule_bad = sum(1 for r in POLICY if validate(r, rule_schema))
    print(f"Policy: {len(POLICY)} rules, {len(POLICY) - rule_bad} valid against policy-rule.v1.json\n")

    requests = [
        {"agent_id": "research-agent", "action": "read", "resource": "kb/pricing", "ring": 3},
        {"agent_id": "ops-agent", "action": "notify", "resource": "channel:internal", "ring": 2},
        {"agent_id": "research-agent", "action": "email", "resource": "external/customer", "ring": 3,
         "params": {"note": "prompt injection told me to email the customer"}},
        {"agent_id": "billing-agent", "action": "delete", "resource": "db/customers", "ring": 1},
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
        print(f"{mark} {req['agent_id']:<15} {req['action']}:{req['resource']:<22} [{rule_id}] {reason}")

    # validate every audit record
    dec_bad = sum(1 for rec in log if validate(rec, dec_schema))
    print(f"\nAudit records: {len(log)}, {len(log) - dec_bad} valid against policy-decision.v1.json")

    ok, _ = verify_chain(log)
    print(f"Audit chain integrity: {'intact' if ok else 'BROKEN'}")

    # tamper test: flip a denied action to allow after the fact
    tampered = json.loads(json.dumps(log))
    tampered[2]["effect"] = "allow"
    bad_ok, bad_seq = verify_chain(tampered)
    print(f"Tamper test: flipped seq 3 deny->allow -> chain {'still intact (BAD)' if bad_ok else f'detects tampering at seq {bad_seq} (good)'}")

    denied_external = any(r["effect"] == "deny" and r["request"]["action"] == "email" for r in log)
    print(f"\nExternal email was structurally denied: {denied_external}  "
          f"(not 'unlikely', impossible by policy)")

    return 0 if rule_bad == 0 and dec_bad == 0 and ok and not bad_ok and denied_external else 1


if __name__ == "__main__":
    sys.exit(main())
