# Public prior-art receipts

These receipts dogfood the product's decision vocabulary before or alongside implementation. JSON is the machine-readable authority; this page is the human index.

| Receipt | Decision |
|---|---|
| [`language.json`](language.json) | Adopt Python 3.12–3.14 for the first release; reject a language rewrite without a single-binary or native-runtime requirement |
| [`dependencies.json`](dependencies.json) | Give each direct runtime dependency exactly one narrow role and an explicit removal boundary |
| [`cli-filter.json`](cli-filter.json) | Adopt Click plus JMESPath; reject Typer-over-Click and a custom filter language |
| [`canonical-state.json`](canonical-state.json) | Adopt RFC 8785 and plain versioned files; defer SQLite pending measured concurrency/query volume |
| [`github-transport.json`](github-transport.json) | Wrap the official installed `gh` CLI; reject another token store or SDK |
| [`quality-security.json`](quality-security.json) | Use non-duplicative test, lint, type, dependency, source, workflow, and posture tools |
| [`context.json`](context.json) | Adopt deterministic progressive disclosure; reject persistent capture/compression until measured |
| [`sbom-release.json`](sbom-release.json) | Select CycloneDX Python after an executed clean-wheel comparison with Syft; use GitHub-native release and attestation |
| [`vcs-lifecycle.json`](vcs-lifecycle.json) | Treat coherent commits, protected-main pushes, an annotated tag, and immutable GitHub release assets as product evidence |
| [`curation-coordinator.json`](curation-coordinator.json) | Build only the deterministic curation/project/projection residual while keeping GitHub and standards authoritative |
| [`github-curation.json`](github-curation.json) | Use native Stars/Lists APIs behind an additive sealed plan, drift check, operation receipts, and independent readback |
| [`project-inventory.json`](project-inventory.json) | Prefer supplied standards-based SBOMs and bounded explicit inspection; reject a universal manifest parser |
| [`zensical-site.json`](zensical-site.json) | Trial exact Zensical 0.0.62 as a removable static view adapter for the public catalog |
| [`pages-workflow.json`](pages-workflow.json) | Verify public inputs on pull requests and schedules, then deploy only a verified main-branch artifact with official pinned Pages actions |
| [`personal-oss-curation.json`](personal-oss-curation.json) | Use cross-source discovery, explicit quality gates, and human-authored interest boundaries to furnish the public catalog and native GitHub Lists |
| [`membership-apply-scaling.json`](membership-apply-scaling.json) | Use the exact validated membership-mutation result for immediate progress, while retaining operation receipts, final full replay, and independent verification |
| [`public-writing.json`](public-writing.json) | Establish Vale, context-free first reading, and non-authoritative AI-pattern diagnostics |
| [`public-writing-v0.3.json`](public-writing-v0.3.json) | Supersede the narrow entrypoint trial with First Reader and local ZeroSlop review routes across every public surface |
| [`public-writing-v0.4.json`](public-writing-v0.4.json) | Surface existing contextual actions and residual work so the public site shows the decision before the evidence machinery |

Claims are distinct from behavior inspected locally or executed in CI. Dated popularity appears only as discovery evidence and never controls a disposition.
