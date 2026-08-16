"""Send one chat request through the proxy as a given user.

Run from the repo root (proxy must be running):
  uv run -m scripts.chat <api-key> "your prompt" [--model llama3.2:1b] [--stream] [--image photo.jpg]
"""

import argparse
import base64
import mimetypes
from pathlib import Path

import openai
from openai.types.chat import ChatCompletionContentPartParam, ChatCompletionMessageParam


def build_content(
    prompt: str, image_path: str | None
) -> str | list[ChatCompletionContentPartParam]:
    if image_path is None:
        return prompt
    # Ollama accepts vision input only as base64 data URIs (jpeg/png/webp).
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        raise SystemExit(
            f"error: unsupported image type for {image_path} (use jpeg/png/webp)"
        )
    image_base64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    return [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a chat request through the proxy."
    )
    parser.add_argument("api_key", help="API key of the user to send as (sk-proxy-...)")
    parser.add_argument("prompt")
    parser.add_argument("--model", default="llama3.2:1b")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument(
        "--image", help="path to a jpeg/png/webp file (use with --model moondream)"
    )
    args = parser.parse_args()

    client = openai.OpenAI(
        base_url="http://localhost:8000", api_key=args.api_key, max_retries=0
    )
    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": build_content(args.prompt, args.image)}
    ]
    try:
        if args.stream:
            stream = client.chat.completions.create(
                model=args.model, messages=messages, stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    print(chunk.choices[0].delta.content, end="", flush=True)
            print()
        else:
            completion = client.chat.completions.create(
                model=args.model, messages=messages
            )
            print(completion.choices[0].message.content)
            print(f"\nusage: {completion.usage}")
    except openai.APIStatusError as error:
        raise SystemExit(f"error {error.status_code}: {error_message(error)}") from None
    except openai.APIConnectionError:
        raise SystemExit(
            "error: could not reach the proxy at http://localhost:8000 — is it running?"
        ) from None


def error_message(error: openai.APIStatusError) -> str:
    # The SDK unwraps the {"error": {...}} envelope, so body is the inner object.
    if isinstance(error.body, dict) and "message" in error.body:
        return str(error.body["message"])
    return str(error.body)


if __name__ == "__main__":
    main()
