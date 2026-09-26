"""
Lab 11 — Main Entry Point

Chạy từ **gốc repo** (không cần ``cd src``):

    python src/main.py              # Core: Checkpoint 2 → 3 → 4
    python src/main.py --part 2     # Checkpoint 2 — guardrails
    python src/main.py --part 3     # Checkpoint 3 — pipeline / results.json
    python src/main.py --part 4     # Checkpoint 4 — Red / Red Advance
    python src/main.py --chat blue  # Interactive chat with guarded Blue
    python src/main.py --chat red   # Interactive chat with unguarded Red

File JSON luôn ghi vào ``<repo>/outputs/`` (không phụ thuộc thư mục hiện tại).

Tham khảo (không chấm, không có CLI): ``src/testing/``, ``src/hitl/``.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Cho phép chạy ``python src/main.py`` từ gốc repo
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.config import get_openrouter_api_key, setup_api_key


async def _chat_loop(team: str, agent, runner, model_label: str, api_key: str):
    from core.utils import chat_with_agent

    print(f"\nChat {team} với {model_label} — gõ 'thoát' hoặc 'exit' để kết thúc.")
    if team == "Blue":
        print("Blue có input/output guardrails và rate limiter; route miễn phí hiện vẫn có giới hạn tốc độ.\n")
    else:
        print("Red không có guardrails mạnh và được nhúng canary giả của lab. Chỉ dùng để demo.\n")

    while True:
        try:
            prompt = input("Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nĐã kết thúc phiên chat.")
            break

        if prompt.lower() in {"thoát", "thoat", "exit", "quit"}:
            print("Đã kết thúc phiên chat.")
            break
        if not prompt:
            continue

        try:
            response, _ = await chat_with_agent(agent, runner, prompt)
            print(f"{team}: {response or '(không có nội dung trả lời)'}\n")
        except Exception as exc:
            # Show the provider's useful status while redacting the configured key.
            status = getattr(exc, "status_code", None)
            detail = getattr(exc, "message", None)
            if detail:
                key = api_key
                detail = str(detail).replace(key, "[REDACTED]") if key else str(detail)
                detail = detail[:300]
            status_text = f" HTTP {status}" if status else ""
            detail_text = f": {detail}" if detail else ""
            print(
                f"Không gọi được model ({type(exc).__name__}{status_text}){detail_text}. "
                "Kiểm tra model, kết nối, hạn mức và cấu hình key trong .env.\n"
            )


async def chat_blue():
    """Start an interactive terminal chat with Blue and its guardrail plugins."""
    if not get_openrouter_api_key():
        print("Thiếu OPENROUTER_API_KEY. Hãy kiểm tra .env; không dán key vào terminal/chat.")
        return

    from agents.agent import create_blue_agent
    from assignment.pipeline import build_production_plugins
    from core.config import blue_provider_label

    agent, runner = create_blue_agent(build_production_plugins(use_llm_judge=False))
    await _chat_loop("Blue", agent, runner, blue_provider_label(), get_openrouter_api_key())


async def chat_red():
    """Start an interactive chat with the intentionally unguarded Red agent."""
    from agents.agent import create_red_agent_default
    from core.config import (
        get_google_api_key,
        get_openai_api_key,
        get_red_provider,
        red_provider_label,
    )

    provider = get_red_provider()
    api_key = get_google_api_key() if provider == "gemini" else get_openai_api_key()
    if not api_key:
        key_name = "GOOGLE_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
        print(f"Thiếu {key_name}. Hãy kiểm tra .env; không dán key vào terminal/chat.")
        return

    agent, runner = create_red_agent_default()
    await _chat_loop("Red", agent, runner, red_provider_label("default"), api_key)


async def part2_guardrails():
    """Checkpoint 2: input + output guardrails."""
    print("\n" + "=" * 60)
    print("CHECKPOINT 2: Guardrails")
    print("=" * 60)

    print("\n--- Input Guardrails ---")
    from guardrails.input_guardrails import (
        test_injection_detection,
        test_topic_filter,
        test_input_plugin,
    )
    test_injection_detection()
    print()
    test_topic_filter()
    print()
    await test_input_plugin()

    print("\n--- Output Guardrails ---")
    from guardrails.output_guardrails import test_content_filter
    test_content_filter()
    print("(LLM-as-Judge / NeMo — optional, skipped)")


async def part3_assignment_suite():
    """Checkpoint 3: defense suite → outputs/results.json."""
    print("\n" + "=" * 60)
    print("CHECKPOINT 3: Assignment suite → outputs/*.json")
    print("=" * 60)

    from assignment.pipeline import (
        build_production_plugins,
        build_observability,
        run_assignment_suite,
    )

    try:
        plugins = build_production_plugins(use_llm_judge=False)
        audit, monitor = build_observability()
        pipeline = {"plugins": plugins, "audit": audit, "monitor": monitor}
        result = await run_assignment_suite(pipeline)
        print("Suite finished.")
        print("Wrote outputs under repo outputs/")
        return result
    except NotImplementedError as e:
        print(
            "Chưa xong Checkpoint 3 (src/assignment/pipeline.py). "
            "Hoàn thành rồi chạy lại từ gốc repo:\n"
            "  python src/main.py --part 3"
        )
        print(f"Detail: {e}")
        return None


async def part4_attacks():
    """Checkpoint 4: attack Red, then Red Advance (bonus)."""
    print("\n" + "=" * 60)
    print("CHECKPOINT 4: Red + Red Advance")
    print("=" * 60)

    from agents.agent import create_red_agent_default, test_agent
    from agents.guards_agent import create_red_agent_advance
    from attacks.attacks import run_attacks, save_attack_results

    red_default, red_default_runner = create_red_agent_default()
    await test_agent(red_default, red_default_runner)

    print("\n--- Attacks on Red ---")
    unsafe_results = await run_attacks(
        red_default, red_default_runner, target_name="red_default"
    )

    print("\n--- Attacks on Red Advance (bonus B2 tối đa +10 nếu LEAKED; chọn 1) ---")
    red_advance, red_advance_runner = create_red_agent_advance()
    guards_results = await run_attacks(
        red_advance, red_advance_runner, target_name="red_advance"
    )

    save_attack_results(
        unsafe_results=unsafe_results,
        guards_results=guards_results,
        ai_attacks=None,
    )

    red_leaks = sum(1 for r in unsafe_results if r.get("leaked"))
    bonus_leaks = sum(1 for r in guards_results if r.get("leaked"))
    print("\n" + "=" * 60)
    print(
        f"Red leaks (B1 tối đa +5): {red_leaks}  |  "
        f"Red Advance leaks (B2 tối đa +10): {bonus_leaks}  "
        "→ chọn MỘT bonus (B1 hoặc B2); grader replay"
    )
    from core.config import is_harder_model, provider_label

    if is_harder_model():
        print(f"Đang dùng model khó ({provider_label()}) — tuỳ chọn khi săn bonus.")
    print("=" * 60)

    return {
        "red_default": unsafe_results,
        "red_advance": guards_results,
        "unsafe": unsafe_results,
        "guards": guards_results,
    }


async def main(parts=None):
    setup_api_key()

    if parts is None:
        parts = [2, 3, 4]  # Core: CP2 → CP3 → CP4

    for part in parts:
        if part == 2:
            await part2_guardrails()
        elif part == 3:
            await part3_assignment_suite()
        elif part == 4:
            await part4_attacks()
        else:
            print(f"Unknown part: {part}. Dùng --part 2, 3, hoặc 4.")

    print("\n" + "=" * 60)
    print("Lab 11 complete! Check your results above.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Lab 11: Guardrails / HITL / Red Team — "
            "--part khớp Checkpoint (2, 3, 4)"
        )
    )
    parser.add_argument(
        "--part",
        type=int,
        choices=[2, 3, 4],
        help="2=CP2 guardrails · 3=CP3 suite · 4=CP4 red-team",
    )
    parser.add_argument(
        "--chat",
        nargs="?",
        const="blue",
        choices=["blue", "red"],
        metavar="TEAM",
        help="Mở chat Blue hoặc Red (mặc định: blue)",
    )
    args = parser.parse_args()

    if args.chat and args.part is not None:
        parser.error("Dùng --chat hoặc --part, không dùng đồng thời.")
    if args.chat == "blue":
        asyncio.run(chat_blue())
    elif args.chat == "red":
        asyncio.run(chat_red())
    elif args.part:
        asyncio.run(main(parts=[args.part]))
    else:
        asyncio.run(main())
