# Configuration

A run is configured by a `.env` file and four config files. Every setting can also be given
in code.

## The `.env` file

Copy the [example](../.example.env), which lists and explains every setting:

```shell
cp .example.env .env
```

The settings you will change most:

| Setting | Meaning |
| --- | --- |
| `CLUSTER_IP` | the Qblox cluster's address |
| `CLUSTER_MODE` | `real`, `dummy` (a dummy cluster, with made-up data), or `re_analyse` (no hardware; analyse recorded data) |
| `SPI_MODE` | `real` or `dummy`, for the SPI rack that drives the couplers |
| `QUBITS`, `COUPLERS` | what to calibrate, comma-separated: `q00,q01` and `q00_q01` |
| `TARGET_NODE` | the node to stop at, e.g. `qubit_01_spectroscopy` |
| `DATA_DIR` | where each run writes its data; `out` by default |
| `CALIBRATION` | an earlier run's `results.json`, to start from its values |

### Recalibrating or tuning up

`IS_RECALIBRATION` and `IGNORE_SPEC` both default to `True`: a run recalibrates the nodes,
whatever their calibration status, without resetting the cluster or setting the couplers'
currents. Set both to `False` to tune up the device from scratch, from the device config.

### Where a setting comes from

Every field of `SessionContext` can be set in three places. The first one found wins:

1. a keyword argument to an entry point, such as `tune_device(qubits=["q00"])`;
2. an environment variable, in upper case (`QUBITS`);
3. the `.env` file.

## The config files

The `.env` file names their paths. Each has an example at the repository root.

| File | Holds |
| --- | --- |
| [`device_config.toml`](../device_config.example.toml) | the chip: initial qubit, resonator and coupler values, under `all` or per element |
| [`node_config.toml`](../node_config.example.toml) | per-node overrides that apply while the node runs, under `all` or per qubit |
| [`cluster_config.json`](../cluster_config.example.json) | quantify-scheduler's [hardware compilation config](https://quantify-os.org/docs/quantify-scheduler/v0.27.1/tutorials/Compiling%20to%20Hardware.html#hardware-compilation-configuration) |
| [`spi_config.toml`](../spi_config.example.toml) | optional: which SPI module and DAC drives each coupler |

## Giving the configs in code

Each file's contents can be passed to an entry point as an object instead:

```python
from tergite_tuner import tune_device
from tergite_tuner.config.types import ClusterConfig, DeviceConfig, NodeConfig, SpiConfig

_, results = tune_device(
    device_config=DeviceConfig(
        name="matthias",
        resonator={
            "all": {"attenuation": 10},
            "q01": {"VNA_frequency": 6433000000.0},
            "q02": {"VNA_frequency": 6290000000.0},
        },
        # ...
    ),
    node_config=NodeConfig.model_validate(
        {
            "qubit_spectroscopy_vs_current": {
                "all": {"spec.spec_duration": 6e-6, "reset.duration": 200e-6},
            }
        }
    ),
    spi_config=SpiConfig.model_validate(
        {
            "q11_q12": {"spi_module_number": 1, "dac_name": "dac0", "edge_group": 1},
            "q12_q13": {"spi_module_number": 2, "dac_name": "dac1", "edge_group": 2},
        }
    ),
    cluster_config=ClusterConfig.model_validate(
        {
            "config_type": "quantify_scheduler.backends.qblox_backend.QbloxHardwareCompilationConfig",
            "hardware_description": {
                "clusterA": {
                    "instrument_type": "Cluster",
                    "ref": "internal",
                    "modules": {"1": {"instrument_type": "QCM_RF"}},
                }
            },
            # ...
        }
    ),
)
```
