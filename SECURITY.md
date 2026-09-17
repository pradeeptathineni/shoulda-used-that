# Security policy

## Supported versions

Only the latest `0.2.x` release receives security fixes. The immutable `0.1.x` line remains
available for provenance but is no longer the supported line.

## Reporting

Use [GitHub's private vulnerability reporting](https://github.com/pradeeptathineni/shoulda-used-that/security/advisories/new)
for this repository. Do not include live credentials, private source, or unrelated personal data in
an issue. General security posture and published advisories are available on the repository's
[Security page](https://github.com/pradeeptathineni/shoulda-used-that/security).

## Safety boundary

`v0.2.0` has no target-write or destructive GitHub path. Its only live GitHub mutations are the
interactive, exact-fingerprint-bound additive operations documented in the
[operator runbook](docs/operations/github-curation.md): create a public List, star a public
repository, and add the repository to the union of current and approved memberships. A route that
can unstar, remove membership, delete/rename/change List privacy, expose a private repository,
bypass drift/caps/identity/TTY/CI checks, or mutate from a schedule is security-sensitive. Other
high-priority areas are path containment, public-export allowlists, credential redaction, receipt
immutability, hard-gate unknown handling, and source-failure preservation.
