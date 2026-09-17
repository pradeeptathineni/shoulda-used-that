# Executed SBOM comparison

On 2026-09-17, CycloneDX Python 7.4.0 and Syft 1.51.1 were run against the same clean Python 3.12
environment containing the built `shoulda-used-that` 0.1.0 wheel and its runtime dependencies.
The installed-environment inventory contained 15 distributions including the project.

| Observation | CycloneDX Python | Syft, default | Syft, Python-only and no file catalogers |
|---|---:|---:|---:|
| Project represented as metadata root | Yes, application | Yes, file | Yes, file |
| Component records | 14 dependencies | 48 | 15, including a duplicate project component |
| Installed distributions covered | 15/15 including root | 15/15 | 15/15 |
| Dependency graph nodes | 15 | 7 | 7 |
| Temporary-environment path references | 0 | 34 | 0 |
| Reproducible timestamp/serial omission | Yes | No | No |

The tuned Syft run was included so its default file catalogers did not decide the comparison by
themselves. It removed the path leakage and file-record noise, but its CycloneDX view still had a
duplicated project representation, a shallower graph, a file-typed root, and volatile timestamp and
serial fields. CycloneDX Python therefore owns the Python runtime-environment SBOM role for
`v0.1.0`. Syft remains a credible multi-ecosystem scanner, but that broader role does not exist in
this release.

The release workflow repeats the selected scan from a clean installed wheel, requests CycloneDX
1.6 reproducible output, writes checksums only after the SBOM exists, and submits every release
asset to GitHub's native provenance attestation action.
