"""
ICAO Doc 9303 Transliteration & Normalization Engine — Layer 3.

Implements ICAO Document 9303 Part 3, Section 6:
  "Transliteration of names for use in Machine Readable Travel Documents"

Handles:
  1. European diacritics & umlauts (German, French, Spanish, Nordic)
  2. Devanagari, Bengali, and Arabic-Indic regional numerals → ASCII digits
  3. Nationality / country string mapping to ISO-3166 alpha-3 codes
  4. Unicode script detection via codepoint ranges
  5. VIZ ↔ MRZ name equivalence matching (exact, ICAO transliterated, phonetic)

Used by:
  - field_extractor.py (Layer 1 local OCR)
  - llm_fallback.py    (Layer 2 multimodal vision)
  - orchestrator/core/service_clients.py (pipeline assembly)
"""

import re
import unicodedata
from difflib import SequenceMatcher


# ---------------------------------------------------------------------------
# 1. ICAO Doc 9303 Part 3, Sec. 6 — European diacritics and special letters
# ---------------------------------------------------------------------------

# Order matters: multi-char sequences first to avoid partial replacements.
_ICAO_DIACRITIC_MAP: list[tuple[str, str]] = [
    # --- German umlauts (ICAO 9303: Ä→AE, Ö→OE, Ü→UE, ß→SS) ---
    ("Ä", "AE"), ("ä", "AE"),
    ("Ö", "OE"), ("ö", "OE"),
    ("Ü", "UE"), ("ü", "UE"),
    ("ß", "SS"),
    # --- French/Spanish/Portuguese ---
    ("É", "E"),  ("È", "E"),  ("Ê", "E"),  ("Ë", "E"),
    ("é", "E"),  ("è", "E"),  ("ê", "E"),  ("ë", "E"),
    ("À", "A"),  ("Â", "A"),  ("à", "A"),  ("â", "A"),
    ("Á", "A"),  ("á", "A"),
    ("Î", "I"),  ("Ï", "I"),  ("î", "I"),  ("ï", "I"),
    ("Í", "I"),  ("Ì", "I"),  ("í", "I"),  ("ì", "I"),
    ("Ô", "O"),  ("ô", "O"),  ("Ó", "O"),  ("Ò", "O"),
    ("ó", "O"),  ("ò", "O"),  ("õ", "O"),  ("Õ", "O"),
    ("Ú", "U"),  ("Ù", "U"),  ("ú", "U"),  ("ù", "U"),  ("û", "U"),  ("Û", "U"),
    ("Ý", "Y"),  ("ý", "Y"),
    ("Ç", "C"),  ("ç", "C"),
    ("Ñ", "N"),  ("ñ", "N"),
    # --- Nordic / Scandinavian ---
    ("Å", "AA"), ("å", "AA"),
    ("Æ", "AE"), ("æ", "AE"),
    ("Ø", "OE"), ("ø", "OE"),
    # --- Icelandic ---
    ("Þ", "TH"), ("þ", "TH"),
    ("Ð", "D"),  ("ð", "D"),
    # --- Central/Eastern European ---
    ("Š", "S"),  ("š", "S"),
    ("Ž", "Z"),  ("ž", "Z"),
    ("Č", "C"),  ("č", "C"),
    ("Ř", "R"),  ("ř", "R"),
    ("Ů", "U"),  ("ů", "U"),
    ("Ě", "E"),  ("ě", "E"),
    ("Ď", "D"),  ("ď", "D"),
    ("Ť", "T"),  ("ť", "T"),
    ("Ľ", "L"),  ("ľ", "L"),
    ("Ĺ", "L"),  ("ĺ", "L"),
    ("Ń", "N"),  ("ń", "N"),
    ("Ź", "Z"),  ("ź", "Z"),
    ("Ś", "S"),  ("ś", "S"),
    ("Ć", "C"),  ("ć", "C"),
    ("Ą", "A"),  ("ą", "A"),
    ("Ę", "E"),  ("ę", "E"),
    ("Ó", "O"),  ("ó", "O"),
    # --- Turkish ---
    ("Ğ", "G"),  ("ğ", "G"),
    ("İ", "I"),  ("ı", "I"),
    # --- Romanian ---
    ("Ș", "S"),  ("ș", "S"),
    ("Ț", "T"),  ("ț", "T"),
]


