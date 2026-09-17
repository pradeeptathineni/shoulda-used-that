# Catalog scale validation

The public catalog keeps canonical records as bounded JSON source shards, renders portable
Markdown/JSON, and treats Zensical as a replaceable view adapter. This measurement checks that the
representation remains usable beyond the initial profile without adding a database, custom search
service, or frontend application.

## Targets

For a 5,000-entry synthetic reviewed catalog on the development machine:

- compile one semantic snapshot in under 5 seconds;
- render the allowlisted source site in under 30 seconds;
- complete a strict static build in under 120 seconds;
- keep the built static site under 200 MB and its client search index under 25 MB;
- retain searchable first, middle, and last repositories plus need, alias (`DevOps`), disposition,
  and collection probes;
- make an immediate second export a semantic no-op.

These are bounded development targets, not cross-machine performance guarantees.

## Measured results

Command:

```console
uv run python scripts/benchmark_catalog.py --sizes 1000 5000
```

Environment: Darwin x86_64, Python 3.14.7, Zensical 0.0.62. The runs were local and made no
network requests.

| Entries | Compile | Public render | Strict static build | Generated source | Built site | Search index | Search probes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1,000 | 0.209 s | 3.088 s | 14.077 s | 7,012,852 B | 26,833,972 B | 3,707,844 B | 7/7 present |
| 5,000 | 1.030 s | 15.563 s | 76.749 s | 34,942,508 B | 130,762,772 B | 18,430,488 B | 7/7 present |

The 5,000-entry input used five deterministic 1,000-entry shards so every source remained below the
5 MiB per-source safety cap while compiling into one snapshot. Both second exports were semantic
no-ops.

## Design finding

An initial 1,000-entry build using automatic navigation produced 348,071,836 bytes because every
detail page embedded every other entry in global navigation. Explicit index-only navigation reduced
the same case to 26,833,972 bytes and kept detail pages available through collection links and
client search. The 5,000-entry output then grew approximately linearly and met every target.

Pagefind, SQLite/Datasette, and a custom application remain deferred. Reopen their reuse gates only
if a future measured corpus misses one of the explicit targets above or real search relevance no
longer satisfies repository, need, alias, disposition, and collection queries.
