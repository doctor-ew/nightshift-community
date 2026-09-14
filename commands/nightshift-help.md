---
name: nightshift-help
description: "Find the appropriate Nightshift workflow from project evidence."
argument-hint: "[request, task-key, or artifact path]"
---

# Nightshift help

Read-only consultation: do not edit files, run builds/tests, mutate tickets or Git state, or advance engineering gates.

Read the request and inspect only relevant project instructions and artifacts. Without a request, show the command map below. With a request, recommend one next command, explain why, and cite the evidence. Do not execute the recommendation.

| Intent | Command |
| --- | --- |
| Prepare a new project and committed baseline | nightshift init [runtime/model] [DIR] [--include FILE] |
| Understand a change, run, or failure | nightshift explain <task-key, path, or question> |
| Discuss system tradeoffs | nightshift architect <question> |
| Discuss implementation or debugging | nightshift dev <question> |
| Explore requirements and product decisions | nightshift pm <question> |
| Explore usability and interaction choices | nightshift ux-designer <question> |
| Record architecture before implementation | nightshift architecture <task-key or brief> |
| Record UI and interaction requirements | nightshift ux <task-key or brief> |
| Inspect installed BMad guidance or import its planning artifacts | nightshift bmad <skill name or artifact path> |
| Build a ticket or Markdown brief | nightshift <ticket-ref or prompt.md> |
| Run independent tickets | nightshift batch <tickets-or-query> |

Terminal commands accept the existing runtime/model prefix and --project, --provider, --model and --auth options. Host adapters expose /nightshift-<command> or $nightshift <command>. Specialist conversations are optional; they do not add pipeline gates. Existing engineering stages retain their own contracts.

If asked what bmad-build did, inspect the actual change using explain; the installed BMad walkthrough skill may also help if available. Never claim a skill is installed without inspecting the current host catalog or a provided installation path.
