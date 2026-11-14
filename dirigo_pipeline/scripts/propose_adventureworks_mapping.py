import json
import os
import sys

from pathlib import Path


# Khi chạy trực tiếp script, Python chỉ tự thêm thư mục `scripts/`
# vào sys.path. Thêm project root để import được package `src` nằm
# cạnh thư mục `scripts`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.llm.llm_client import GoogleMappingLLMClient
from src.llm.mapping_proposer import (
    propose_mapping,
    save_mapping_proposal_run,
)


SOURCE_PROFILE_PATH = (
    PROJECT_ROOT
    / "reports"
    / "llm"
    / "adventureworks"
    / "source_profile.json"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "reports"
    / "llm"
    / "adventureworks"
)


def get_required_environment_variable(name: str) -> str:
    """Đọc biến môi trường và báo lỗi rõ nếu chưa cấu hình."""

    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set"
        )

    return value


def load_source_profile() -> dict:
    """Đọc profile AdventureWorks HR được tạo ở bước 1."""

    if not SOURCE_PROFILE_PATH.exists():
        raise FileNotFoundError(
            "AdventureWorks HR source profile does not exist. "
            "Run Source Profiler first. Expected file: "
            f"{SOURCE_PROFILE_PATH}"
        )

    return json.loads(
        SOURCE_PROFILE_PATH.read_text(
            encoding="utf-8",
        )
    )


def main() -> None:
    """Sinh mapping proposal cho năm bảng HumanResources."""

    source_profile = load_source_profile()

    # GOOGLE_API_KEY được GoogleMappingLLMClient tự đọc.
    # Tên model để ngoài source code để dễ thay đổi khi benchmark.
    model = get_required_environment_variable(
        "GOOGLE_LLM_MODEL"
    )

    llm_client = GoogleMappingLLMClient(
        model=model,
    )

    run = propose_mapping(
        source_profile=source_profile,
        dataset_name="adventureworks_hr",
        domain_hint=(
            "AdventureWorks Human Resources domain. The source "
            "contains employees, departments, shifts, employee "
            "department assignment history and employee pay-rate "
            "history. Focus on employee lifecycle (assign and remove from departments and shift), department and "
            "shift assignments, and pay-rate changes ."
        ),
        llm_client=llm_client,
    )

    save_mapping_proposal_run(
        run,
        OUTPUT_DIRECTORY,
    )

    print(
        "Proposal created:",
        OUTPUT_DIRECTORY / "mapping_proposal.json",
    )


if __name__ == "__main__":
    main()