# ---------------------------------------------------------------------------
# 2. Regional numeral → ASCII digit mapping tables
# ---------------------------------------------------------------------------

_DEVANAGARI_DIGITS: dict[str, str] = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

_BENGALI_DIGITS: dict[str, str] = {
    "০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
    "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9",
}

_ARABIC_INDIC_DIGITS: dict[str, str] = {
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

_THAI_DIGITS: dict[str, str] = {
    "๐": "0", "๑": "1", "๒": "2", "๓": "3", "๔": "4",
    "๕": "5", "๖": "6", "๗": "7", "๘": "8", "๙": "9",
}

_ALL_REGIONAL_DIGITS: dict[str, str] = {
    **_DEVANAGARI_DIGITS,
    **_BENGALI_DIGITS,
    **_ARABIC_INDIC_DIGITS,
    **_THAI_DIGITS,
}


# ---------------------------------------------------------------------------
# 3. Nationality / Country string → ISO-3166 alpha-3 mapping
# ---------------------------------------------------------------------------

_COUNTRY_NAME_TO_CODE: dict[str, str] = {
    # German names (from German passports)
    "DEUTSCH": "DEU",
    "DEUTSCHLAND": "DEU",
    "GERMAN": "DEU",
    "GERMANY": "DEU",

    # Indian names (from Indian passports — Hindi VIZ label)
    "BHARAT": "IND",
    "BHARATIYA": "IND",
    "INDIA": "IND",
    "INDIAN": "IND",
    "भारत": "IND",
    "भारतीय": "IND",

    # Bangladesh
    "BANGLADESH": "BGD",
    "BANGLADESHI": "BGD",
    "বাংলাদেশ": "BGD",

    # Nepal
    "NEPAL": "NPL",
    "NEPALI": "NPL",
    "NEPALESE": "NPL",
    "नेपाल": "NPL",

    # Bhutan
    "BHUTAN": "BTN",
    "BHUTANESE": "BTN",

    # Sri Lanka
    "SRI LANKA": "LKA",
    "SRI LANKAN": "LKA",
    "SRILANKA": "LKA",

    # Myanmar / Burma
    "MYANMAR": "MMR",
    "BURMESE": "MMR",
    "BURMA": "MMR",

    # France
    "FRANCE": "FRA",
    "FRANÇAIS": "FRA",
    "FRANCAIS": "FRA",
    "FRENCH": "FRA",

    # United Arab Emirates
    "UAE": "ARE",
    "UNITED ARAB EMIRATES": "ARE",
    "EMIRATI": "ARE",

    # Saudi Arabia
    "SAUDI ARABIA": "SAU",
    "SAUDI": "SAU",

    # Pakistan
    "PAKISTAN": "PAK",
    "PAKISTANI": "PAK",

    # China
    "CHINA": "CHN",
    "CHINESE": "CHN",

    # Russia
    "RUSSIA": "RUS",
    "RUSSIAN": "RUS",

    # United Kingdom
    "UNITED KINGDOM": "GBR",
    "UK": "GBR",
    "BRITISH": "GBR",

    # United States
    "UNITED STATES": "USA",
    "USA": "USA",
    "AMERICAN": "USA",

    # Japan
    "JAPAN": "JPN",
    "JAPANESE": "JPN",
}


# ---------------------------------------------------------------------------
# 4. Unicode script detection via codepoint ranges
# ---------------------------------------------------------------------------

def detect_script(text: str) -> str:
    """
    Detect the dominant non-Latin script in a string via Unicode codepoints.

    Returns one of:
      'devanagari', 'bengali', 'arabic', 'cyrillic', 'thai',
      'burmese', 'sinhala', 'chinese', 'japanese', 'latin', 'unknown'
    """
    counters: dict[str, int] = {
        "devanagari": 0,
        "bengali": 0,
        "arabic": 0,
        "cyrillic": 0,
        "thai": 0,
        "burmese": 0,
        "sinhala": 0,
        "chinese": 0,
        "japanese": 0,
        "latin": 0,
    }

    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:     # Devanagari (Hindi, Nepali, Marathi, Sanskrit)
            counters["devanagari"] += 1
        elif 0x0980 <= cp <= 0x09FF:   # Bengali
            counters["bengali"] += 1
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:  # Arabic + Arabic Supplement
            counters["arabic"] += 1
        elif 0x0400 <= cp <= 0x04FF:   # Cyrillic (Russian, Ukrainian, etc.)
            counters["cyrillic"] += 1
        elif 0x0E00 <= cp <= 0x0E7F:   # Thai
            counters["thai"] += 1
        elif 0x1000 <= cp <= 0x109F:   # Myanmar / Burmese
            counters["burmese"] += 1
        elif 0x0D80 <= cp <= 0x0DFF:   # Sinhala
            counters["sinhala"] += 1
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:  # CJK
            counters["chinese"] += 1
        elif 0x3040 <= cp <= 0x30FF:   # Hiragana + Katakana
            counters["japanese"] += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):  # Basic Latin A-Z a-z
            counters["latin"] += 1

    # Return the script with the most characters (excluding latin if a non-latin wins)
    non_latin = {k: v for k, v in counters.items() if k != "latin"}
    best_non_latin = max(non_latin, key=lambda k: non_latin[k])
    if non_latin[best_non_latin] >= 1:
        return best_non_latin
    if counters["latin"] > 0:
        return "latin"
    return "unknown"


