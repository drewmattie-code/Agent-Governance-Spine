# AGS Claude skills

This directory holds the AGS architectural-consultant skill in a format that drops directly into Claude Code, Codex, Cursor, and other clients that support the skills convention.

## Install for Claude Code

```bash
mkdir -p ~/.claude/skills/ags
cp ags/SKILL.md ~/.claude/skills/ags/SKILL.md
```

Restart your Claude Code session (or run `/help` and confirm the skill appears).

The skill will activate automatically when you ask architectural questions about agent governance, policy enforcement for AI, agent identity, OWASP Agentic risks, audit logs, or any of the other triggering contexts described in the SKILL frontmatter.

## What the skill does

It's an architectural consultant, not a code library. When triggered, Claude (or another supporting agent) will:

1. Diagnose which of the four documented governance failure modes you're hitting (prompt-layer trust collapse, identity blur, audit gap, policy drift)
2. Recommend the 2-3 AGS principles that address it
3. Give one concrete next step
4. Cite the empirical case (JailbreakBench, Andriushchenko, Microsoft Red Team) when appropriate
5. Link to the full spec for deeper reading

It will NOT install software, pretend to be a runnable library, or recite the whole spec at you. The point is fast diagnosis.

## Composition with PDS, ACS, ESF, CRI, and DCS

AGS is one of nine specifications in the same architectural catalog (PDS, ACS, ESF, AGS, DCS public; CRI, GDS, ARS, SRS private/forthcoming). Install the public skills for full coverage:

```bash
mkdir -p ~/.claude/skills/{pds,acs,esf,cri,ags,dcs}
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Progressive-Discovery-Spine/main/dist/skills/pds/SKILL.md \
  -o ~/.claude/skills/pds/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/External-Signal-Fabric/main/dist/skills/esf/SKILL.md \
  -o ~/.claude/skills/esf/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Adversarial-Coordination-Spine/main/dist/skills/acs/SKILL.md \
  -o ~/.claude/skills/acs/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Composite-Risk-Index/main/dist/skills/cri/SKILL.md \
  -o ~/.claude/skills/cri/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Agent-Governance-Spine/main/dist/skills/ags/SKILL.md \
  -o ~/.claude/skills/ags/SKILL.md
curl -fsSL https://raw.githubusercontent.com/drewmattie-code/Durable-Context-Spine/main/dist/skills/dcs/SKILL.md \
  -o ~/.claude/skills/dcs/SKILL.md
```

## Other clients

The SKILL.md format is portable. Drop it into:

- **Cursor**: `~/.cursor/skills/ags/SKILL.md`
- **Codex**: `~/.codex/skills/ags/SKILL.md`
- Any other agent that supports the SKILL.md / agent-skill convention

For agents that don't natively support the skills convention, the SKILL.md is also readable as a prompt. Paste it into a system prompt or context.

## Versioning

The skill version tracks the spec version. Current: v1.1 (matches SPEC.md v1.1).

When the spec evolves, the skill evolves with it. Watch this repo for updates.

## Attribution

Agent Governance Spine by Drew Mattie · SaaSquach AI Labs (a division of Charles & Roe Inc.) · CC BY 4.0
