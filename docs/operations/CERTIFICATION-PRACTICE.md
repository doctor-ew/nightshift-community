# Proposed local certification practice

Implement a Python slugify function and command-line entrypoint in an isolated
repository. Lowercase ASCII letters, replace each run of whitespace between words
with one hyphen, and reject unsupported punctuation with a clear error.

Required unittest cases:

| Input | Expected result |
| --- | --- |
| Empty string | Empty string |
| `Alpha   Beta` | `alpha-beta` |
| `HELLO` | `hello` |
| `hello!` | Clear error; CLI exits unsuccessfully |

The CLI must accept a quoted input argument and print the successful result. An
independent reviewer must inspect the actual assertions and the implementation.
Before implementation, resolve any unspecified behavior (including surrounding
whitespace, digits and non-ASCII input) through the guided decision flow; do not
silently broaden the practice requirement.

Required manual observation: run the CLI with `Alpha   Beta`, retain the exact
command/output, then run `hello!` and retain its error/exit evidence. Accept only
against current reviewed source and current manual-case bindings.

This practice has no publication, merge or deployment endpoint. It must use a
fresh disposable repository and new explicit bounded authorization. This document
is proposed input, not a ticket restart or a live grant.