def detect_languages_in_text(text: str) -> list[str]:
    """
    Return ISO 639-1 language code hints based on detected scripts and keywords.
    Returns multiple codes when mixed-language text is detected.
    """
    text_upper = text.upper()
    langs: list[str] = []

    script = detect_script(text)
    script_to_lang: dict[str, list[str]] = {
        "devanagari": ["hi", "ne"],
        "bengali": ["bn"],
        "arabic": ["ar"],
        "cyrillic": ["ru"],
        "thai": ["th"],
        "burmese": ["my"],
        "sinhala": ["si"],
        "chinese": ["zh"],
        "japanese": ["ja"],
    }
    if script in script_to_lang:
        langs.extend(script_to_lang[script])

    # Check for Latin-script specific language indicators
    german_indicators = [
        "BUNDESREPUBLIK", "DEUTSCHLAND", "REISEPASS", "STAATSANGEHÖRIGKEIT",
        "STAATSANGEHORIGKEIT", "GEBURTSDATUM", "GEBURTSORT", "VORNAMEN", "NACHNAME", "PASS-NR"
    ]
    if any(k in text_upper for k in german_indicators):
        if "de" not in langs:
            langs.append("de")

    french_indicators = [
        "RÉPUBLIQUE", "REPUBLIQUE", "FRANÇAISE", "FRANCAISE", "PASSEPORT", "PRÉNOMS", "PRENOMS"
    ]
    if any(k in text_upper for k in french_indicators):
        if "fr" not in langs:
            langs.append("fr")

    spanish_indicators = [
        "ESPAÑA", "ESPANA", "PASAPORTE", "APELLIDOS", "NACIONALIDAD"
    ]
    if any(k in text_upper for k in spanish_indicators):
        if "es" not in langs:
            langs.append("es")

    if not langs:
        langs = ["en"]
    elif "en" not in langs:
        langs.append("en")

    return langs


# ---------------------------------------------------------------------------
# 5. Indic character transliteration dictionary (Devanagari & Bengali)
# ---------------------------------------------------------------------------

