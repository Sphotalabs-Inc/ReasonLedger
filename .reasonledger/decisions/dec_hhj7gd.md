---
id: dec_hhj7gd
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-10T18:45:36.835610Z'
justifies:
- packages/core/src/reasonledger_core/modules/digest.py::_named_support
- packages/core/src/reasonledger_core/modules/digest.py::source_files
- packages/core/src/reasonledger_core/modules/digest.py::labelable_files
- packages/core/src/reasonledger_core/modules/labels.py::folder_pattern
- packages/core/src/reasonledger_core/views/map_view.py::_without_module
- packages/cli/src/reasonledger_cli/ui_decisions.py::claim
- packages/cli/src/reasonledger_cli/ui_assets/map_actions.js::html
- packages/cli/src/reasonledger_cli/ui_assets/map_actions.js::edit
watchers: []
context: A decision whose anchors all sit in spec/ showed under "Decisions with no
  module" on the Map with nothing to do about it. Support folders (specs, docs, tests,
  fixtures) are excluded from the map's files, so no module could own them, and hand
  placement is refused while any anchor still works. How should a decision anchored
  only in support files get a module, and where should a person act on it?
choice: 'A person may opt support files into the map; a scan still never proposes
  them. A label whose own pattern runs through a support folder (spec/**) claims the
  files it matches, and those files then count as the map''s source files everywhere;
  a label that only passes over a support folder (packages/**) leaves it out, so existing
  maps keep their counts. The map view gives each decision with no module the folder
  patterns that would claim its live anchored files and whether it may be placed by
  hand, and the Map card acts on them through one new undoable organize edit (claim:
  into an existing module, or a new one confirmed by its maker). Hand placement keeps
  its rule: never for a decision with a working anchor. This extends dec_jkmyxy and
  dec_8a28z3.'
alternatives_rejected:
- 'A built-in Specs and docs bucket in every map: no click needed, but it changes
  file counts and coverage on every repo''s map and the calibration ratings taken
  so far'
- 'Let a person place by hand any decision whose anchors land outside every module:
  keeps spec/ out of the map, but gives up the rule that a working anchor always decides
  membership, and the owner wanted specs as a module'
- 'Let any label that matches a support file opt it in: an existing folder rule such
  as packages/** would silently pull every tests folder below it into the map'
- 'Send the person to the Organize tab from the card: Organize lists only decisions
  with no working anchor, so this decision appears in neither place'
assumptions:
- A decision anchored only in specs or docs is common enough (imported ADRs, product
  decisions) that a one-click claim is worth the extra edit
- Reading the manifest inside source_files costs one more YAML parse per request,
  which is acceptable at the sizes measured so far
- Claiming the anchored file's own folder is the scope a person expects; a root file
  is claimed alone
---

## Context

A decision whose anchors all sit in spec/ showed under "Decisions with no module" on the Map with nothing to do about it. Support folders (specs, docs, tests, fixtures) are excluded from the map's files, so no module could own them, and hand placement is refused while any anchor still works. How should a decision anchored only in support files get a module, and where should a person act on it?

## Choice

A person may opt support files into the map; a scan still never proposes them. A label whose own pattern runs through a support folder (spec/**) claims the files it matches, and those files then count as the map's source files everywhere; a label that only passes over a support folder (packages/**) leaves it out, so existing maps keep their counts. The map view gives each decision with no module the folder patterns that would claim its live anchored files and whether it may be placed by hand, and the Map card acts on them through one new undoable organize edit (claim: into an existing module, or a new one confirmed by its maker). Hand placement keeps its rule: never for a decision with a working anchor. This extends dec_jkmyxy and dec_8a28z3.

## Alternatives rejected

- A built-in Specs and docs bucket in every map: no click needed, but it changes file counts and coverage on every repo's map and the calibration ratings taken so far
- Let a person place by hand any decision whose anchors land outside every module: keeps spec/ out of the map, but gives up the rule that a working anchor always decides membership, and the owner wanted specs as a module
- Let any label that matches a support file opt it in: an existing folder rule such as packages/** would silently pull every tests folder below it into the map
- Send the person to the Organize tab from the card: Organize lists only decisions with no working anchor, so this decision appears in neither place

## Assumptions

- A decision anchored only in specs or docs is common enough (imported ADRs, product decisions) that a one-click claim is worth the extra edit
- Reading the manifest inside source_files costs one more YAML parse per request, which is acceptable at the sizes measured so far
- Claiming the anchored file's own folder is the scope a person expects; a root file is claimed alone
