# Agent Harness Engineering — Resources

## Knowledge

- [Course: Learn Claude Code (this repo)](https://github.com/shareAI-lab/learn-claude-code)
  20-section progressive course on agent harness engineering. Primary learning material. Each section has README (Chinese), English/Japanese translations, and runnable `code.py`.

- [Claude Code (Anthropic)](https://claude.ai/code)
  The reference implementation. The production agent harness this course reverse-engineers. Use for: comparing course patterns against real-world implementation.

- [Anthropic API Docs — Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
  Official documentation on how Claude handles tool calling. Use for: understanding the `tool_use` content block and `tool_result` message format.

- [Code: Kode Agent CLI](https://github.com/shareAI-lab/Kode-cli)
  Open-source coding agent CLI by the same team. TypeScript implementation. Use for: seeing harness patterns in TypeScript (closer to the learner's stack).

- [Code: Kode Agent SDK](https://github.com/shareAI-lab/Kode-agent-sdk)
  Embeddable agent SDK, no per-user process overhead. Use for: understanding how harness patterns translate to a library/SDK form.

- [Sister course: claw0](https://github.com/shareAI-lab/claw0)
  Teaches the "always-on" harness mechanisms: heartbeat, cron, IM multi-channel routing, memory, soul/personality. Complements this course's "session-based" harness model.

## Wisdom (Communities)

- [Claude Code Discord](https://discord.gg/anthropic)
  Official Anthropic Discord with Claude Code channels. Use for: asking implementation questions, seeing how others use/extend the harness.

- [r/ClaudeAI](https://reddit.com/r/ClaudeAI)
  Active community discussing Claude products including Claude Code. Use for: real-world usage patterns, troubleshooting.

## Gaps

- No dedicated TypeScript port of the 20-section course exists yet (the learner may create this)
- No structured community specifically for "agent harness engineering" as a discipline (the field is emerging)
- The course focuses on coding agents; domain-specific harness patterns (agriculture, healthcare, etc.) are mentioned as principles but not demonstrated with runnable code