_INDIC_CHAR_MAP: dict[str, str] = {
    # Devanagari vowels & matras
    "अ": "A", "आ": "A", "इ": "I", "ई": "I", "उ": "U", "ऊ": "U", "ऋ": "RI",
    "ए": "E", "ऐ": "AI", "ओ": "O", "औ": "AU", "अं": "AM", "अः": "AH",
    "ा": "A", "ि": "I", "ी": "I", "ु": "U", "ू": "U", "ृ": "RI",
    "े": "E", "ै": "AI", "ो": "O", "ौ": "AU", "ं": "N", "ँ": "N", "्": "",
    # Devanagari consonants
    "क": "K", "ख": "KH", "ग": "G", "घ": "GH", "ङ": "NG",
    "च": "CH", "छ": "CHH", "ज": "J", "झ": "JH", "ञ": "NY",
    "ट": "T", "ठ": "TH", "ड": "D", "ढ": "DH", "ण": "N",
    "त": "T", "थ": "TH", "द": "D", "ध": "DH", "न": "N",
    "प": "P", "फ": "PH", "ब": "B", "भ": "BH", "म": "M",
    "य": "Y", "र": "R", "ल": "L", "व": "V",
    "श": "SH", "ष": "SH", "स": "S", "ह": "H",
    # Bengali vowels & matras
    "অ": "O", "আ": "A", "ই": "I", "ঈ": "I", "উ": "U", "ঊ": "U", "ঋ": "RI",
    "এ": "E", "ঐ": "OI", "ও": "O", "ঔ": "OU",
    "া": "A", "ি": "I", "ী": "I", "ু": "U", "ূ": "U", "ৃ": "RI",
    "ে": "E", "ৈ": "OI", "ো": "O", "ৌ": "OU", "ং": "NG", "ঃ": "H", "্": "",
    # Bengali consonants
    "ক": "K", "খ": "KH", "গ": "G", "ঘ": "GH", "ঙ": "NG",
    "চ": "CH", "ছ": "CHH", "জ": "J", "ঝ": "JH", "ঞ": "N",
    "ট": "T", "ঠ": "TH", "ড": "D", "ঢ": "DH", "ণ": "N",
    "ত": "T", "থ": "TH", "দ": "D", "ध": "DH", "ন": "N",
    "প": "P", "ফ": "PH", "ব": "B", "ভ": "BH", "ম": "M",
    "য": "Y", "র": "R", "ল": "L", "শ": "SH", "ষ": "SH", "স": "S", "হ": "H",
    "ড়": "R", "ঢ়": "RH", "য়": "Y", "ৎ": "T",
}


# ---------------------------------------------------------------------------
# 6. Core transliteration functions
# ---------------------------------------------------------------------------

def normalize_regional_numerals(text: str) -> str:
    """Convert Devanagari, Bengali, Arabic-Indic, and Thai digits to ASCII 0-9."""
    result = text
    for native_digit, ascii_digit in _ALL_REGIONAL_DIGITS.items():
        result = result.replace(native_digit, ascii_digit)
    return result


def normalize_diacritics_icao(text: str) -> str:
    """
    Apply ICAO Doc 9303 Part 3, Section 6 diacritic transliteration rules.
    Converts European diacritics and special letters to ASCII equivalents.

    Examples:
      JÜRGEN MÜLLER → JUERGEN MUELLER
      SCHRÖDER      → SCHROEDER
      GROß          → GROSS
      RENÉE         → RENEE
      JOSÉ          → JOSE
    """
    result = text.upper()
    for src, dst in _ICAO_DIACRITIC_MAP:
        result = result.replace(src.upper(), dst.upper())
    # Unicode normalize: decompose any remaining combined chars and strip diacritic marks
    result = unicodedata.normalize("NFKD", result)
    result = "".join(c for c in result if unicodedata.category(c) != "Mn")
    return result


def normalize_country_code(text: str) -> str:
    """
    Map country name strings (in any language) to ICAO/ISO-3166 alpha-3 codes.
    Returns the original text (uppercased) if no mapping is found.

    Examples:
      DEUTSCH    → DEU
      BHARAT     → IND
      BANGLADESH → BGD
      IND        → IND   (pass-through for already-coded values)
    """
    text_up = text.strip().upper()
    if text_up in _COUNTRY_NAME_TO_CODE:
        return _COUNTRY_NAME_TO_CODE[text_up]
    # Check partial prefix matches for compound names
    for key, code in _COUNTRY_NAME_TO_CODE.items():
        if text_up.startswith(key) or key.startswith(text_up):
            if len(min(text_up, key)) >= 3:
                return code
    return text_up


