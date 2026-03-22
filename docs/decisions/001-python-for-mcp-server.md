# ADR-001: Use Python for the MCP Server

**Status:** Accepted
**Date:** 2026-03-22

## Context

The project has two components: an MCP server (speaks JSON-RPC over stdio with AI clients) and a Remote Script (runs inside Ableton Live's Python runtime). The Remote Script must be Python -- Ableton's embedded runtime requires it. The question is what language to use for the MCP server.

The initial implementation used Swift with the official MCP Swift SDK. This was attractive for type safety, Swift concurrency, and differentiation from the all-Python competitors. However, several problems emerged:

1. **The MCP Swift SDK is Tier 3** (least mature), while the Python SDK is Tier 1.
2. **The Swift SDK has no Windows support.** Ableton runs on both macOS and Windows, so a Swift MCP server would exclude roughly half the user base.
3. **Most of the meaningful logic lives in the Remote Script** (Python), not the MCP server. The server is largely a typed proxy that forwards commands over TCP.
4. **Two-language projects increase contributor friction.** Every new tool requires changes in both Swift and Python. Contributors need expertise in both.
5. **Every competing project is Python.** While we considered this a differentiator, it also means anyone migrating from a competitor already knows the stack.

Alternatives considered:

- **TypeScript** -- Tier 1 MCP SDK, cross-platform via Node.js, but introduces a third language alongside the required Python Remote Script.
- **Go** -- Tier 1 SDK, single-binary distribution, but same third-language problem and limited audience overlap.
- **C#** -- Tier 1 SDK, Microsoft-backed, but small C#/Ableton developer overlap.

## Decision

Use Python for the MCP server, making Python the single language for the entire project.

## Consequences

**Positive:**
- Single language across both components. One skill set for contributors, one toolchain to maintain.
- Cross-platform out of the box. Works identically on macOS and Windows.
- Tier 1 MCP SDK with active maintenance and community support.
- Faster iteration -- no compile step, no two-language coordination for new tools.
- Larger potential contributor pool.

**Negative:**
- Lose the "only non-Python Ableton MCP server" differentiator. Must differentiate on architecture, features, and maintenance instead.
- No compile-time type safety at the protocol boundary. Mitigated by using Pydantic for typed models.
- Python's async model is less ergonomic than Swift concurrency for the TCP client. Acceptable given the server's relatively simple I/O pattern.
