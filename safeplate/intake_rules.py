"""Hearing a typed request without a model, for hosts that cannot run Gemma.

Gemma 4 E2B is a 7.2 GB model and runs on a laptop, not on a free web host. In
rules mode this module stands in for `speech.understand_text`: same `Intent`
out, but from keyword matching over the tables the loop already trusts — the
dish table, the Symphony menu and the allergen synonyms.

It is less capable than the model and meant to be. It cannot resolve "the thing
my friend ordered" or hear audio, and when it does not recognise a dish or an
allergen it returns nothing for it rather than guessing — the loop then stops
and asks, exactly as it would if Gemma had missed the same word. A word given
as an allergy that matches nothing ("allergic to kiwi and milk") is reported as
unrecognised, so the loop stops there too instead of checking milk alone. It
also errs wide: any allergen word in the sentence is treated as something to
avoid, since checking one allergen too many costs a dish and one too few costs
far more.
"""

from __future__ import annotations

import re
import unicodedata

from . import dishes, menu_symphony
from .allergens import EU_14, GROUPS, SYNONYMS, normalise
from .speech import Intent

#: Single words a diner uses for a table dish without saying its full name.
#: `dishes.strong_match` needs every word of "falafel plate"; nobody says "plate".
DISH_ALIASES: dict[str, str] = {
    "padthai": "pad thai",
    "tomyum": "tom yum",
    "falafel": "falafel plate",
    "falafels": "falafel plate",
    "caesar": "caesar salad",
    "margherita": "margherita pizza",
    "pizza": "margherita pizza",
    "mariniere": "moules marinieres",
    "marinieres": "moules marinieres",
}

#: French allergen words, mapped to the English the rest of the loop reads.
#: Keys are accent-free because the text is flattened before matching.
FRENCH_TERMS: dict[str, str] = {
    "poisson": "fish", "cabillaud": "fish",
    "crevette": "crustaceans", "crustace": "crustaceans", "moules": "molluscs",
    "mollusque": "molluscs", "sulfite": "sulphites",
    "lait": "milk", "beurre": "milk", "creme": "milk", "fromage": "milk",
    "laitier": "dairy", "laitiers": "dairy", "produits laitiers": "dairy",
    "oeuf": "eggs", "jaune d oeuf": "eggs",
    "ble": "gluten", "farine": "gluten", "semoule": "gluten",
    "arachide": "peanuts", "cacahuete": "peanuts",
    "amande": "nuts", "noisette": "nuts", "noix": "nuts",
    "fruits a coque": "tree nuts", "fruit a coque": "tree nuts",
    "fruits de mer": "shellfish",
    "celeri": "celery", "moutarde": "mustard", "soja": "soybeans",
}

#: Foods that carry an advisory rather than an EU-14 allergen, in any language,
#: mapped to the English the loop reads. Pine nuts are not "nuts" in Annex II.
ADVISORY_WORDS: dict[str, str] = {
    "pine nut": "pine nut", "pine nuts": "pine nuts", "pinoli": "pine nuts",
    "pignon": "pine nuts", "pignons": "pine nuts",
    "pignon de pin": "pine nuts", "pignons de pin": "pine nuts",
}

#: Conditions stated instead of a food. "I'm coeliac" names no ingredient, and
#: missing it would leave the diner checked against nothing.
CONDITION_TERMS: dict[str, str] = {
    "coeliac": "gluten", "celiac": "gluten", "coeliaque": "gluten",
}

#: Words that turn a question into a request to change the dish.
MODIFICATION_WORDS = frozenset({"without", "sans", "no", "remove", "omit", "hold"})
MODIFICATION_PHRASES: tuple[tuple[str, ...], ...] = (("leave", "out"), ("take", "out"))

#: Function words that only a French sentence contains. One is enough.
FRENCH_MARKERS = frozenset({
    "je", "j", "suis", "allergique", "allergiques", "sans", "avec", "vous", "pouvez",
    "puis", "est", "les", "des", "du", "une", "pas", "mon", "ma", "au", "aux", "le",
    "dans", "bonjour", "merci", "plait",
})

