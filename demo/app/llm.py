import re
from typing import List

from app.config import (
    MAX_CONTEXT_CHARS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    TEMPERATURE,
    TOP_P,
)
from app.retriever import RetrievedContext


NO_CONTEXT_ANSWER = (
    "Tôi chưa tìm thấy căn cứ pháp luật phù hợp trong dữ liệu hiện có "
    "để trả lời câu hỏi này."
)


class OllamaError(RuntimeError):
    pass


def clean_qwen_thinking(text: str) -> str:
    cleaned = re.sub(
        r"<think>.*?(?:</think>|$)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


def build_context(
    contexts: List[RetrievedContext],
    max_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    blocks = []
    total_chars = 0

    for index, context in enumerate(contexts, start=1):
        block = (
            f"[Nguồn {index}]\n"
            f"ID đoạn: {context.paragraph_id}\n"
            f"ID điều/mục: {context.section_id}\n"
            f"Nội dung:\n{context.text}"
        )
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining].rstrip()
        blocks.append(block)
        total_chars += len(block)

    return "\n\n".join(blocks)


def generate_answer(query: str, contexts: List[RetrievedContext]) -> str:
    context_text = build_context(contexts)
    if not context_text:
        return NO_CONTEXT_ANSWER

    system_prompt = """
Bạn là trợ lý hỏi đáp pháp luật Việt Nam. Hãy trả lời câu hỏi chỉ dựa trên
các đoạn văn bản trong phần NGỮ CẢNH.

Yêu cầu:
- Không tự tạo điều luật, số điều, mức phạt hoặc thủ tục không có trong ngữ cảnh.
- Nếu ngữ cảnh chưa đủ, nói rõ rằng dữ liệu hiện có chưa đủ căn cứ để kết luận.
- Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu.
- Trích dẫn nguồn theo dạng [Nguồn 1], [Nguồn 2] khi sử dụng thông tin.
- Chỉ giải thích văn bản được cung cấp, không đưa ra tư vấn pháp lý cá nhân hóa.
- Trả lời bằng văn bản thuần, không dùng Markdown. Không dùng các ký tự định dạng như *, **, ***, #, --- để in đậm, in nghiêng, tạo tiêu đề hoặc đường kẻ.
""".strip()

    user_prompt = f"""
/no_think

CÂU HỎI:
{query}

NGỮ CẢNH:
{context_text}

Hãy trả lời câu hỏi dựa trên ngữ cảnh trên.
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
        },
    }

    try:
        import requests

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise OllamaError(
            f"Không thể gọi Ollama tại {OLLAMA_BASE_URL}: {exc}"
        ) from exc

    answer = str(data.get("message", {}).get("content", "")).strip()
    if not answer:
        raise OllamaError("Ollama trả về câu trả lời rỗng")
    return clean_qwen_thinking(answer)
