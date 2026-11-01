# P11-PEE-004 Quantum Sandbox Router

This component implements the smallest deterministic Jarvis-side representation of the five Prompt #11 Quantum Question sandboxes.

It does not call any AI model. It does not fetch remote content. It does not modify Jarvis-Hub or Jarvis-Flow. It does not activate production behavior.

Supported sandboxes:

- IF — Hypothesis Engineer
- MAYBE — Uncertainty Analyst
- WHY_NOT — Innovation Architect
- DONT_DO_THAT — Red-Team & Safety Engineer
- I_TOLD_YOU_NOT_TO_DO_THAT — Incident Forensics & Recovery Engineer

The failure-forensics sandbox requires an explicit incident/failure-review flag. Every packet remains non-production and requires external human approval for any later activation.