#: Endings that make a plural, matched in both directions: "crustacean" finds
#: the EU-14 "crustaceans", and "crevettes" finds "crevette".
PLURAL_SUFFIXES = ("s", "es")

#: Words that describe the dish rather than name an allergen, when they sit next
#: to its name: "pasta carbonara" orders the carbonara, it does not avoid gluten.
DISH_DESCRIPTORS = frozenset({"pasta", "pates", "spaghetti"})

#: Words after which a diner lists what they cannot eat.
ALLERGY_CUES = frozenset({
    "allergic", "allergique", "allergiques", "allergy", "allergies", "allergie",
    "intolerant", "intolerante", "intolerance",
})
ALLERGY_CUE_PAIRS = frozenset({("t", "eat"), ("cannot", "eat"), ("cant", "eat"),
                               ("not", "eat")})

#: Words before which a diner names the food: "a kiwi allergy".
NAMED_BEFORE_CUES = frozenset({"allergy", "allergies", "allergie", "intolerance"})

#: Words that join the items of a list of allergies.
LIST_JOINERS = frozenset({"and", "et", "or", "ou", "nor", "ni", "also", "aussi", "plus"})

#: Words that carry no food inside a list of allergies.
LIST_FILLERS = frozenset({
    "to", "a", "an", "the", "of", "any", "some", "all", "my", "no", "severe", "serious",
    "bad", "mild", "slight", "strong", "food", "foods", "raw", "cooked", "products",
    "au", "aux", "la", "le", "les", "l", "des", "du", "de", "d", "un", "une", "mon", "ma",
    "mes", "produits", "grave", "eat",
})

#: Words that end a list of allergies: the sentence has moved on to the order.
LIST_ENDERS = frozenset({
    "can", "could", "may", "please", "so", "but", "is", "are", "i", "what", "which",
    "do", "does", "would", "will", "want", "like", "have", "has", "in", "with", "without",
    "mais", "est", "puis", "pouvez", "je", "sans", "dans", "avec", "donc", "voudrais",
})


