---
id: dec_t6vkni
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-12T18:35:38.768665Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_judge.py::JudgeSession
- packages/cli/src/reasonledger_cli/ui_judge.py::JudgeSession._start
- packages/cli/src/reasonledger_cli/ui_judge.py::JudgeSession._refusal
- packages/core/src/reasonledger_core/reasoning/judge.py::judge_pending
- packages/cli/src/reasonledger_cli/ui_assets/judge.js:65-139
- packages/cli/src/reasonledger_cli/ui_assets/judge.js:11-22
anchor_hashes:
  packages/cli/src/reasonledger_cli/ui_assets/judge.js:65-139: sha256:90c8d9643acfeaba
  packages/cli/src/reasonledger_cli/ui_assets/judge.js:11-22: sha256:09b175c770c95b98
watchers: []
context: 'The UI showed conflicts and unjudged related pairs but had no way to run
  the judge: that took the reasonledger judge command or a coding agent, and with
  zero conflicts nothing on the page said so. The owner asked for a button. dec_zfty5t
  limited the model judge to the explicit CLI command, with status, ui and check only
  reading verdicts, and judging can take half an hour on a local model and sends decision
  text to whatever model is configured. Should the UI be able to start the judge,
  and if so how does a long model run fit a stdlib request-per-thread server, and
  what guards it?'
choice: 'The UI may start the judge, but only on a person''s click; loading a page
  never does. This narrows dec_zfty5t on one point (the judge is no longer CLI-only)
  and keeps its rule that verdicts are produced only by an explicit ask and that status,
  check and page loads only read them; that record is not superseded. A JudgeSession
  held by the UI server runs the same judge_pending as the CLI on one daemon thread,
  one run at a time, and exposes GET /api/judge for progress and POST start and stop.
  Start accepts an optional pair to check one pair. Before anything is sent the server
  applies the command''s checks without prompting: no provider configured is refused
  with need model, and a model off the machine without consent for decision text is
  refused with need consent; the UI cannot grant consent from this card and sends
  the person to Settings. judge_pending gained two parameters, only (one pair by pair
  key) and before_each (handed each pair before it is sent; False stops the run), so Stop ends a run after the pair
  in flight and keeps every verdict already saved. The page shows a Check for conflicts
  card at the top of the related-pairs list in Ask, a Check this pair button on each unjudged pair there,
  links to that list from Overview and Review,
  polls every two seconds while a run is going, and redraws the lists when a conflict
  is found or the run ends. The button says Check for conflicts, not Judge, because
  the UI already uses judged by a person to mean approved.'
alternatives_rejected:
- 'Keep the judge CLI-only and show the command with a copy button: the owner asked
  for a way to run it from the page, and the earlier walk-through found the command
  hint was easy to miss'
- 'Run the judge inside the POST request and answer when it finishes: a full run takes
  minutes to tens of minutes, far past any request timeout, and shows no progress'
- 'Start the CLI as a subprocess and parse its output: a second code path for the
  same run, with progress scraped from text meant for a terminal'
- 'Ask for consent in a browser dialog and grant it from the judge card: consent is
  granted per data class in Settings where its scope is explained, and a one-click
  grant beside a run button invites clicking through'
- 'A button on each decision that checks that decision''s pairs: judging is per pair,
  a decision can sit in many pairs, and the pair list already gives the smaller unit'
- 'Server-sent events or a websocket for progress: the stdlib server has neither,
  and a two-second poll of a small JSON object is enough for a run measured in seconds
  per pair'
- 'Kill the model call in flight on Stop: the provider client has no cancel, and letting
  the current pair finish keeps its verdict instead of wasting the call'
assumptions:
- The UI server is single-user and loopback-only, so one run at a time held in memory
  is enough and nothing needs to survive a restart; saved verdicts are what persist
- A run started in the UI and one started from the CLI at the same moment may both
  write the verdict file; this is as it already was for two CLI runs and is not guarded
  here
- Polling is acceptable because the page is local and the status object is a few numbers
---

## Context

The UI showed conflicts and unjudged related pairs but had no way to run the judge: that took the reasonledger judge command or a coding agent, and with zero conflicts nothing on the page said so. The owner asked for a button. dec_zfty5t limited the model judge to the explicit CLI command, with status, ui and check only reading verdicts, and judging can take half an hour on a local model and sends decision text to whatever model is configured. Should the UI be able to start the judge, and if so how does a long model run fit a stdlib request-per-thread server, and what guards it?

## Choice

The UI may start the judge, but only on a person's click; loading a page never does. This narrows dec_zfty5t on one point (the judge is no longer CLI-only) and keeps its rule that verdicts are produced only by an explicit ask and that status, check and page loads only read them; that record is not superseded. A JudgeSession held by the UI server runs the same judge_pending as the CLI on one daemon thread, one run at a time, and exposes GET /api/judge for progress and POST start and stop. Start accepts an optional pair to check one pair. Before anything is sent the server applies the command's checks without prompting: no provider configured is refused with need model, and a model off the machine without consent for decision text is refused with need consent; the UI cannot grant consent from this card and sends the person to Settings. judge_pending gained two parameters, only (one pair by pair key) and before_each (handed each pair before it is sent; False stops the run), so Stop ends a run after the pair in flight and keeps every verdict already saved. The page shows a Check for conflicts card at the top of the related-pairs list in Ask, a Check this pair button on each unjudged pair there, links to that list from Overview and Review, polls every two seconds while a run is going, and redraws the lists when a conflict is found or the run ends. The button says Check for conflicts, not Judge, because the UI already uses judged by a person to mean approved.

## Alternatives rejected

- Keep the judge CLI-only and show the command with a copy button: the owner asked for a way to run it from the page, and the earlier walk-through found the command hint was easy to miss
- Run the judge inside the POST request and answer when it finishes: a full run takes minutes to tens of minutes, far past any request timeout, and shows no progress
- Start the CLI as a subprocess and parse its output: a second code path for the same run, with progress scraped from text meant for a terminal
- Ask for consent in a browser dialog and grant it from the judge card: consent is granted per data class in Settings where its scope is explained, and a one-click grant beside a run button invites clicking through
- A button on each decision that checks that decision's pairs: judging is per pair, a decision can sit in many pairs, and the pair list already gives the smaller unit
- Server-sent events or a websocket for progress: the stdlib server has neither, and a two-second poll of a small JSON object is enough for a run measured in seconds per pair
- Kill the model call in flight on Stop: the provider client has no cancel, and letting the current pair finish keeps its verdict instead of wasting the call

## Assumptions

- The UI server is single-user and loopback-only, so one run at a time held in memory is enough and nothing needs to survive a restart; saved verdicts are what persist
- A run started in the UI and one started from the CLI at the same moment may both write the verdict file; this is as it already was for two CLI runs and is not guarded here
- Polling is acceptable because the page is local and the status object is a few numbers
