from tergite_tuner import extract_bcc_params

extract_bcc_params(
    qubits = ["q11", "q12", "q13", "q14", "q15"],
    couplers = ["q11_q12", "q12_q13", "q13_q14" , "q14_q15"],
    env_file=".env", format="toml", output="calibration_seed.toml")