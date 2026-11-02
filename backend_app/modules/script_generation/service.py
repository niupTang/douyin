from .prompts import build_identity_script_prompt
from .schemas import identity_script_schema


def generate_identity_script(run_structured, identity_profile, radar_result, benchmark_analysis=None):
    return run_structured(
        "scriptGeneration",
        build_identity_script_prompt(identity_profile, radar_result, benchmark_analysis),
        identity_script_schema(),
    )
