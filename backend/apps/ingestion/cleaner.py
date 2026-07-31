"""SEC filing HTML cleaning and text extraction.

Converts raw SEC filing HTML into clean plain text suitable
for chunking and embedding. Handles various filing formats.
"""

import re
from typing import Optional

from bs4 import BeautifulSoup

# Sections we care about for 10-K filings
SECTION_PATTERNS = {
    "Item 1": r"Item\s+1[.\s:]+Business",
    "Item 1A": r"Item\s+1A[.\s:]+Risk\s+Factors",
    "Item 7": r"Item\s+7[.\s:]+Management.{0,20}Discussion",
    "Item 7A": r"Item\s+7A[.\s:]+Quantitative",
    "Item 8": r"Item\s+8[.\s:]+Financial\s+Statements",
}


def clean_filing_html(html_content: str) -> str:
    """Convert SEC filing HTML to clean plain text.

    Removes scripts, styles, and normalizes whitespace.

    Args:
        html_content: Raw HTML string from SEC EDGAR

    Returns:
        Cleaned plain text
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "meta", "link", "noscript"]):
        tag.decompose()

    # Remove hidden elements
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()

    # Get text with newline separators
    text = soup.get_text(separator="\n")

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 newlines
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)  # Leading whitespace

    return text.strip()


def extract_section(text: str, section_name: str) -> Optional[str]:
    """Extract a specific section from filing text.

    Args:
        text: Full filing text
        section_name: Section key (e.g., "Item 7")

    Returns:
        Section text or None if not found
    """
    if section_name not in SECTION_PATTERNS:
        return None

    pattern = SECTION_PATTERNS[section_name]

    # Find section start
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None

    start = match.start()

    # Find next section (end of this section)
    end = len(text)
    for other_name, other_pattern in SECTION_PATTERNS.items():
        if other_name == section_name:
            continue
        other_match = re.search(other_pattern, text[start + 100:], re.IGNORECASE)
        if other_match:
            potential_end = start + 100 + other_match.start()
            if potential_end < end:
                end = potential_end

    section_text = text[start:end].strip()

    # Basic validation: section should have reasonable length
    if len(section_text) < 100:
        return None

    return section_text


def extract_all_sections(text: str) -> dict[str, str]:
    """Extract all known sections from filing text.

    Args:
        text: Full filing text

    Returns:
        Dict mapping section names to their content
    """
    sections = {}
    for section_name in SECTION_PATTERNS:
        content = extract_section(text, section_name)
        if content:
            sections[section_name] = content
    return sections


def detect_filing_type(text: str) -> str:
    """Detect if filing is 10-K or 10-Q based on content.

    Args:
        text: Filing text

    Returns:
        '10-K' or '10-Q'
    """
    text_lower = text[:5000].lower()

    if "annual report" in text_lower or "form 10-k" in text_lower:
        return "10-K"
    if "quarterly report" in text_lower or "form 10-q" in text_lower:
        return "10-Q"

    # Default to 10-K
    return "10-K"
