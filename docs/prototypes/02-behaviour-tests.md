# Step 2 sign-off: behaviour pinned by tests

## 1. The pins pass

```bash
uv run pytest tergite_tuner/tests/test_reanalysis_goldens.py tergite_tuner/tests/test_schedule_goldens.py tergite_tuner/tests/test_public_api.py -q
uv run pytest tergite_tuner/tests/test_tune_up.py -q
```

The first gives `56 passed` (19 reanalysis goldens, 33 compiled programs, 4 entry points). The second takes about five minutes and gives `29 passed, 4 xfailed`; the four are the known defects in REFACTOR.md step 2.1.

## 2. The pins catch a change

- **Compiled programs:** in `tergite_tuner/lib/nodes/qubit_control/rabi_oscillations/measurement.py`, change the first `phase=0,` to `phase=1,`. `test_schedule_goldens.py -k rabi` fails both Rabi nodes. Revert it.
- **Analysis values:** in `tergite_tuner/tests/fixtures/goldens/punchout.json`, change any `measure:pulse_amp` value. `test_reanalysis_goldens.py -k punchout` fails. Revert it.
- **A known failure that gets fixed:** remove `NodeEnum.CZ_CHEVRON` from `_KNOWN_FAILURES` in `test_tune_up.py`. Its case fails, as the defect is still there. Restore it.

## 3. The digests do not depend on the machine

```bash
PYTHONHASHSEED=12345 uv run pytest tergite_tuner/tests/test_schedule_goldens.py -q
```

`33 passed`. CI runs the same tests on Linux; a green pipeline confirms the digests hold there too.
