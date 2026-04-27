from tergite_autocalibration.config.globals import REDIS_CONNECTION
import json

def _export_initial_cz_parameters(coupler:str):
    cz_pulse_frequency = REDIS_CONNECTION.hget(
        f"couplers:{coupler}", "cz_pulse_frequency"
    )

    cz_pulse_amplitude = REDIS_CONNECTION.hget(
        f"couplers:{coupler}", "cz_pulse_amplitude"
    )

    cz_pulse_duration = REDIS_CONNECTION.hget(
        f"couplers:{coupler}", "cz_pulse_duration"
    )

    return dict(
        cz_pulse_frequency=cz_pulse_frequency, 
        cz_pulse_amplitude=cz_pulse_amplitude, 
        cz_pulse_duration=cz_pulse_duration
        )

def export_initial_cz_parameters(couplers:list[str]):
    dct = dict()
    for coupler in couplers:
        dct[coupler] = _export_initial_cz_parameters(coupler)

    with open("./cz_initial_parameters.json", "w+") as f:
        json.dump(dct, f, indent=4)

def load_initial_cz_parameters():
    with open("./cz_initial_parameters.json", "r") as f:
        dct = json.load(f)

    for coupler in dct:
        for key in dct[coupler]:
            REDIS_CONNECTION.hset(f"couplers:{coupler}", key, dct[coupler][key])

if __name__ == "__main__":
    export_initial_cz_parameters(["q11_q12", "q12_q13", "q13_q14", "q14_q15"])
    # load_initial_cz_parameters()