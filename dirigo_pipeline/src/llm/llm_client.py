from __future__ import annotations

import os

from dataclasses import dataclass
from typing import Any, Protocol

from google import genai
from google.genai import types

from .mapping_models import MappingProposal


# response_json_schema của Gemini hỗ trợ phần lớn JSON Schema nhưng
# không hỗ trợ một số metadata mà Pydantic tự sinh cho field có default.
_UNSUPPORTED_GOOGLE_SCHEMA_KEYS = {
    "default",
    "examples",
    "deprecated",
    "readOnly",
    "writeOnly",
}


def build_google_response_json_schema() -> dict[str, Any]:
    """
    Sinh JSON Schema cho Gemini từ MappingProposal.

    Không dùng `response_schema=MappingProposal` vì Google SDK sẽ
    chuyển schema sang OpenAPI Schema nội bộ. Kiểu nội bộ đó không
    chấp nhận `additionalProperties` do Pydantic extra="forbid" sinh
    ra và API sẽ trả INVALID_ARGUMENT.

    `response_json_schema` nhận JSON Schema trực tiếp và hỗ trợ
    additionalProperties. Hàm chỉ bỏ những metadata không được Gemini
    hỗ trợ; schema Pydantic gốc không bị thay đổi.
    """

    def sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if key not in _UNSUPPORTED_GOOGLE_SCHEMA_KEYS
            }

        if isinstance(value, list):
            return [sanitize(item) for item in value]

        return value

    return sanitize(MappingProposal.model_json_schema())


@dataclass(frozen=True)
class LLMGenerationResult:
    """
    Kết quả chung từ LLM adapter.

    Mapping Proposer không cần biết SDK cụ thể của provider.
    """

    proposal: MappingProposal

    provider: str
    model: str

    response_id: str | None
    usage: dict[str, Any]


class MappingLLMClient(Protocol):
    """
    Interface mà mọi LLM provider phải triển khai.

    Sau này có thể viết Azure/OpenAI/local-model adapter
    mà không sửa Mapping Proposer.
    """

    def generate_mapping(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMGenerationResult:
        ...


class GoogleMappingLLMClient:
    """
    Google Gemini adapter sử dụng Google Gen AI SDK và
    Pydantic structured output.

    API key được đọc từ biến môi trường GOOGLE_API_KEY.
    Không ghi API key trực tiếp vào source code hoặc YAML mapping.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        client: genai.Client | None = None,
    ) -> None:
        if not model:
            raise ValueError("LLM model must not be empty")

        resolved_api_key = api_key or os.getenv("GOOGLE_API_KEY")

        # Khi test có thể truyền fake/injected client nên không bắt buộc
        # GOOGLE_API_KEY. Khi tạo client thật, key phải tồn tại.
        if client is None and not resolved_api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set"
            )

        self.model = model
        self.client = client or genai.Client(
            api_key=resolved_api_key,
        )

    def generate_mapping(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMGenerationResult:
        """
        Gửi source profile và nhận MappingProposal đã parse.

        Google SDK sinh response schema từ MappingProposal và trả
        kết quả đã parse qua response.parsed.
        """

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                # Dùng JSON Schema trực tiếp để giữ được
                # additionalProperties=false của StrictModel.
                response_json_schema=(
                    build_google_response_json_schema()
                ),
                # Mapping proposal cần ổn định giữa các lần chạy.
                # Dù vậy vẫn phải lưu model, prompt hash và chạy QC.
                temperature=0,
            ),
        )

        proposal = getattr(response, "parsed", None)

        # Một số phiên bản SDK/model có thể trả response.text nhưng
        # không điền response.parsed. Khi đó vẫn dùng chính Pydantic
        # model để validate JSON, không tin trực tiếp chuỗi trả về.
        if proposal is None:
            response_text = getattr(response, "text", None)

            if not response_text:
                raise RuntimeError(
                    "Gemini returned no structured mapping proposal"
                )

            proposal = MappingProposal.model_validate_json(
                response_text
            )

        # Bảo đảm adapter luôn trả đúng MappingProposal ngay cả khi
        # fake client hoặc SDK trả dictionary.
        if not isinstance(proposal, MappingProposal):
            proposal = MappingProposal.model_validate(proposal)

        usage: dict[str, Any] = {}
        usage_metadata = getattr(
            response,
            "usage_metadata",
            None,
        )

        if usage_metadata is not None:
            if hasattr(usage_metadata, "model_dump"):
                usage = usage_metadata.model_dump()
            else:
                usage = {
                    "raw": str(usage_metadata),
                }

        return LLMGenerationResult(
            proposal=proposal,
            provider="google",
            model=self.model,
            response_id=getattr(response, "response_id", None),
            usage=usage,
        )