def _flatten(text: str) -> list[str]:
    """Lowercase words with accents stripped and punctuation turned into spaces."""
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("œ", "oe"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", plain).split()


def _segments(text: str) -> list[list[str]]:
    """The flattened words of each stretch of text between punctuation marks."""
    return [words for part in re.split(r"[,.;:!?]+", text) if (words := _flatten(part))]


def _vocabulary() -> dict[tuple[str, ...], str]:
    """Every allergen phrase, flattened, mapped to the English term to report."""
    vocabulary: dict[tuple[str, ...], str] = {}
    for term in (*EU_14, *SYNONYMS, *GROUPS):
        words = tuple(_flatten(term))
        # An accented key is French ("sésame", "crème"); report its English allergen.
        vocabulary[words] = term if " ".join(words) == term else normalise(term)
    for table in (FRENCH_TERMS, ADVISORY_WORDS, CONDITION_TERMS):
        for term, english in table.items():
            vocabulary[tuple(_flatten(term))] = english
    return vocabulary


#: Longest phrase first, so "fish sauce" is claimed before "fish" can be, and
#: "pine nuts" before "pine nut" reads it as a plural.
VOCABULARY: tuple[tuple[tuple[str, ...], str], ...] = tuple(
    sorted(_vocabulary().items(), key=lambda item: (-len(item[0]), -len(" ".join(item[0]))))
)


def _same_word(word: str, target: str) -> bool:
    """True when two words differ at most by a plural ending, either way round."""
    if word == target:
        return True
    return any(word == target + suffix or target == word + suffix
               for suffix in PLURAL_SUFFIXES)


def _matches_at(words: list[str], start: int, phrase: tuple[str, ...]) -> bool:
    """True when `phrase` occurs at `start`, allowing a plural on its last word."""
    end = start + len(phrase)
    if end > len(words) or words[start:end - 1] != list(phrase[:-1]):
        return False
    return _same_word(words[end - 1], phrase[-1])


def _is_allergen_word(word: str) -> bool:
    """True when this single word names an allergen on its own."""
    return any(len(phrase) == 1 and _same_word(word, phrase[0]) for phrase, _ in VOCABULARY)


def _mask_phrase(words: list[str], masked: list[bool], phrase: list[str]) -> bool:
    """Mark every occurrence of a contiguous phrase; True when there was one."""
    if not phrase:
        return False
    found = False
    for start in range(len(words) - len(phrase) + 1):
        if words[start:start + len(phrase)] == phrase:
            masked[start:start + len(phrase)] = [True] * len(phrase)
            found = True
    return found


def _mask_words(words: list[str], masked: list[bool], names: set[str]) -> None:
    """Mark every occurrence of these single words, except a word that is an allergen.

    A scattered word is only evidence of the dish, not of where it was named, so
    an allergen word is left for `_avoid`: "moules" said elsewhere in the
    sentence is still a mollusc allergy, and the dish's own ingredients then
    produce the conflict. Erring that way refuses; the other way clears.
    """
    for index, word in enumerate(words):
        if word in names and not _is_allergen_word(word):
            masked[index] = True


def _table_dish(words: list[str], masked: list[bool]) -> str | None:
    """The dish-table key named in the text, masking only the words that named it."""
    dish = dishes.strong_match(" ".join(words))
    key = next((name for name, item in dishes.DISHES.items() if item is dish), None)
    alias = None
    if key is None:
        alias = next((word for word in words if word in DISH_ALIASES), None)
        key = DISH_ALIASES.get(alias) if alias else None
    if key is None:
        return None

    phrases = [_flatten(key), _flatten(dishes.DISHES[key].name), [alias] if alias else []]
    named = [_mask_phrase(words, masked, phrase) for phrase in phrases]
    if not any(named):
        _mask_words(words, masked, {word for phrase in phrases for word in phrase})
    _mask_descriptors(words, masked)
    return key


def _mask_descriptors(words: list[str], masked: list[bool]) -> None:
    """Mark a descriptor word that sits directly beside the dish's own name."""
    named = [index for index, flag in enumerate(masked) if flag]
    for index in named:
        for neighbour in (index - 1, index + 1):
            if 0 <= neighbour < len(words) and words[neighbour] in DISH_DESCRIPTORS:
                masked[neighbour] = True


def _symphony_dish(words: list[str], masked: list[bool]) -> str | None:
    """The Symphony tray named in the text, by plate number or by keyword."""
    tray = next(
        (item for item in menu_symphony.SYMPHONY_MENU.values()
         if item.plate_number.lower() in words),
        None,
    ) or menu_symphony.lookup(" ".join(words))
    key = next(
        (name for name, item in menu_symphony.SYMPHONY_MENU.items() if item is tray), None
    )
    if key is None:
        return None

    _mask_phrase(words, masked, _flatten(key))
    _mask_phrase(words, masked, _flatten(tray.name))
    keywords = {word for term in menu_symphony.DISH_KEYWORDS[key] for word in _flatten(term)}
    _mask_words(words, masked, keywords)
    return key


def _mentions(words: list[str], masked: list[bool]) -> list[tuple[int, int, str]]:
    """Every allergen phrase in the unmasked words, as (start, end, English term)."""
    found: list[tuple[int, int, str]] = []
    claimed = list(masked)
    for phrase, english in VOCABULARY:
        for start in range(len(words)):
            span = range(start, start + len(phrase))
            if any(claimed[index] for index in span if index < len(words)):
                continue
            if _matches_at(words, start, phrase):
                found.append((start, start + len(phrase), english))
                for index in span:
                    claimed[index] = True
    return sorted(found)


def allergen_mentions(words: list[str]) -> list[tuple[int, int, str]]:
    """Every allergen phrase in already-lowercased words, as (start, end, English term).

    Args:
        words: Lowercase, accent-free words, in order.

    Returns:
        One entry per phrase found, ordered by where it starts. Where phrases
        overlap, the longest wins: "peanut oil" is one mention, not two.
    """
    return _mentions(words, [False] * len(words))


def _avoid(words: list[str], masked: list[bool]) -> list[str]:
    """Every allergen term in the unmasked words, in the order the diner said them."""
    ordered: list[str] = []
    for _, _, term in _mentions(words, masked):
        if term not in ordered:
            ordered.append(term)
    return ordered


def _cue_ends(words: list[str]) -> list[int]:
    """The index just after each allergy cue, where a list of allergies would start."""
    ends = [index + 1 for index, word in enumerate(words) if word in ALLERGY_CUES]
    ends += [index + 2 for index, pair in enumerate(zip(words, words[1:], strict=False))
             if pair in ALLERGY_CUE_PAIRS]
    return sorted(ends)


def _listed_items(words: list[str], start: int, masked: list[bool]) -> list[list[int]]:
    """The word indices of each item in the allergy list that starts at `start`."""
    items: list[list[int]] = [[]]
    for index in range(start, len(words)):
        word = words[index]
        if masked[index] or word in LIST_ENDERS or word in ALLERGY_CUES:
            break
        if word in LIST_JOINERS:
            items.append([])
        elif word not in LIST_FILLERS:
            items[-1].append(index)
    return [item for item in items if item]


def _named_before(words: list[str], masked: list[bool]) -> list[list[int]]:
    """The word naming each "X allergy", skipping adjectives such as "severe"."""
    items: list[list[int]] = []
    for index, word in enumerate(words):
        if word not in NAMED_BEFORE_CUES:
            continue
        before = index - 1
        while before >= 0 and words[before] in LIST_FILLERS:
            before -= 1
        if before >= 0 and not masked[before] and words[before] not in LIST_ENDERS:
            items.append([before])
    return items


def _unrecognised(segments: list[list[str]], masked: list[bool]) -> list[str]:
    """Items given as allergies in which no allergen word was recognised."""
    unknown: list[str] = []
    offset = 0
    for words in segments:
        local = masked[offset:offset + len(words)]
        covered = {index for start, end, _ in _mentions(words, local)
                   for index in range(start, end)}
        listed = [item for end in _cue_ends(words) for item in _listed_items(words, end, local)]
        for item in listed + _named_before(words, local):
            if not covered & set(item):
                unknown.append(" ".join(words[index] for index in item))
        offset += len(words)
    return list(dict.fromkeys(unknown))


def _request_type(words: list[str]) -> str:
    """`modification` when the diner asked for something taken out, else `question`."""
    if MODIFICATION_WORDS & set(words):
        return "modification"
    pairs = set(zip(words, words[1:], strict=False))
    return "modification" if pairs & set(MODIFICATION_PHRASES) else "question"


def _language(words: list[str]) -> str:
    """French when any French-only function word appears, English otherwise."""
    return "fr" if FRENCH_MARKERS & set(words) else "en"


def understand_text(utterance: str) -> Intent:
    """Extract the diner's request from typed text, with no model involved.

    Args:
        utterance: What the diner typed.

    Returns:
        The same `Intent` Gemma would produce. `dish` is None and `avoid` empty
        whenever nothing was recognised, so the loop asks rather than guesses;
        `unrecognised` names anything given as an allergy that matched nothing.
    """
    segments = _segments(utterance)
    words = [word for segment in segments for word in segment]
    masked = [False] * len(words)
    dish = _table_dish(words, masked) or _symphony_dish(words, masked)
    return Intent(
        utterance=utterance.strip(),
        language=_language(words),
        dish=dish,
        avoid=_avoid(words, masked),
        request_type=_request_type(words),
        unrecognised=_unrecognised(segments, masked),
    )
