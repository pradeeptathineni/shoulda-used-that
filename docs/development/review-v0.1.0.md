# v0.1.0 correctness and security review

This maintainer review was completed on 2026-09-17 before the release tag. It covered the public
contracts, runtime source, state boundary, GitHub adapter, fixtures, CLI, generated schemas,
package contents, workflows, and release helpers. The review looked specifically for a path that
could mutate GitHub or a target repository, attach evidence to the wrong subject, accept partial
source data, replace immutable evidence, disclose credentials, or publish an unverified artifact.

## Findings resolved before release

- A material recheck wrote a snapshot and then advanced the accepted baseline. The snapshot is
  still retained as evidence, but only semantic no-op and refresh-only outcomes can now advance
  the baseline. Repeated material rechecks continue to compare with the same last-known-good
  receipt.
- Fixture loading checked a path before reading it but did not prove that the opened file was the
  same inode. The loader now compares `lstat` and open-file identities, accepts only a regular
  file, and enforces the size bound on the opened stream.
- An exact GitHub repository locator was allowed to reach `gh` before canonical validation. The
  adapter now reduces the input to lowercase `owner/repo` first, so an option-shaped value cannot
  cross the subprocess boundary as an endpoint.
- Invalid GitHub field types could escape as generic validation failures. Repository evidence is
  now accepted as a complete canonical candidate or rejected with a typed source-schema error.
- A List projection was validated after local saved items were written. Projection scope and the
  complete sealed plan are now validated before the first saved-item write, preventing invalid
  input from leaving partial state.
- A decision using `--from` could name a repository absent from the cited check. Bound decisions
  must now concern a candidate actually observed in that check.
- Public predicate trees and candidate explanations could interleave soft filters before hard
  gates. Both now preserve the documented exclusion, hard-gate, typed-filter, expression, and
  limit precedence.
- Fine-grained GitHub token prefixes, timezone-naive receipt timestamps, malformed set-like
  values, missing source locators, and a string-valued fixture source each received explicit
  handling and regression coverage.

## Executed evidence

The complete local gate passed with 88 tests and 96% branch-aware coverage. Ruff formatting and
linting, strict mypy, generated-schema comparison, repository/privacy validation, actionlint,
zizmor, typos, and all 21 documentation links passed. A hash-locked audit of the runtime
dependency export reported no known vulnerabilities. The sdist and wheel build completed from an
isolated PEP 517 environment.

The source audit found only local coordinator state writes. GitHub access is restricted to fixed
argument-vector `GET` calls through `gh`; `apply` and `verify` have no executor and fail closed.
No target-project write implementation, star operation, List mutation, token request, shell
execution, PyPI upload, runtime model, or hidden network client exists in the release boundary.

## Deliberate limits

The file state design is single-user and single-writer for this release. GitHub search is an
explicit bounded first-page source, while the authenticated star source requires complete
pagination. Fuzzing, an external human code review, and project-age maintenance evidence are not
claimed. Those are posture or future-scale gaps, not silently passing checks. The annotated tag,
hosted checks on its exact commit, release assets, checksums, SBOM, and GitHub attestations remain
release-time evidence and are verified after the tag is pushed.

## Deletion and reuse audit

After the correctness and security review, the repository was checked with the complete
`ponytail-review` and `ponytail-audit` guidance from `DietrichGebert/ponytail` commit
`e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156` (MIT). The result was `Lean already. Ship.` The
small adapters and type families that initially resemble possible cuts each implement an explicit
release contract: typed transport failures, public export allowlisting, stable human renderings,
conditional GitHub reads, immutable plan validation, or content identity. Each runtime dependency
owns one distinct role. No second framework, single-implementation interface, factory, dead
configuration layer, or standard-library reimplementation survived the audit.

The upstream skill's one-smoke-test minimum was deliberately not applied. The implementation
contract requires algebra, replay, privacy, path-safety, package, platform, and release-chain
evidence, so the stronger test and hosted-validation gates remain.
