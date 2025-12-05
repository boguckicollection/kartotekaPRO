"""Profanity filter module."""

import re

# List of forbidden word stems (covers variations)
FORBIDDEN_STEMS = [
    # Polish
    "kurw", "chuj", "pierdol", "jeb", "kutas", "cipa", "fiut", "szmat", "suka",
    "pedal", "ciota", "debil", "idiot",
    # English
    "fuck", "shit", "bitch", "whore", "dick", "pussy", "cunt", "nigger", "faggot",
    "asshole", "bastard"
]

def contains_profanity(text: str) -> bool:
    """
    Check if text contains forbidden words, handling leetspeak and mixing.
    """
    if not text:
        return False
        
    normalized = text.lower()
    
    # Simple leetspeak replacements
    replacements = {
        "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", 
        "@": "a", "$": "s", "!": "i", "+": "t"
    }
    
    # Create two versions: one with replacements, one without (to avoid false positives if original was safe)
    # Actually, we should check both or apply replacements intelligently.
    # Let's apply replacements to a copy.
    leetspeak_text = normalized
    for k, v in replacements.items():
        leetspeak_text = leetspeak_text.replace(k, v)
        
    # Remove non-alphanumeric chars (e.g. "k.u.r.w.a" -> "kurwa")
    clean_text = re.sub(r'[^a-z]', '', leetspeak_text)
    
    # Also check the version without leetspeak replacements but with stripped chars
    clean_orig = re.sub(r'[^a-z]', '', normalized)

    for stem in FORBIDDEN_STEMS:
        if stem in clean_text or stem in clean_orig:
            return True
            
    return False