def normalize_icao_transliteration(text: str) -> str:
    """
    Full ICAO Doc 9303 transliteration pipeline:
      1. Convert regional numerals (Devanagari/Bengali/Arabic-Indic) → ASCII
      2. Transliterate non-Latin Indic scripts (Devanagari, Bengali) → Latin ASCII
      3. Apply ICAO diacritic map (Ä→AE, Ö→OE, Ü→UE, ß→SS, É→E, Ç→C, etc.)
      4. Strip any remaining combining diacritical marks via Unicode NFC/NFD
      5. Uppercase and strip non-ASCII characters
      6. Remove MRZ filler characters `<`

    Args:
        text: Input string, which may contain native-script characters.

    Returns:
        ICAO-normalized uppercase ASCII string for MRZ cross-comparison.
    """
    if not text:
        return ""

    # Step 1: Replace MRZ filler characters `<` with space
    text = text.replace("<", " ")

    # Step 2: Regional numerals
    result = normalize_regional_numerals(text)

    # Step 3: Transliterate non-Latin Indic scripts (Devanagari, Bengali)
    indic_converted = []
    for ch in result:
        if ch in _INDIC_CHAR_MAP:
            indic_converted.append(_INDIC_CHAR_MAP[ch])
        else:
            indic_converted.append(ch)
    result = "".join(indic_converted)

    # Step 4: ICAO diacritic map
    result_upper = result.upper()
    for src, dst in _ICAO_DIACRITIC_MAP:
        result_upper = result_upper.replace(src.upper(), dst.upper())

    # Step 5: Unicode normalize + strip combining marks
    result_nfkd = unicodedata.normalize("NFKD", result_upper)
    result_ascii = "".join(
        c for c in result_nfkd
        if unicodedata.category(c) != "Mn"
    )

    # Step 6: Keep only A-Z, 0-9, space, hyphen (standard Latin/MRZ charset)
    result_clean = re.sub(r"[^A-Z0-9 \-]", "", result_ascii)
    result_clean = re.sub(r"\s+", " ", result_clean)

    return result_clean.strip()


# ---------------------------------------------------------------------------
# 6. VIZ ↔ MRZ Name Equivalence Matching
# ---------------------------------------------------------------------------

