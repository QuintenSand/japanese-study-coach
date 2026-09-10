"""Command-line entry point.

    coach                      interactive chat
    coach "日本語の文"          one-shot explanation
    coach --image shot.png     explain a screenshot (optional prompt after it)
    coach quiz                 review due flashcards
    coach stats                deck summary, no API call
    coach ui                   open the Streamlit app
"""

from __future__ import annotations

import argparse
import sys

import anthropic


def _require_credentials() -> anthropic.Anthropic:
    """Build the client and fail early with a clear message if it has no credentials.

    The SDK resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login`
    profile on its own, but it only raises at request time, so check here.
    """
    client = anthropic.Anthropic()
    if not (client.api_key or client.auth_token or client.credentials):
        sys.exit("No Anthropic credentials found. Export ANTHROPIC_API_KEY or run `ant auth login`.")
    return client


def _print_stats() -> None:
    from .tools import get_store

    store = get_store()
    print(f"backend: {store.name}")
    for k, v in store.stats().items():
        print(f"{k:>10}: {v}")


def _run_ui() -> None:
    import subprocess
    from pathlib import Path

    app = Path(__file__).parent / "ui" / "app.py"
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)]))


def _chat(coach, first_message: str | None = None, image: str | None = None) -> None:
    print("Japanese study coach. Type your text, or 'quit' to exit.\n")
    if first_message:
        print(f"> {first_message}")
        coach.send(first_message, image=image)
        print()
    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            break
        try:
            coach.send(user)
        except anthropic.RateLimitError:
            print("Rate limited. Wait a moment and try again.")
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            print("Network error. Check your connection.")
        print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="coach", description="Claude-powered Japanese study coach")
    parser.add_argument("text", nargs="*", help="text to explain, or 'quiz' / 'stats' / 'ui'")
    parser.add_argument("--image", "-i", help="path to a screenshot to explain")
    parser.add_argument("--once", action="store_true", help="answer once and exit instead of staying in chat")
    parser.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args(argv)

    text = " ".join(args.text).strip()

    if text == "stats":
        _print_stats()
        return
    if text == "ui":
        _run_ui()

    client = _require_credentials()
    from .agent import Coach

    from .config import Settings

    settings = Settings.load()
    coach = Coach(client=client, model=settings.model, effort=args.effort or settings.effort)

    if text == "quiz":
        text = "Quiz me on my due flashcards, one at a time."
    elif args.image and not text:
        text = "Explain the Japanese in this screenshot."

    if args.once:
        if not text:
            parser.error("--once needs text or --image")
        coach.send(text, image=args.image)
        return

    _chat(coach, first_message=text or None, image=args.image)


if __name__ == "__main__":
    main()
