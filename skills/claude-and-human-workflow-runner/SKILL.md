---
name: claude-and-human-workflow-runner
description: Run a step-by-step workflow from a spec file or inline description, alternating between Claude actions and human actions. Claude reads the steps, figures out who does what from natural language, executes its own steps, and pauses at human steps until they confirm. Use whenever the user wants to walk through a workflow, pipeline, or checklist that involves both Claude and human actions.
---

# Workflow Runner

Read a workflow spec and execute it step by step. For each step, figure out from the text whether it's Claude's job or the human's job, then act accordingly.
Human overrides, take human interference over prewritten rules

## Figuring out who does what

There's no required format. Use common sense to read the intent:

**Claude's step** if the text says things like: "claude does", "claude run this command", "claude generate", "claude will", a shell command to execute, something that requires file access or computation.

**Human's step** if the text says things like: "user", something that requires the human's eyes, hands, or judgment.

When it's ambiguous, lean toward human — it's better to pause and confirm than to do the wrong thing.

## How to run

**1. Read and announce** — scan all the steps and briefly tell the human the sequence before starting:
> "6 steps: yours → mine → mine → yours → mine × 3. Starting now."

**2. Claude steps** — do the work, report briefly what you did, move straight to the next step.

**3. Human steps** — make it obvious it's their turn:
> **Your turn — Step 3**
> [what they need to do]
> Let me know when you're done.
> Human step can also be assisted by Claude, in which case stay and help user in said task until the user approves the step is done


Then stop. Don't continue until they reply.

**4. On human reply** — any response counts as confirmation. If they included notes or results, acknowledge them and use that context in subsequent steps.

**5. When done** — short summary of what was accomplished.
