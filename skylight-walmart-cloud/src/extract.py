from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import BinaryIO

from openai import OpenAI

from .models import GroceryList


@dataclass
class UploadedImage:
    data: bytes
    mime_type: str


def _data_url(image: UploadedImage) -> str:
    encoded = base64.b64encode(image.data).decode("ascii")
    mime = image.mime_type or "image/png"
    return f"data:{mime};base64,{encoded}"


def extract_grocery_list(
    *,
    api_key: str,
    model: str,
    images: list[UploadedImage],
    pasted_text: str = "",
) -> GroceryList:
    if not api_key.strip():
        raise ValueError("An OpenAI API key is required for screenshot extraction.")
    if not images and not pasted_text.strip():
        raise ValueError("Provide at least one screenshot or some pasted text.")

    client = OpenAI(api_key=api_key.strip())
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Extract only the grocery or household shopping-list entries visible in the provided "
                "Skylight screenshots and/or pasted list. Do not invent recipe ingredients. Combine obvious "
                "duplicate lines. Preserve meaningful qualifiers such as brand, flavor, fresh/frozen, low sodium, "
                "or package size in notes. Convert written quantities to numbers. When no quantity is shown, use 1. "
                "Use a practical unit such as item, lb, oz, can, bunch, bottle, bag, box, pack, jar, gallon, quart, "
                "pint, head, cup, tbsp, or tsp. Keep names concise and suitable for a Walmart search."
            ),
        }
    ]

    if pasted_text.strip():
        content.append({"type": "input_text", "text": f"Pasted list:\n{pasted_text.strip()}"})

    for image in images:
        content.append({
            "type": "input_image",
            "image_url": _data_url(image),
            "detail": "high",
        })

    response = client.responses.parse(
        model=model.strip() or "gpt-5.6",
        input=[{"role": "user", "content": content}],
        text_format=GroceryList,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The model did not return a structured grocery list.")
    return parsed