def _clean_for_compare(s: str) -> str:
    """Strip spaces, hyphens, and punctuation; uppercase."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _levenshtein_ratio(a: str, b: str) -> float:
    """SequenceMatcher ratio as a fast approximate Levenshtein similarity (0.0–1.0)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def are_names_equivalent(
    viz_name: str,
    mrz_name: str,
    threshold: float = 0.85,
) -> tuple[bool, str]:
    """
    Determine if a VIZ name (potentially in any language or with diacritics)
    is equivalent to the standard English MRZ name.

    Checks in order:
      1. Exact match after normalization
      2. ICAO transliteration match (Ä→AE, etc.)
      3. Phonetic/Levenshtein similarity >= threshold
      4. Substring containment (one name is a subset of the other)

    Args:
        viz_name:  Name from the Visual Inspection Zone (may contain diacritics/scripts)
        mrz_name:  Authoritative name from the Machine Readable Zone (ICAO ASCII)
        threshold: Minimum Levenshtein similarity ratio for phonetic matching.

    Returns:
        (is_equivalent: bool, reason: str)
    """
    if not viz_name or not mrz_name:
        return (False, "MISSING_VALUE")

    # Step 1: Direct normalized comparison
    v_norm = _clean_for_compare(normalize_icao_transliteration(viz_name))
    m_norm = _clean_for_compare(normalize_icao_transliteration(mrz_name))

    if v_norm == m_norm:
        return (True, "EXACT_MATCH")

    # Step 2: ICAO transliteration match (handles Ä→AE, ß→SS, Ö→OE)
    v_transliterated = _clean_for_compare(normalize_diacritics_icao(viz_name))
    if v_transliterated == m_norm or v_norm == _clean_for_compare(normalize_diacritics_icao(mrz_name)):
        return (True, "ICAO_TRANSLITERATION_MATCH")

    # Step 3: Token set matching (handles inverted name components e.g. "HANS MUELLER" vs "MUELLER<<HANS")
    v_tokens_list = re.findall(r"[A-Z0-9]+", normalize_icao_transliteration(viz_name))
    m_tokens_list = re.findall(r"[A-Z0-9]+", normalize_icao_transliteration(mrz_name))
    v_tokens = set(v_tokens_list)
    m_tokens = set(m_tokens_list)
    if v_tokens and m_tokens:
        if v_tokens == m_tokens:
            return (True, "ICAO_TRANSLITERATION_MATCH")
        if len(v_tokens) >= 2 and len(m_tokens) >= 2:
            if v_tokens.issubset(m_tokens) or m_tokens.issubset(v_tokens):
                return (True, "SUBSET_TOKEN_MATCH")
        # Pairwise fuzzy token matching (handles minor phonetic/transliteration variances like SHRMA vs SHARMA)
        if len(v_tokens_list) == len(m_tokens_list) and len(v_tokens_list) >= 2:
            matched_indices = set()
            all_tokens_matched = True
            for vt in v_tokens_list:
                found_match = False
                for j, mt in enumerate(m_tokens_list):
                    if j in matched_indices:
                        continue
                    if vt == mt or _levenshtein_ratio(vt, mt) >= 0.75:
                        matched_indices.add(j)
                        found_match = True
                        break
                if not found_match:
                    all_tokens_matched = False
                    break
            if all_tokens_matched:
                return (True, "ICAO_TRANSLITERATION_MATCH")

    # Step 4: Levenshtein / phonetic similarity
    similarity = _levenshtein_ratio(v_norm, m_norm)
    if similarity >= threshold:
        return (True, f"PHONETIC_MATCH (similarity={similarity:.2f})")

    # Step 5: Substring containment (handles middle name differences)
    if v_norm and m_norm:
        if v_norm in m_norm or m_norm in v_norm:
            return (True, "SUBSTRING_MATCH")

    return (False, f"MISMATCH (similarity={similarity:.2f})")


def are_dates_equivalent(viz_date: str, mrz_date: str) -> bool:
    """
    Compare dates that may be in different formats:
      VIZ: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, or DD.MM.YYYY (German style)
      MRZ: YYMMDD or DD/MM/YYYY (parsed)

    Returns True if dates represent the same calendar day.
    """
    def _extract_parts(d: str) -> tuple[str, str, str] | None:
        """Return (dd, mm, yyyy) or (dd, mm, yy) tuple."""
        d = d.strip().replace("-", "/").replace(".", "/")
        parts = d.split("/")
        if len(parts) == 3:
            p0, p1, p2 = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if len(p0) == 4:
                return (p2, p1, p0)  # YYYY/MM/DD → (dd, mm, yyyy)
            return (p0, p1, p2)
        # Try YYMMDD (6 consecutive digits)
        d_clean = re.sub(r"[^0-9]", "", d)
        if len(d_clean) == 6:
            return (d_clean[4:6], d_clean[2:4], d_clean[0:2])
        return None

    v_parts = _extract_parts(viz_date)
    m_parts = _extract_parts(mrz_date)
    if not v_parts or not m_parts:
        return False

    v_dd, v_mm, v_yy = v_parts
    m_dd, m_mm, m_yy = m_parts

    # Normalize years: 2-digit → 4-digit
    def expand_year(yy: str) -> str:
        if len(yy) == 4:
            return yy
        if len(yy) == 2:
            n = int(yy)
            return str(2000 + n) if n <= 30 else str(1900 + n)
        return yy

    return (
        v_dd == m_dd and
        v_mm == m_mm and
        expand_year(v_yy) == expand_year(m_yy)
    )
