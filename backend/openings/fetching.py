"""Bounded public-page reading; offers remain incomplete when extraction fails."""

import asyncio
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx


class PostingHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text, self.title = [], []
        self.skip = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in {"p", "div", "li", "br", "section", "h1", "h2", "h3"}:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.skip:
            self.text.append(data + " ")


async def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        return False
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
        return all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, ValueError):
        return False


async def read_posting(url):
    try:
        async with httpx.AsyncClient(
            timeout=10, headers={"User-Agent": "Openings/1.0 job import"}
        ) as client:
            for _ in range(4):
                if not await public_url(url):
                    return {}
                async with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get(
                        "content-type", ""
                    ) and "text/plain" not in response.headers.get("content-type", ""):
                        return {}
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 2_000_000:
                            return {}
                        chunks.append(chunk)
                    text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                    parser = PostingHTML()
                    parser.feed(text)
                    posting = "\n".join(
                        " ".join(line.split())
                        for line in "".join(parser.text).splitlines()
                        if line.strip()
                    )
                    return (
                        {"title": "".join(parser.title).strip()[:400], "posting": posting[:200_000]}
                        if len(posting) > 80
                        else {}
                    )
    except (httpx.HTTPError, OSError, ValueError):
        pass
    return {}
