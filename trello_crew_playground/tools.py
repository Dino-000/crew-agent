"""Tools for CrewAI agents to interact with web pages and external resources."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests
from crewai.tools import tool


class _WebPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = "No title"
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._in_title = False
        self._skip_text = False
        self._current_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_text = True
            return

        if tag == "title":
            self._in_title = True
            return

        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._current_link = {"text": "", "href": href}

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip_text = False
            return

        if tag == "title":
            self._in_title = False
            return

        if tag == "a" and self._current_link is not None:
            self.links.append(self._current_link)
            self._current_link = None

    def handle_data(self, data: str) -> None:
        text = unescape(data).strip()
        if not text or self._skip_text:
            return

        if self._in_title:
            self.title = text

        self.text_parts.append(text)

        if self._current_link is not None:
            current_text = self._current_link.get("text", "")
            self._current_link["text"] = f"{current_text} {text}".strip()


@tool
def fetch_webpage(url: str) -> dict[str, Any]:
    """
    Fetch the content of a webpage.
    
    Args:
        url: The URL to fetch
        
    Returns:
        A dictionary with 'status', 'title', 'text', and 'html' keys
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        parser = _WebPageParser()
        parser.feed(response.text)
        title = parser.title
        text = "\n".join(part for part in parser.text_parts if part)
        
        return {
            "status": "success",
            "url": url,
            "title": title,
            "text": text,
            "html": response.text,
        }
    except Exception as e:
        return {
            "status": "error",
            "url": url,
            "error": str(e),
        }


@tool
def extract_links(url: str) -> dict[str, Any]:
    """
    Extract all links from a webpage.
    
    Args:
        url: The URL to fetch and parse
        
    Returns:
        A dictionary with 'status' and 'links' list
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        parser = _WebPageParser()
        parser.feed(response.text)
        links = [
            {"text": item.get("text", "").strip(), "href": urljoin(url, item["href"]) }
            for item in parser.links
        ]
        
        return {
            "status": "success",
            "url": url,
            "links": links,
            "total": len(links),
        }
    except Exception as e:
        return {
            "status": "error",
            "url": url,
            "error": str(e),
        }


def count_keyword_occurrences(text: str, keyword: str) -> int:
    """
    Count occurrences of a keyword in text (case-insensitive).
    
    Args:
        text: The text to search in
        keyword: The keyword to count
        
    Returns:
        The number of occurrences
    """
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return len(pattern.findall(text))


@tool
def extract_repositories(text: str) -> list[str]:
    """
    Extract repository mentions from text (GitHub-style repo references).
    
    Args:
        text: The text to search in
        
    Returns:
        A list of repository identifiers found
    """
    # Match patterns like owner/repo or github.com/owner/repo
    patterns = [
        r"github\.com/([a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_\.]+)",  # github.com URLs
        r"(?:^|\s)([a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_\.]+)(?:\s|$)",  # owner/repo format
    ]
    
    repos = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        repos.update(matches)
    
    return sorted(list(repos))
