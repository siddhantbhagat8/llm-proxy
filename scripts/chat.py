"""Send one chat request through the proxy as a given user.

Run from the repo root (proxy must be running):
  uv run python -m scripts.chat <api-key> "your prompt" [--model llama3.2:1b] [--stream]
"""

import argparse

import openai


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a chat request through the proxy."
    )
    parser.add_argument("api_key", help="API key of the user to send as (sk-proxy-...)")
    parser.add_argument("prompt")
    parser.add_argument("--model", default="llama3.2:1b")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()

    client = openai.OpenAI(
        base_url="http://localhost:8000", api_key=args.api_key, max_retries=0
    )
    if args.stream:
        stream = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": args.prompt}],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print()
    else:
        completion = client.chat.completions.create(
            model=args.model, messages=[{"role": "user", "content": args.prompt}]
        )
        print(completion.choices[0].message.content)
        print(f"\nusage: {completion.usage}")


if __name__ == "__main__":
    main()
