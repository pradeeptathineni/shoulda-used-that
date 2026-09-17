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

Claims are distinct from behavior inspected locally or executed in CI. Dated popularity appears only as discovery evidence and never controls a disposition.
