import os
import sys

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.pipeline import PipelineConfig, run_pipeline


def get_required_environment_variable(
    name: str,
) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Environment variable '{name}' is not set"
        )

    return value


def main() -> None:
    config = PipelineConfig(
        project_root=PROJECT_ROOT,
        dataset_name="adventureworks_hr",
        database_path=(
            PROJECT_ROOT
            / "data/raw/adventureworks_hr.sqlite"
        ),
        runtime_database_path=(
            "data/raw/adventureworks_hr.sqlite"
        ),
        domain_hint=(
            "AdventureWorks Human Resources domain with "
            "employees, departments, shifts, department "
            "assignment history and employee pay-rate history."
        ),
        model=get_required_environment_variable(
            "GOOGLE_LLM_MODEL"
        ),
        published_mapping_path=(
            PROJECT_ROOT
            / "configs/mappings/adventureworks_hr_llm.yaml"
        ),
        reports_root=(
            PROJECT_ROOT / "reports/llm"
        ),
        outputs_root=(
            PROJECT_ROOT / "outputs"
        ),
        max_llm_repairs=2,
    )

    summary = run_pipeline(config)

    print("Pipeline completed successfully")
    print("Output:", summary["output_directory"])
    print("Mapping:", summary["mapping"])


if __name__ == "__main__":
    main()