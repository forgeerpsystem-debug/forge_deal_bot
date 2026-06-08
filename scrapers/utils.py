import re
from datetime import datetime

# Checked before single-word makes — order matters (longest match first)
MULTI_WORD_MAKES = [
    ("john deere", "John Deere"),
    ("new holland", "New Holland"),
    ("ditch witch", "Ditch Witch"),
    ("wacker neuson", "Wacker Neuson"),
    ("link belt", "Link Belt"),
    ("massey ferguson", "Massey Ferguson"),
    ("american crane", "American Crane"),
    ("atlas copco", "Atlas Copco"),
    ("western star", "Western Star"),
    ("blaw knox", "Blaw-Knox"),
]

KNOWN_MAKES = {
    # Heavy construction
    "caterpillar", "cat", "komatsu", "volvo", "liebherr", "hitachi", "doosan",
    "hyundai", "kobelco", "takeuchi", "yanmar", "kubota", "case", "jcb",
    "terex", "manitou", "gradall",
    # Skid steers / compact
    "bobcat", "gehl", "mustang", "thomas",
    # Lifts
    "genie", "jlg", "skyjack", "snorkel", "upright", "haulotte",
    # Ag
    "deere", "agco", "claas", "fendt", "challenger", "hesston", "massey",
    # Trenchers / utility
    "vermeer", "toro", "ditchwitch",
    # Compaction
    "bomag", "hamm", "dynapac", "sakai", "wacker", "mikasa",
    # Paving
    "roadtec", "vogele", "wirtgen",
    # Cranes
    "grove", "manitowoc", "tadano",
    # Aerial / truck
    "altec", "elliott", "versalift",
    # Grinders / chippers
    "bandit", "morbark", "peterson",
    # Forklifts
    "toyota", "linde", "crown", "raymond", "yale", "hyster", "clark",
    "jungheinrich", "mitsubishi", "nissan", "tcm",
    # Trucks
    "mack", "peterbilt", "kenworth", "freightliner", "international",
    # Compressors
    "ingersoll", "sullair", "airman",
    # Other
    "multiquip", "husqvarna", "stihl", "vermeer",
}


def parse_title(raw_title: str) -> tuple[int | None, str, str]:
    """Parse an equipment listing title into (year, make, model)."""
    if not raw_title:
        return None, "Unknown", "Unknown"

    raw_title = " ".join(raw_title.strip().split())
    parts = raw_title.split()
    current_year = datetime.now().year

    year = None
    idx = 0
    if parts and parts[0].isdigit() and 1950 <= int(parts[0]) <= current_year + 1:
        year = int(parts[0])
        idx = 1

    remaining = parts[idx:]
    if not remaining:
        return year, "Unknown", "Unknown"

    lower_str = " ".join(remaining).lower()

    for lower_make, display_make in MULTI_WORD_MAKES:
        if lower_str == lower_make or lower_str.startswith(lower_make + " "):
            word_count = len(lower_make.split())
            model = " ".join(remaining[word_count:]) or "Unknown"
            return year, display_make, model

    first = remaining[0].lower().rstrip(".,")
    if first in KNOWN_MAKES:
        make = remaining[0]
        model = " ".join(remaining[1:]) or "Unknown"
        return year, make, model

    # Fallback: treat first word as make
    make = remaining[0]
    model = " ".join(remaining[1:]) or "Unknown"
    return year, make, model


def clean_price(price_str) -> int:
    if not price_str:
        return 0
    digits = re.sub(r'[^\d]', '', str(price_str))
    return int(digits) if digits else 0
