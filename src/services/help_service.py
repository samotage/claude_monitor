"""Help documentation service for Claude Headspace.

This module handles:
- Loading help documentation from docs/application/
- Parsing YAML frontmatter for metadata
- Searching help content by keywords

Ported from lib/help.py to the new src/ architecture.
"""

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Path to help documentation directory (relative to project root)
HELP_DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "application"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: Markdown content with optional frontmatter

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\n", content[3:])
    if not end_match:
        return {}, content

    frontmatter_str = content[3 : end_match.start() + 3]
    remaining = content[end_match.end() + 3 :]

    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        frontmatter = {}

    return frontmatter, remaining


def extract_headings(content: str) -> list[str]:
    """Extract all headings from markdown content.

    Args:
        content: Markdown content

    Returns:
        List of heading texts
    """
    headings = []
    for line in content.split("\n"):
        if line.startswith("#"):
            # Remove # prefix and clean up
            heading = re.sub(r"^#+\s*", "", line).strip()
            if heading:
                headings.append(heading)
    return headings


def load_help_index() -> list[dict]:
    """Load index of all help documentation pages.

    Returns:
        List of dicts with slug, title, order, keywords for each page
    """
    if not HELP_DOCS_DIR.exists():
        logger.warning(f"Help docs directory not found: {HELP_DOCS_DIR}")
        return []

    pages = []
    for md_file in HELP_DOCS_DIR.glob("*.md"):
        slug = md_file.stem
        content = md_file.read_text()
        frontmatter, _ = parse_frontmatter(content)

        pages.append(
            {
                "slug": slug,
                "title": frontmatter.get("title", slug.replace("-", " ").title()),
                "order": frontmatter.get("order", 99),
                "keywords": frontmatter.get("keywords", "").split(", ")
                if frontmatter.get("keywords")
                else [],
            }
        )

    # Sort by order, then by title
    pages.sort(key=lambda p: (p["order"], p["title"]))
    return pages


def load_help_page(slug: str) -> dict | None:
    """Load a specific help page by slug.

    Args:
        slug: Page slug (filename without .md extension)

    Returns:
        Dict with slug, title, content, keywords, headings
        None if page not found
    """
    page_path = HELP_DOCS_DIR / f"{slug}.md"
    if not page_path.exists():
        return None

    content = page_path.read_text()
    frontmatter, markdown_content = parse_frontmatter(content)
    headings = extract_headings(markdown_content)

    return {
        "slug": slug,
        "title": frontmatter.get("title", slug.replace("-", " ").title()),
        "content": markdown_content,
        "keywords": frontmatter.get("keywords", "").split(", ")
        if frontmatter.get("keywords")
        else [],
        "headings": headings,
        "order": frontmatter.get("order", 99),
    }


def search_help(query: str) -> list[dict]:
    """Search help documentation by query.

    Searches in:
    - Page titles
    - Keywords in frontmatter
    - Headings within content
    - Content text

    Args:
        query: Search query string

    Returns:
        List of matching pages with scores, sorted by relevance
    """
    if not query or not query.strip():
        return []

    if not HELP_DOCS_DIR.exists():
        return []

    query = query.lower().strip()
    query_words = query.split()
    results = []

    for md_file in HELP_DOCS_DIR.glob("*.md"):
        slug = md_file.stem
        content = md_file.read_text()
        frontmatter, markdown_content = parse_frontmatter(content)

        title = frontmatter.get("title", slug.replace("-", " ").title())
        keywords = frontmatter.get("keywords", "")
        headings = extract_headings(markdown_content)

        # Calculate relevance score
        score = 0
        matched_in = []

        # Title match (highest weight)
        title_lower = title.lower()
        if query in title_lower:
            score += 100
            matched_in.append("title")
        elif any(word in title_lower for word in query_words):
            score += 50
            matched_in.append("title")

        # Keywords match (high weight)
        keywords_lower = keywords.lower()
        if query in keywords_lower:
            score += 80
            matched_in.append("keywords")
        elif any(word in keywords_lower for word in query_words):
            score += 40
            matched_in.append("keywords")

        # Headings match (medium weight)
        headings_text = " ".join(headings).lower()
        if query in headings_text:
            score += 60
            matched_in.append("headings")
        elif any(word in headings_text for word in query_words):
            score += 30
            matched_in.append("headings")

        # Content match (lower weight)
        content_lower = markdown_content.lower()
        if query in content_lower:
            score += 40
            matched_in.append("content")
            # Count occurrences for bonus
            occurrences = content_lower.count(query)
            score += min(occurrences * 5, 20)  # Cap bonus at 20
        elif any(word in content_lower for word in query_words):
            score += 20
            matched_in.append("content")

        if score > 0:
            # Extract snippet around first match
            snippet = _extract_snippet(markdown_content, query, query_words)

            results.append(
                {
                    "slug": slug,
                    "title": title,
                    "score": score,
                    "matched_in": matched_in,
                    "snippet": snippet,
                    "order": frontmatter.get("order", 99),
                }
            )

    # Sort by score descending, then by order
    results.sort(key=lambda r: (-r["score"], r["order"]))
    return results


def _extract_snippet(
    content: str, query: str, query_words: list[str], max_length: int = 150
) -> str:
    """Extract a relevant snippet from content around the search match.

    Args:
        content: Full content text
        query: Full search query
        query_words: Individual search words
        max_length: Maximum snippet length

    Returns:
        Snippet with match highlighted (using ** for bold)
    """
    content_lower = content.lower()

    # Find best match position
    pos = content_lower.find(query)
    if pos == -1:
        # Try individual words
        for word in query_words:
            pos = content_lower.find(word)
            if pos != -1:
                break

    if pos == -1:
        # No direct match, return start of content
        clean_content = re.sub(r"```[\s\S]*?```", "", content)  # Remove code blocks
        clean_content = re.sub(r"`[^`]+`", "", clean_content)  # Remove inline code
        clean_content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_content)  # Clean links
        clean_content = re.sub(r"[#*_]", "", clean_content)  # Remove markdown
        clean_content = " ".join(clean_content.split())  # Normalize whitespace
        return (
            clean_content[:max_length] + "..." if len(clean_content) > max_length else clean_content
        )

    # Get context around match
    start = max(0, pos - 50)
    end = min(len(content), pos + max_length - 50)

    snippet = content[start:end]

    # Clean up the snippet
    snippet = re.sub(r"```[\s\S]*?```", " ", snippet)  # Remove code blocks
    snippet = re.sub(r"`([^`]+)`", r"\1", snippet)  # Clean inline code
    snippet = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", snippet)  # Clean links
    snippet = re.sub(r"[#*_]", "", snippet)  # Remove markdown formatting
    snippet = " ".join(snippet.split())  # Normalize whitespace

    # Add ellipsis if needed
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet


def get_help_page_content(slug: str) -> str | None:
    """Get raw markdown content for a help page.

    Args:
        slug: Page slug

    Returns:
        Markdown content without frontmatter, or None if not found
    """
    page = load_help_page(slug)
    if page is None:
        return None
    return page["content"]
