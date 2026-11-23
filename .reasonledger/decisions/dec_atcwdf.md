---
id: dec_atcwdf
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-12T23:35:30.057502Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_assets/conflicts.js:50-67
- packages/cli/src/reasonledger_cli/ui_assets/conflicts.js:86-95
- packages/cli/src/reasonledger_cli/ui_assets/conflicts.js:122-180
- packages/cli/src/reasonledger_cli/ui_assets/judge.js:118-126
- packages/cli/src/reasonledger_cli/ui_assets/overview.js:37-54
- packages/cli/src/reasonledger_cli/ui_assets/app.js:174-177
anchor_hashes:
  packages/cli/src/reasonledger_cli/ui_assets/conflicts.js:50-67: sha256:6b88e30bd77c0f9c
  packages/cli/src/reasonledger_cli/ui_assets/conflicts.js:86-95: sha256:220bb1b130a16821
  packages/cli/src/reasonledger_cli/ui_assets/conflicts.js:122-180: sha256:febaed2507168d4b
  packages/cli/src/reasonledger_cli/ui_assets/judge.js:118-126: sha256:629206d4fcd30b58
  packages/cli/src/reasonledger_cli/ui_assets/overview.js:37-54: sha256:ae41a8342a51339f
  packages/cli/src/reasonledger_cli/ui_assets/app.js:174-177: sha256:0882ec415412e020
watchers: []
context: After the five-tab layout (dec_28c3xi), judged conflicts sat at the foot
  of the Review queue under every pending approval, related pairs were an Ask filter,
  and the conflict check card moved between Review and Ask. The owner found a conflict
  there did not read as something to act on, and asked either for a tab of its own
  or for conflicts to lead Review. On a pair the who-and-when lines came after both
  columns, so it was not clear which side they described, and Dismiss stayed clickable
  while a check was reading the pair. Where do conflicts and related pairs live, and
  how does a pair show which decision is which and which came later?
choice: 'A sixth tab, Conflicts, between Review and Ask, with its own count. It holds,
  in order, the judged conflicts to settle, the Check for conflicts card, and every
  related pair (unchecked, or checked and compatible). Review goes back to approvals
  only (pending decisions and proposals) and its count no longer includes conflicts;
  Ask loses the Related pairs filter. Overview gains a second call to action that
  links to Conflicts: conflicts to settle when any exist, otherwise the number of
  pairs not yet checked. Each side of a pair shows who recorded and judged that decision
  and when inside its own column, and the side recorded later carries a more recent
  badge in words as well as colour; when either side has no date neither is marked.
  While a check runs, Check this pair and Dismiss are disabled on every unchecked
  pair, both in lists drawn during the run and on buttons already on the page. This
  changes dec_28c3xi on where conflicts and pairs live and on the number of tabs,
  and dec_t6vkni on where the check card sits; the rest of both holds, so neither
  is superseded.'
alternatives_rejected:
- 'Keep five tabs and move conflicts to the top of Review: approvals and conflicts
  are different jobs with different actions, the related pairs and the check card
  would still live elsewhere, and one count on the tab could not say which kind is
  waiting'
- 'Keep related pairs in Ask and only the judged conflicts in a new tab: checking
  a pair is what produces a conflict, so the pairs, the check and its results belong
  on one page'
- 'Mark the more recent side by colour or position alone: colour must not be the only
  carrier, and swapping columns would break the fixed A and B order the explanation
  text refers to'
- 'Use approved date rather than recorded date for more recent: many decisions are
  not approved yet, and the question a person asks is which choice was made later'
- 'Disable only the pair being checked: one run at a time is enforced by the server,
  so every other Check button would only produce a refusal'
assumptions:
- Six tabs still fit the header at common widths; at narrow widths they wrap under
  the logo
- Recorded date, including the git-derived fallback, is a fair proxy for which decision
  was made later
- Dismissing a judged conflict while a check runs is safe, since it writes a different
  file from the one the run saves verdicts to; only unchecked pairs are locked
---

## Context

After the five-tab layout (dec_28c3xi), judged conflicts sat at the foot of the Review queue under every pending approval, related pairs were an Ask filter, and the conflict check card moved between Review and Ask. The owner found a conflict there did not read as something to act on, and asked either for a tab of its own or for conflicts to lead Review. On a pair the who-and-when lines came after both columns, so it was not clear which side they described, and Dismiss stayed clickable while a check was reading the pair. Where do conflicts and related pairs live, and how does a pair show which decision is which and which came later?

## Choice

A sixth tab, Conflicts, between Review and Ask, with its own count. It holds, in order, the judged conflicts to settle, the Check for conflicts card, and every related pair (unchecked, or checked and compatible). Review goes back to approvals only (pending decisions and proposals) and its count no longer includes conflicts; Ask loses the Related pairs filter. Overview gains a second call to action that links to Conflicts: conflicts to settle when any exist, otherwise the number of pairs not yet checked. Each side of a pair shows who recorded and judged that decision and when inside its own column, and the side recorded later carries a more recent badge in words as well as colour; when either side has no date neither is marked. While a check runs, Check this pair and Dismiss are disabled on every unchecked pair, both in lists drawn during the run and on buttons already on the page. This changes dec_28c3xi on where conflicts and pairs live and on the number of tabs, and dec_t6vkni on where the check card sits; the rest of both holds, so neither is superseded.

## Alternatives rejected

- Keep five tabs and move conflicts to the top of Review: approvals and conflicts are different jobs with different actions, the related pairs and the check card would still live elsewhere, and one count on the tab could not say which kind is waiting
- Keep related pairs in Ask and only the judged conflicts in a new tab: checking a pair is what produces a conflict, so the pairs, the check and its results belong on one page
- Mark the more recent side by colour or position alone: colour must not be the only carrier, and swapping columns would break the fixed A and B order the explanation text refers to
- Use approved date rather than recorded date for more recent: many decisions are not approved yet, and the question a person asks is which choice was made later
- Disable only the pair being checked: one run at a time is enforced by the server, so every other Check button would only produce a refusal

## Assumptions

- Six tabs still fit the header at common widths; at narrow widths they wrap under the logo
- Recorded date, including the git-derived fallback, is a fair proxy for which decision was made later
- Dismissing a judged conflict while a check runs is safe, since it writes a different file from the one the run saves verdicts to; only unchecked pairs are locked
