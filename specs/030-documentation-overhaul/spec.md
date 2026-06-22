# Spec 030 — Documentation Overhaul

## Goal

Rewrite the README and the architecture doc so that a first-time visitor can install and
run Gata in under three minutes, and an engineer can understand every agent and how they
communicate without reading source code.

## Scope

- `README.md` — restructured so install comes first, required API keys come second (with
  links), then usage, agents, and reference material.
- `docs/architecture.md` — full rewrite with:
  - High-level diagram (agent names only)
  - One section per agent with a more detailed diagram
  - A section explaining the current communication protocol (ParallelPanel)
  - A final section explaining how to add a new communication protocol

## Out of scope

- No Python source changes
- No test changes
- No new agents or protocols

## Success criteria

1. README leads with `pipx install gata`
2. README immediately follows with the three required LLM API keys (Anthropic, Google,
   xAI) and their sign-up links; NEWSAPI is mentioned separately as needed for auto-topic
   mode
3. `docs/architecture.md` opens with a Mermaid flowchart containing only agent names
4. Each agent has its own sub-section with a Mermaid diagram showing internal structure
5. The communication protocol section covers both `ParallelPanel` and `DualPersonaLoop`
   with interface examples
6. A final sub-section shows the minimal steps to implement a new protocol
