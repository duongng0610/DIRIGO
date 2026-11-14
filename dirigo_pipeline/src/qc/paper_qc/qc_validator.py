from .paper_qc import (
    PaperQCContext,
    run_all_paper_qc,
)


def validate_all_qc(
    expected,
    actual,
    mapping,
):
    context = PaperQCContext(
        mapping=mapping,
        expected=expected,
        actual=actual,
    )

    return run_all_paper_qc(context)