#goi llm 
#Cần thiết lập biến môi trường : 
# $env:GOOGLE_API_KEY="..."
# $env:GOOGLE_LLM_MODEL="gemini-2.5-pro"
import argparse
import json
import os

# Phải import trước src để thêm project root vào sys.path.
from pipeline_paths import (
    PROJECT_ROOT,
    PipelinePaths,
)

from dotenv import load_dotenv

from src.llm.llm_client import (
    GoogleMappingLLMClient,
)
from src.llm.mapping_proposer import (
    propose_mapping,
    save_mapping_proposal_run,
)

def get_required_environment_variable(
    name: str,
) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Environment variable '{name}' is not set. "
            f"Check {PROJECT_ROOT / '.env'}"
        )

    return value



def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("sqlite_file")

    parser.add_argument(
        "--domain-hint",
        default=None,
        help="Optional business-domain description",
    )

    return parser.parse_args()



def main() -> None:
    args = parse_arguments()

    paths = PipelinePaths.from_sqlite_file(
        args.sqlite_file
    )

    # Đọc biến từ .env tại project root.
    # override=False: biến PowerShell nếu có sẽ được ưu tiên hơn .env.
    load_dotenv(
        dotenv_path=PROJECT_ROOT / ".env",
        override=False,
    )

    google_api_key = (
        get_required_environment_variable(
            "GOOGLE_API_KEY"
        )
    )

    google_model = (
        get_required_environment_variable(
            "GOOGLE_LLM_MODEL"
        )
    )

    if not paths.source_profile_path.exists():
        raise FileNotFoundError(
            "Source profile does not exist. "
            "Run step 01 first: "
            f"{paths.source_profile_path}"
        )

    source_profile = json.loads(
        paths.source_profile_path.read_text(
            encoding="utf-8",
        )
    )

    domain_hint = args.domain_hint or (
        f"Infer the business domain of dataset "
        f"'{paths.dataset_name}' only from source_profile. "
        "Do not invent tables or columns."
    )

    # GoogleMappingLLMClient đọc GOOGLE_API_KEY
    # từ environment đã được load phía trên.
    llm_client = GoogleMappingLLMClient(
        model=google_model,
    )

    proposal_run = propose_mapping(
        source_profile=source_profile,
        dataset_name=paths.dataset_name,
        domain_hint=domain_hint,
        llm_client=llm_client,
    )

    save_mapping_proposal_run(
        proposal_run,
        paths.work_directory,
    )

    print("MAPPING PROPOSAL COMPLETED")
    print("Dataset:", paths.dataset_name)
    print("Model:", google_model)
    print("Proposal:", paths.mapping_proposal_path)


if __name__ == "__main__":
    main()