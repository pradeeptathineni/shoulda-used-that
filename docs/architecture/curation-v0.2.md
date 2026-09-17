# Curated OSS coordinator contract for `v0.2.0`

ShouldaUsedThat coordinates four related jobs without conflating their truth:

1. inspect an explicit project or supplied SBOM without writing to the target;
2. compile reviewed OSS decisions and unresolved discoveries into a deterministic curation;
3. publish an allowlisted catalog that shows what is used, trialed, referenced, watched,
   rejected, or still in the inbox; and
4. propose a small, lossy public projection into native GitHub Stars and Lists.

Canonical JSON receipts are authoritative. GitHub stars are bookmarks and the prerequisite for
Lists. GitHub Lists are public topical projections. Generated Markdown/JSON and the Pages site are
derived views. None may silently become the decision ledger.

## Commands and records

- `inspected TARGET [--sbom PATH]` creates a versioned read-only `ProjectSnapshot` from an explicit
  GitHub repository, local root, SPDX document, or CycloneDX document.
- `checked NEED --in SNAPSHOT_OR_PROJECT` exposes the exact project facts that affect applicability.
- `curated PROFILE_PATH` validates a versioned profile and compiles a deterministic
  `CurationSnapshot`, preserving exclusions, inbox items, stale evidence, and conflicts.
- `projected CURATION_ID --to github-lists --account LOGIN` reads current GitHub state and writes a
  sealed `GitHubProjectionPlan`; it performs no mutation.
- `apply PLAN_ID --fingerprint FINGERPRINT` accepts only `plan_kind: github-curation`, refuses CI
  and non-TTY execution, rechecks identity/capabilities/drift/caps, and records every attempted
  additive operation.
- `verify APPLY_RECEIPT_ID` independently reads every claimed star, List, description, and
  membership postcondition.
- `exported CURATION_ID --public --output DIRECTORY` constructs a staged allowlisted package,
  validates it, and atomically replaces the destination.
- `rechecked TARGET --material-only` replays the original policy and emits no semantic change for
  unchanged inputs.

New canonical records are `ProjectSnapshot`, `CurationProfile`, `CollectionDefinition`,
`CurationEntry`, `CurationSnapshot`, `GitHubProjectionPlan`, `ApplyReceipt`, `VerifyReceipt`, and
`PublicCatalogExport`. Unknown schema versions fail closed; existing `v0.1.0` records remain
readable and immutable.

## Mutation boundary

The only live operations this release may execute are:

- star a named public repository;
- create a public List with an exact name and description; and
- add a starred repository to the union of its current and approved List memberships.

Unstar, membership removal, List deletion/rename/privacy change, private-repository exposure,
replacement-style membership updates, CI execution, and unattended scheduled apply are forbidden.
Timeouts after uncertain writes become `indeterminate` and require readback before retry. Partial
execution remains an append-only resumable receipt; rollback never deletes user-authored state.

The first personal-account apply requires the maintainer to approve the exact account, complete
plan fingerprint, ordered operations, and operation caps after seeing the rendered sealed plan.

## Public catalog boundary

The first public profile is `curation/profiles/shoulda-used-that.json`. Public export constructs
only allowlisted facts and reviewed decisions. It excludes local paths, private repository
metadata, raw API responses, credentials/scope dumps, private notes, hidden source membership, and
unreviewed model output.

The catalog must remain complete with GitHub List projection disabled. It exposes evidence-bound
roles and needs, dated popularity metadata, alternatives, freshness, source attribution, and
reconsideration triggers—never a magic score or timeless “best” claim.

## Presentation and upkeep

Zensical is a development-only, replaceable shell for generated Markdown, built-in client-side
search, tags, responsive navigation, and GitHub Pages output. The site makes no third-party runtime
requests and carries no analytics. Its desktop and mobile renders, keyboard focus, contrast,
overflow, search, links, and empty states are verified before release.

One-shot upkeep is documented only after two identical runs produce a semantic no-op and a fixture
change produces only the expected material diff. Local schedulers and public Actions may invoke
read-only checks/builds. They may never receive a personal token or call `apply`.

## Release gates

`v0.2.0` requires full local and clean-install validation, deterministic regeneration, hosted CI
and security checks on the exact merge candidate, a live externally fetched Pages site, resolved
review findings, an annotated tag matching `main` and `origin/main`, inspected assets/checksums/
runtime SBOM/attestations, and final replay. PyPI remains intentionally unpublished.
