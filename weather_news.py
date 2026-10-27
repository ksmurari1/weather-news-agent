"""AutoGen Weather News Agent core logic.

Searches DuckDuckGo News for city-specific weather news, then asks an AutoGen
AssistantAgent to summarize the retrieved results in exactly three short lines.
"""
from __future__ import annotations

import os
import re
from typing import Any

from ddgs import DDGS
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient


def search_weather_news(city: str) -> str:
    """Search recent news about today's weather for the supplied city.

    AutoGen reads this function's name, type hint, and docstring to understand
    when to call the tool. DuckDuckGo search itself does not require an API key.
    """
    city = city.strip()
    if not city:
        return "No city was provided. Ask the user to enter a city."

    try:
        results = DDGS().news(
            query=f"{city} weather today",
            max_results=5,
        )
        if not results:
            return f"No weather-related news results were found for {city}."
        return str(results)
    except Exception as exc:
        # Return a useful tool result instead of crashing the whole agent run.
        return f"Search failed for {city}: {type(exc).__name__}: {exc}"


def enforce_three_lines(text: str) -> str:
    """Normalize model output to exactly three non-empty display lines.

    This is a presentation safeguard; it does not create new weather facts.
    """
    text = (text or "").strip()
    lines = [line.strip().lstrip("-•* ").strip() for line in text.splitlines() if line.strip()]

    if len(lines) == 3:
        return "\n".join(lines)
    if len(lines) > 3:
        return "\n".join(lines[:2] + [" ".join(lines[2:])])

    # If the model returned a paragraph, try splitting it into sentences.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", " ".join(lines)) if s.strip()]
    if len(sentences) >= 3:
        return "\n".join([sentences[0], sentences[1], " ".join(sentences[2:])])

    if len(sentences) == 2:
        return "\n".join([
            sentences[0],
            sentences[1],
            "Source note: Check the search results for the latest updates.",
        ])

    if len(sentences) == 1:
        return "\n".join([
            sentences[0],
            "Additional detail: The search did not yield a separate supported point.",
            "Source note: Check the search results for the latest updates.",
        ])

    return "\n".join([
        "No reliable weather-news summary was produced.",
        "The search may have returned no usable results or encountered an error.",
        "Please try again with a city name.",
    ])


async def run_weather_news(city: str) -> tuple[list[Any], str]:
    """Run the AutoGen agent and return its event trace plus a three-line answer."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to your .env file or environment."
        )

    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=api_key,
    )

    agent = AssistantAgent(
        name="weather_news",
        model_client=model_client,
        tools=[search_weather_news],
        system_message=(
            "You are a careful weather-news assistant. Use the search_weather_news "
            "tool to search for recent weather-related news for the requested city. "
            "Base every claim only on the returned search results. Do not invent "
            "current temperatures, forecasts, or conditions. If sources are unclear "
            "or results are missing, say so. Respond in exactly three short, non-empty "
            "lines. Prefer useful facts and mention source/headline context when available."
        ),
        reflect_on_tool_use=True,
    )

    events: list[Any] = []
    final_text = ""
    try:
        task = (
            f"Find and summarize today's weather-related news for {city}. "
            "Use the search tool and return exactly three short lines."
        )
        async for event in agent.run_stream(task=task):
            events.append(event)
            # TextMessage is intentionally detected by class name so this module
            # remains easy to inspect without depending on event internals.
            if event.__class__.__name__ == "TextMessage":
                content = getattr(event, "content", "")
                if isinstance(content, str) and content.strip():
                    final_text = content
            # Some AutoGen versions expose the final task result with messages.
            if event.__class__.__name__ == "TaskResult":
                for message in getattr(event, "messages", []):
                    if message.__class__.__name__ == "TextMessage":
                        content = getattr(message, "content", "")
                        if isinstance(content, str) and content.strip():
                            final_text = content
    finally:
        # Always release the model client, including when a run fails.
        await model_client.close()

    return events, enforce_three_lines(final_text)
