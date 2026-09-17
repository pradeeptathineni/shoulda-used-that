# Security policy

## Supported versions

Until a later release exists, only the latest `0.1.x` release receives security fixes.

## Reporting

Use GitHub's private vulnerability reporting for this repository. Do not include live credentials, private source, or unrelated personal data in an issue.

## Safety boundary

`v0.1.0` has no live GitHub mutation or target-write path. A report that finds one is security-sensitive. Other high-priority areas are path containment, export allowlists, credential redaction, receipt immutability, hard-gate unknown handling, and source-failure preservation.
