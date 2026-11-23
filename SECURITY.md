# Security policy

## Supported versions

Only the latest pre-release of `reasonledger`, `reasonledger-core` and `reasonledger-mcp` is
supported. The three packages are versioned together; a fix ships as the next pre-release.

## Reporting a vulnerability

Please report it privately. Do not open a public issue or pull request for a security problem.

Send the report to **info@sphotalabs.com** (put "ReasonLedger security" in the subject).

Include what you found, the version (`reasonledger --version`), the steps to reproduce it and what
an attacker could do with it. If the problem involves the local review UI, say how it is reached.

Please give us a reasonable time to fix the problem before you disclose it.

## What is in scope

ReasonLedger is a local developer tool. The reports that matter most are:

- the local review UI (`reasonledger ui`): anything that lets a web page or another local user read
  or change a ledger, bypass its token, Origin or Host checks, or reach files outside the repository;
- the MCP server: anything that makes it write outside `.reasonledger/` or listen on a network;
- the PII and secret linter letting a real secret or personal identifier into a decision record;
- the packages themselves: a published file that does not match this repository.

The linter is a safety net for accidents. A secret with no recognisable shape passing it is a known
limit, not a vulnerability.
