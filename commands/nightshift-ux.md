---
name: nightshift-ux
description: "Record visual and interaction requirements for a verified specification."
argument-hint: "[request, task-key, or artifact path]"
---

# Nightshift ux

This workflow may write only the planning artifacts specified below. It must not start engineering or change gate state.

Read the request, repository instructions, existing requirements and UI conventions. Resolve the existing task docs directory from its tracker; otherwise use docs/planning/<brief-stem>/ for a supplied brief. If no stable identity exists, ask for a descriptive name before writing. Never interpret raw user input as a filesystem path.

Write or update only DESIGN.md and EXPERIENCE.md in that directory, preserving established decisions. DESIGN.md records the visual system, layout, typography, spacing, responsive behavior, accessibility requirements and sources. EXPERIENCE.md records user journeys, navigation, interactions, loading/empty/error/success states, keyboard and assistive-technology behavior, and measurable UX acceptance criteria. Mark unresolved decisions explicitly. Avoid inventing research findings.

Finish with artifact paths and the next product/spec command. These are planning inputs: accepted requirements must be verified and incorporated into SPEC.md before implementation. Do not alter implementation, tickets, trackers or engineering gate status.
