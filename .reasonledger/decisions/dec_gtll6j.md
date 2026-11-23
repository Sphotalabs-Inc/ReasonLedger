---
id: dec_gtll6j
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
justifies:
- AGENTS.md::Data minimization
watchers: []
context: Spec 14 first said a decision spanning several modules has a home module
  with the others as also-touches, and kept model-filed topics as a fallback. The
  owner wants overlaps visible, and dates is a base capability used everywhere, so
  showing a dates decision in every feature would make no sense. How should decisions
  be assigned to modules and shown, and what should happen to topics and the source-code
  rule? This revises dec_84nu3p.
choice: 'Use equal membership: a decision belongs to every module its code anchors
  fall in, overlap is drawn distinctly, and every total counts unique decisions. Modules
  are either feature or foundation (proposed by name hints and co-change fan-in, confirmed
  by a person); membership comes from anchors only, so a foundation decision stays
  in the foundation and is not copied into features that use it. A decision anchored
  in more than four modules is cross-cutting and listed once in its own group. Remove
  the topics field, command and UI once membership lands, keeping only the description
  parser and classifier plumbing, and amend the charter so a loopback viewer may read
  local files on request without persisting or sending them.'
alternatives_rejected:
- 'Home module with also-touches: gives one canonical place and cleaner per-module
  counts, but the owner preferred showing overlaps equally and it hides how shared
  a decision really is'
- 'Show foundation decisions in every module that uses the foundation: needs a usage
  graph we are not building, and repeats a dates decision across every feature page'
- 'Keep topics as a permanent fallback label: adds a public frontmatter field, command
  and MCP parameter to support once modules already place decisions'
- 'Keep the never-source-code wording unchanged and forbid a viewer: blocks the in-context
  code view the product is differentiated on, when the rule''s intent was only about
  stored and transmitted data'
assumptions:
- Anchors are a good enough proxy for which modules a decision concerns; anchorless
  decisions are shown as unplaced and warned about at record time
- Four modules is a reasonable breadth cap, to be tuned on the calibration corpus
  along with the foundation fan-in threshold
- Removing topics before the first public release costs nothing because the package
  is unpublished
---

## Context

Spec 14 first said a decision spanning several modules has a home module with the others as also-touches, and kept model-filed topics as a fallback. The owner wants overlaps visible, and dates is a base capability used everywhere, so showing a dates decision in every feature would make no sense. How should decisions be assigned to modules and shown, and what should happen to topics and the source-code rule? This revises dec_84nu3p.

## Choice

Use equal membership: a decision belongs to every module its code anchors fall in, overlap is drawn distinctly, and every total counts unique decisions. Modules are either feature or foundation (proposed by name hints and co-change fan-in, confirmed by a person); membership comes from anchors only, so a foundation decision stays in the foundation and is not copied into features that use it. A decision anchored in more than four modules is cross-cutting and listed once in its own group. Remove the topics field, command and UI once membership lands, keeping only the description parser and classifier plumbing, and amend the charter so a loopback viewer may read local files on request without persisting or sending them.

## Alternatives rejected

- Home module with also-touches: gives one canonical place and cleaner per-module counts, but the owner preferred showing overlaps equally and it hides how shared a decision really is
- Show foundation decisions in every module that uses the foundation: needs a usage graph we are not building, and repeats a dates decision across every feature page
- Keep topics as a permanent fallback label: adds a public frontmatter field, command and MCP parameter to support once modules already place decisions
- Keep the never-source-code wording unchanged and forbid a viewer: blocks the in-context code view the product is differentiated on, when the rule's intent was only about stored and transmitted data

## Assumptions

- Anchors are a good enough proxy for which modules a decision concerns; anchorless decisions are shown as unplaced and warned about at record time
- Four modules is a reasonable breadth cap, to be tuned on the calibration corpus along with the foundation fan-in threshold
- Removing topics before the first public release costs nothing because the package is unpublished
