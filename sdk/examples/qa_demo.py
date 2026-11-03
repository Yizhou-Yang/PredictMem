"""Runnable QA demo. Needs an OpenAI-compatible endpoint.

    PREDICTMEM_MODEL=... PREDICTMEM_API_KEY=... PREDICTMEM_BASE_URL=... python examples/qa_demo.py
"""

from predictmem import LLMClient, QAEngine

EVIDENCE = (
    "[2023-04-02] Audrey: I adopted Pixie today.\n"
    "[2023-06-11] Andrew: I went rock climbing with Audrey."
)

EXPANDED = EVIDENCE + "\n[2023-06-20] Audrey: The training course starts in June 2023."


def main() -> None:
    engine = QAEngine(LLMClient())
    result = engine.answer("When did Audrey adopt Pixie?", EVIDENCE, expand=lambda _: EXPANDED)
    print(f"answer={result.answer!r} agreed={result.agreed} expanded={result.expanded}")


if __name__ == "__main__":
    main()
