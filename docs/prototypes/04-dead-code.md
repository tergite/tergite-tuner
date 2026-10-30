# Step 4 sign-off: what nothing used is gone

Step 4 removed 3,586 lines of the package's Python (29,769 to 26,457), with no behaviour change apart from the three commits named in section 3. The baselines shrank as the dead code went:

| Baseline | Before | After |
| --- | --- | --- |
| ruff | 650 | 488 |
| pylint | 86 | 70 |
| vulture | 55 | 26 |
| style guide | 865 | 747 |

## 1. Behaviour is unchanged

```bash
uv run pytest tergite_tuner -n auto -q
uv run python -m dev.lint.baseline ruff && uv run python -m dev.lint.baseline pylint && uv run python -m dev.lint.baseline vulture
```

`456 passed, 5 skipped, 3 xfailed`, and the baselines pass. The reanalysis goldens and the compiled-program digests did not move.

## 2. Performance is no worse

```bash
dev/perf/record.sh /tmp/perf-step4
uv run python -m dev.perf.compare dev/perf/baselines/macos-arm64 /tmp/perf-step4
```

No measure more than 15% worse.

## 3. The changes users can see

- `NodeEnum.PROCESS_TOMOGRAPHY_SSRO` is gone, with the reset chevron and process tomography nodes, which could not run.
- A malformed TOML config raises `tomllib.TOMLDecodeError`, where it raised `toml.TomlDecodeError`.
- CZ chevron's analysis no longer raises `IndexError` when it finds no working points: the line that raised was dead.

## 4. What stayed, and why

The vulture baseline's 26 remaining entries are called by name or are public:
- the export models behind string annotations, and the type-only `CompiledSchedule` imports;
- quantify's `generate_device_config` and `generate_edge_config` hooks;
- `RedisStore`'s public `delete_many`, `prune_fields` and `save_field` (step 9.4 decides them);
- the logger's handler methods (step 9.5);
- the Clifford helpers (step 8).
