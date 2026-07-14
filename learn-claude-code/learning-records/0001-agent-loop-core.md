# Agent Loop — learning established

The learner understands the core agent loop pattern (`while stop_reason == "tool_use"`) and the philosophy that the 30-line loop in s01 is the core of Claude Code's 1729-line `query.ts`. The rest are protection mechanisms. They also understand the mental model shift from "building an agent" to "building a harness" — the model provides intelligence, the harness provides the world (tools, knowledge, observation, action interfaces, permissions).

Evidence: learner read s01 README and code.py, can identify the 5-step loop (user message → LLM call → check stop_reason → execute tools → feed results → loop).

Implications: ready for s02 (tool dispatch) and s03 (permissions). Should be asked to write the loop in TypeScript as a retrieval practice exercise.
