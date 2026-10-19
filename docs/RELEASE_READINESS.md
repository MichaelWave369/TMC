# Source-publication readiness

The default branch is a source-release candidate only. A public repository and a secure remotely accessible service are very different things.

## Checks before making this repository public

- [ ] Confirm the new repository's `main` and PR branches contain only independently created commits, with no transplanted Git history, tags, legacy PRs or previous releases.
- [ ] Run Python tests, current-tree source hygiene checks and the history-wide Gitleaks scan successfully **on this repository**, including after merge.
- [ ] Review all tracked source, sample data, dependency licenses, default author/email metadata, GitHub Actions logs and artifacts, webhooks and collaborators.
- [ ] Confirm copyright and authority to distribute all included material under MIT, including all contributed code and third-party dependencies.
- [ ] Inspect `data/sample_capsules.json` to confirm all content is synthetic; never commit real memory databases or support bundles.
- [ ] Enable GitHub private vulnerability reporting and reasonable branch protection where available.
- [ ] Explicitly approve the source visibility change after reviewing the checklist.

## Operating scope

The current HTTP API is unauthenticated, and the old XOR vault transformation is not secure encryption. Use on a trusted loopback interface with disposable/non-sensitive data only. Do not host as a network service until those issues have been fixed and independently tested.

Green checks verify their configured rules, not exhaustive private-data removal or production security.
