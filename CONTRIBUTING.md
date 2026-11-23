# Contributing

Thank you for helping. This page is the short version of what we need from a contribution.

## Licence of your contribution

By submitting a contribution you agree that it is licensed under the Apache License, Version 2.0,
the same terms as the project (section 5 of [`LICENSE`](LICENSE): inbound is outbound). There is no
contributor licence agreement to sign.

## Sign off every commit

We use the [Developer Certificate of Origin](https://developercertificate.org/). Add a
`Signed-off-by` line to each commit with `-s`:

```bash
git commit -s -m "fix(core): handle an empty decisions directory"
```

The line states that you wrote the change or have the right to submit it under the project's
licence. Use your real name and an address you control. A pull request with unsigned commits will
be asked to add the sign-off.

## Before you open a pull request

- Read [`AGENTS.md`](AGENTS.md): it is the engineering charter for humans and agents alike, and it
  governs how code is written here (stack, file size, tests, no dead code).
- Set up a checkout with the steps under *Contributors* in [`docs/install.md`](docs/install.md).
- Use [Conventional Commits](https://www.conventionalcommits.org/), for example
  `feat(cli): add a --short flag to why`.
- Run the checks that CI runs: `ruff`, `mypy` and the phase suites (`./scripts/release_gate.sh`
  runs all of them).
- If you chose between real alternatives, record the decision (AGENTS.md section 10). This project
  uses ReasonLedger on itself.

## Reporting a security problem

Do not open a public issue. Follow [`SECURITY.md`](SECURITY.md).
