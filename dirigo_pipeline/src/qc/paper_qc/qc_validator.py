"""Public facade để gọi toàn bộ Paper QC từ scripts."""

from .paper_qc import (
    PaperQCContext,
    run_all_paper_qc,
)


def validate_all_qc(
    expected,
    actual,
    mapping,
):
    """Tạo PaperQCContext và chạy QC2a-QC4b theo cùng một snapshot."""
    context = PaperQCContext(
        mapping=mapping,
        expected=expected,
        actual=actual,
    )

    return run_all_paper_qc(context)
