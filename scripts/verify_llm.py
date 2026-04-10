"""
Локальная проверка Gemini без HTTP: из корня проекта:
  python scripts/verify_llm.py
  python scripts/verify_llm.py "Какой у вас статус заказа на вчерашний день?"
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# корень репозитория в PYTHONPATH
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.ai_classifier import AIClassifier  # noqa: E402


async def main() -> None:
    text = " ".join(sys.argv[1:]).strip() or (
        "Сколько будет стоить тираж 1000 визиток на мелованном картоне?"
    )
    r = await AIClassifier().classify_full(text)
    print("model       =", r.model)
    print("intent      =", r.intent)
    print("raw_text    =", repr(r.raw_text))
    print("error       =", r.error)
    print("block_reason=", r.block_reason)
    if r.error:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
