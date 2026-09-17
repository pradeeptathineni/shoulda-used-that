# Read-only upkeep and scheduling

Scheduling wraps one deterministic command; it does not add a daemon, scheduler framework, model
call, or unattended personal-account authority.

## One-shot command

Prepare the exact locked environment once:

```console
uv sync --all-groups --frozen
```

Then run:

```console
./scripts/upkeep_catalog.sh
```

The command uses the existing environment without synchronizing it, verifies committed catalog
generation, performs a clean strict static build, checks local links and fragments, confirms all
five search probes, rejects third-party runtime resources, and proves that `docs/curation` did not
change. It reads only committed public inputs. Its only generated tree is ignored `site/` output;
it never invokes `gh`, `shoulda apply`, a model, or a network fetch.

Two immediate successful runs are semantic no-ops. The public-export tests additionally prove that
one fixture change produces only the expected material files and that a failed staged write leaves
the prior destination intact. A nonzero scheduled exit therefore means drift or a typed build/
verification failure, not an attempted repair.

## macOS launchd

Create `~/Library/LaunchAgents/io.shoulda-used-that.catalog-upkeep.plist` after replacing the two
`/path/to/...` placeholders with absolute paths owned by the operator:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>io.shoulda-used-that.catalog-upkeep</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/shoulda-used-that/scripts/upkeep_catalog.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/shoulda-used-that</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>5</integer>
    <key>Hour</key><integer>4</integer>
    <key>Minute</key><integer>43</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/path/to/logs/shoulda-catalog.out.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/logs/shoulda-catalog.err.log</string>
</dict>
</plist>
```

Validate and load it explicitly:

```console
plutil -lint ~/Library/LaunchAgents/io.shoulda-used-that.catalog-upkeep.plist
launchctl bootstrap "gui/$(id -u)" \
  ~/Library/LaunchAgents/io.shoulda-used-that.catalog-upkeep.plist
launchctl kickstart -k "gui/$(id -u)/io.shoulda-used-that.catalog-upkeep"
```

Inspect the two configured logs and the exit status after the first manual kick. A path, locked
environment, or repository change requires operator review; the job does not install or repair
anything silently.

## systemd user timer

`~/.config/systemd/user/shoulda-catalog.service`:

```ini
[Unit]
Description=Verify the ShouldaUsedThat public catalog

[Service]
Type=oneshot
WorkingDirectory=/path/to/shoulda-used-that
ExecStart=/path/to/shoulda-used-that/scripts/upkeep_catalog.sh
NoNewPrivileges=true
PrivateTmp=true
```

`~/.config/systemd/user/shoulda-catalog.timer`:

```ini
[Unit]
Description=Weekly ShouldaUsedThat public catalog verification

[Timer]
OnCalendar=Thu *-*-* 04:43:00
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

After replacing paths, run `systemd-analyze --user verify` on both files, enable the timer, and
inspect the first service result with `journalctl --user -u shoulda-catalog.service`.

## Cron fallback

After an interactive successful run, an operator may add this entry with explicit paths:

```cron
43 4 * * 4 cd /path/to/shoulda-used-that && ./scripts/upkeep_catalog.sh >> /path/to/logs/shoulda-catalog.log 2>&1
```

Cron has weaker service state and failure visibility than launchd or systemd; use it only when the
host already monitors nonzero exits or the log.

## Public GitHub Actions schedule

`.github/workflows/catalog.yml` runs at minute 43 on Thursday from the default branch. The scheduled
job has only `contents: read`, uses committed public evidence, runs the same one-shot command, and
retains the catalog manifest as an artifact. It cannot deploy Pages, access a personal secret, or
mutate Stars/Lists. Only a verified `main` push or explicit `main` workflow dispatch can enter the
separate Pages deployment job.

GitHub schedules are not a real-time guarantee: runs may be delayed during load, always use the
latest default-branch commit, and can be disabled after repository inactivity. No schedule should
be treated as proof that evidence is current; the dated catalog receipt remains authoritative.

## Personal curation remains manual in `v0.2.0`

Authenticated Stars/Lists reads and projection planning use the existing keyring-backed `gh`
session and can be run manually from the [GitHub curation runbook](github-curation.md). They are not
part of the scheduled script. `apply` and `verify` are never scheduler targets, and no personal PAT
belongs in launchd, systemd, cron, or repository Actions configuration.
