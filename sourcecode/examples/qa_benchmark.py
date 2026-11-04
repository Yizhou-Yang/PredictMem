"""Thin QA benchmark example: data loading only, algorithm comes from the SDK."""

import json

from predictmem import LLMClient, QAEngine
from predictmem.benchmarks import QAExample, run

EXAMPLE = QAExample(
    question="When did Audrey adopt Pixie?",
    gold="2023-04-02",
    pool=[
        "[2023-04-02] Audrey: I adopted Pixie today.",
        "[2023-06-11] Andrew: I went rock climbing with Audrey.",
    ],
    expand=lambda pool: pool + ["[2023-04-02] Audrey: Pixie is my new dog."],
)


def main() -> None:
    rows = run(QAEngine(LLMClient()), [EXAMPLE], k=2, expand_k=4)
    print(json.dumps(rows[0], indent=2))


if __name__ == "__main__":
    main()
