# P11-PEE-008 Deterministic AI Council Resolver

This component resolves structured disagreement metadata from ChatGPT, Claude, Gemini AI, and Jarvis specialist agents.

Rules:
- critical policy disagreement => STOP_AND_ESCALATE;
- factual disagreement => collect authoritative evidence or run deterministic test;
- risk disagreement => use conservative unresolved risk state and red-team;
- evidence disagreement => collect evidence;
- agreement with evidence but no deterministic tests => provisional consensus;
- agreement with evidence plus deterministic tests => verified consensus;
- majority vote never establishes truth;
- minority positions are preserved;
- no production activation occurs.

The resolver does not call any model. Model outputs must be produced independently elsewhere and supplied as structured council position records.
