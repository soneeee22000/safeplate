"""Unit tests for the Symphony menu, read off the real packaging.

Three Symphony.fr ready meals carry the same closing line: "Élaboré dans un
atelier qui utilise : gluten, céleri, moutarde, arachides, poisson, œufs, soja,
lait, fruits à coque, sésame." Ten of the EU 14, on every dish, in the
manufacturer's own words. Nothing that comes out of that atelier can honestly be
called free of any of the ten, so the only truthful answer to a severe allergy is
that it cannot be guaranteed.

The case these tests exist for is the "Gnocchis pesto vegan". Vegan is a claim
about animal products, not about allergens: the dish contains gnocchi, which are
gluten, and pignons de pin, which are pine nuts. The label does not bold them. A
nut-allergic diner who reads "vegan" and orders it is the person this project is
for, and this file is what stops that reading from being encoded as safe.

`safeplate/menu_symphony.py` is being written alongside these tests, so the
module is probed by capability rather than by exact symbol name: a dish that
cannot be found skips with a message naming what was looked for, and only a
wrong safety answer fails.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
from typing import Any

import pytest

from safeplate.allergens import EU_14, normalise

menu_symphony = pytest.importorskip(
    "safeplate.menu_symphony",
    reason="safeplate/menu_symphony.py does not exist yet — the Symphony menu tests "
           "have nothing to run against.",
)

#: The ten allergen classes on the Symphony atelier line, mapped from the words a
#: label actually uses (French, and the EU-14 English names) to the EU-14 name.
SHARED_FACILITY_TERMS: dict[str, tuple[str, ...]] = {
    "cereals containing gluten": ("gluten",),
    "celery": ("celeri", "celery"),
    "mustard": ("moutarde", "mustard"),
    "peanuts": ("arachide", "peanut"),
    "fish": ("poisson", "fish"),
    "eggs": ("ouf", "oeuf", "egg"),
    "soybeans": ("soja", "soy", "soybean"),
    "milk": ("lait", "milk"),
    "nuts": ("fruits a coque", "fruit a coque", "noix", "nut"),
    "sesame": ("sesame",),
}

DISH_FIXTURES: tuple[str, ...] = ("paella", "bolognaise", "gnocchi")

#: Accent folding that preserves length, so an index into the folded string is
#: still an index into the original.
_ACCENTS = str.maketrans("àâäçéèêëîïôöùûüÿœ", "aaaceeeeiioouuuyo")

_FACILITY_MARKERS: tuple[str, ...] = (
    "elabore dans un atelier", "atelier qui utilise", "may contain",
    "peut contenir", "traces de", "traces of",
)
_FACILITY_FIELD_HINTS: tuple[str, ...] = (
    "cross", "contact", "facility", "atelier", "trace", "may_contain",
    "shared", "contamination",
)
#: Fields that name an ingredient. Prose about an allergen is an explanation, not
#: a declaration, and reading it would pass a dish whose ingredient list had lost
#: the allergen altogether.
_INGREDIENT_TEXT_HINTS: tuple[str, ...] = ("name", "gloss", "ingredient", "label",
                                           "title", "text")
#: Fields that carry a claim about the dish, as opposed to prose explaining it. A
#: claim of "gluten-free" is a promise; a sentence saying no gluten-free version
#: exists is the opposite, and both contain the same words.
_CLAIM_FIELD_HINTS: tuple[str, ...] = ("claim", "free", "marketing", "label",
                                       "name", "vegan", "diet", "suitable")
_FREE_CLAIMS: tuple[str, ...] = ("sans {}", "{} free", "{}-free", "free from {}",
                                 "exempt de {}", "garanti sans {}")
_CLEARED_WORDS = frozenset({"already_clear", "clear", "cleared", "safe", "free",
                            "verified", "ok", "yes", "true", "none"})
_PROBE_NAMES: tuple[str, ...] = (
    "is_safe_for", "safe_for", "is_free_of", "free_of", "can_serve",
    "clears", "assess", "check_dish", "verdict_for", "report", "read_label",
    "label_report",
)
_WORD = re.compile(r"[a-z]+")
_MAX_DEPTH = 5
#: A dish's label text runs to sentences; a loose constant does not.
_DISH_TEXT_FLOOR = 40


def _fold(text: str) -> str:
    """Lowercase and strip accents without changing the string's length."""
    return text.lower().translate(_ACCENTS)


def _flatten(values: Iterable[object], depth: int) -> list[str]:
    """Collect the strings inside a sequence of values, one level deeper."""
    return [text for value in values for text in _strings(value, depth + 1)]


def _strings(value: object, depth: int = 0) -> list[str]:
    """Every string reachable inside a value, however the module nests it."""
    if isinstance(value, str):
        return [value]
    if depth >= _MAX_DEPTH:
        return []
    if isinstance(value, Mapping):
        return _flatten(value.values(), depth)
    if isinstance(value, (list, tuple, set, frozenset)):
        return _flatten(value, depth)
    if is_dataclass(value) and not isinstance(value, type):
        return _flatten([getattr(value, f.name) for f in fields(value)], depth)
    if hasattr(value, "__dict__"):
        return _flatten(vars(value).values(), depth)
    return []


def _fields_of(value: object) -> dict[str, Any]:
    """The named fields of a dataclass, an object, or a mapping."""
    if isinstance(value, (str, bytes)):
        return {}
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: getattr(value, f.name) for f in fields(value)}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _is_facility_field(name: str) -> bool:
    """True for a field that carries the shared-facility declaration."""
    lowered = name.lower()
    return any(hint in lowered for hint in _FACILITY_FIELD_HINTS)


def _split_label(text: str) -> tuple[str, str]:
    """Split one label string into what is in the dish and what the atelier handles."""
    folded = _fold(text)
    for marker in _FACILITY_MARKERS:
        index = folded.find(marker)
        if index >= 0:
            return text[:index], text[index:]
    return text, ""


def _recipe_text(dish: object) -> list[str]:
    """The label text describing what is in the dish, excluding the atelier line."""
    texts: list[str] = []
    for name, value in _fields_of(dish).items():
        if _is_facility_field(name):
            continue
        texts.extend(_split_label(text)[0] for text in _strings(value))
    return [text for text in texts if text.strip()]


def _facility_text(dish: object) -> list[str]:
    """The shared-facility declaration, wherever the module keeps it."""
    texts: list[str] = []
    for name, value in _fields_of(dish).items():
        found = _strings(value)
        texts.extend(found if _is_facility_field(name)
                     else [_split_label(text)[1] for text in found])
    return [text for text in texts if text.strip()]


def _has_term(folded: str, tokens: set[str], variant: str) -> bool:
    """True when the text uses this label word, singular or plural.

    Whole-word matching, because "peanuts" must not be read as a declaration of
    "nuts" and "laitue" must not be read as "lait".
    """
    if " " in variant:
        return variant in folded
    return variant in tokens or f"{variant}s" in tokens


def _eu14_terms(texts: Iterable[str]) -> set[str]:
    """Every allergen of the atelier ten that this label text names."""
    folded = " ".join(_fold(text) for text in texts)
    tokens = set(_WORD.findall(folded))
    return {allergen for allergen, variants in SHARED_FACILITY_TERMS.items()
            if any(_has_term(folded, tokens, variant) for variant in variants)}


def _component_tags(component: object) -> set[str]:
    """Allergens the module tagged explicitly on one ingredient entry."""
    raw: Any = ()
    if isinstance(component, Mapping):
        raw = component.get("allergens", ())
    elif not isinstance(component, str):
        raw = getattr(component, "allergens", ())
    if isinstance(raw, str):
        raw = (raw,)
    return {normalise(str(item)) for item in raw} & set(EU_14)


def _component_texts(component: object) -> list[str]:
    """The words naming one ingredient, without the prose that explains it."""
    named = _fields_of(component)
    if not named:
        return _strings(component)
    texts = [text for name, value in named.items()
             if any(hint in name.lower() for hint in _INGREDIENT_TEXT_HINTS)
             for text in _strings(value)]
    return texts or _strings(component)


def _component_allergens(component: object) -> set[str]:
    """Every EU-14 allergen one ingredient entry carries, tagged or named."""
    texts = _component_texts(component)
    named = {normalise(text) for text in texts} & set(EU_14)
    return _component_tags(component) | named | _eu14_terms(texts)


def _components(dish: object) -> list[Any]:
    """The dish's individual ingredient entries, however the module models them."""
    named = _fields_of(dish)
    for name, value in named.items():
        if "ingredient" in name.lower() and isinstance(value, (list, tuple)):
            return list(value)
    for name, value in named.items():
        if not _is_facility_field(name) and isinstance(value, (list, tuple)) and value:
            return list(value)
    return list(_recipe_text(dish))


def _declared(dish: object) -> set[str]:
    """Every EU-14 allergen the ingredient list itself carries, bolded or not.

    Read off the ingredients alone, never off the dish title or the explanations
    around it, so that losing an ingredient shows up here as a missing allergen.
    """
    found: set[str] = set()
    for component in _components(dish):
        found |= _component_allergens(component)
    return found


def _resolved(value: object, dish: object) -> object:
    """Call a per-dish accessor if that is what this is, otherwise take it as it is."""
    if isinstance(value, type):
        return None
    if not callable(value):
        return value
    for args in ((dish,), ()):
        try:
            return value(*args)
        except Exception:  # A guessed signature failing is information, not an error.
            continue
    return None


def _module_facility_text(dish: object) -> list[str]:
    """The declaration a module may hold once and reach per dish.

    One workshop makes all three plats, so the module is entitled to store the
    declaration once rather than copy it onto every dish.
    """
    texts: list[str] = []
    for name in dir(menu_symphony):
        if name.startswith("_") or not _is_facility_field(name):
            continue
        texts.extend(_strings(_resolved(getattr(menu_symphony, name), dish)))
    return texts


def _facility(dish: object) -> set[str]:
    """Every allergen the atelier declaration covers for this dish."""
    return _eu14_terms(_facility_text(dish) + _module_facility_text(dish))


def _claim_text(dish: object) -> list[str]:
    """The dish's label and marketing claims, as distinct from prose explaining it."""
    return [text for name, value in _fields_of(dish).items()
            if any(hint in name.lower() for hint in _CLAIM_FIELD_HINTS)
            for text in _strings(value)]


def _claims_free_of(dish: object, allergen: str) -> bool:
    """True when the dish's own claims assert it is free of the allergen."""
    folded = " ".join(_fold(text) for text in _claim_text(dish))
    for variant in SHARED_FACILITY_TERMS[allergen]:
        if any(claim.format(variant) in folded for claim in _FREE_CLAIMS):
            return True
    return False


def _dishes_in(attribute: str, value: object) -> dict[str, Any]:
    """Pull dish-shaped entries out of one module attribute."""
    if isinstance(value, Mapping):
        return {f"{attribute}[{key}]": item
                for key, item in value.items() if _is_dish(item)}
    if isinstance(value, (list, tuple)):
        return {f"{attribute}[{index}]": item
                for index, item in enumerate(value) if _is_dish(item)}
    return {attribute: value} if _is_dish(value) else {}


def _is_dish(value: object) -> bool:
    """True for something that looks like a dish rather than a loose constant."""
    field_names = _fields_of(value)
    if not field_names:
        return False
    if any("ingredient" in name.lower() for name in field_names):
        return True
    return len(" ".join(_strings(value))) > _DISH_TEXT_FLOOR


def _dish_table() -> dict[str, Any]:
    """Every dish object the module exposes, keyed by where it was found."""
    table: dict[str, Any] = {}
    for name in dir(menu_symphony):
        if name.startswith("_"):
            continue
        table.update(_dishes_in(name, getattr(menu_symphony, name)))
    return table


def _require(*alternatives: str) -> Any:
    """The dish matching any of these label words, or a skip naming what was missing."""
    table = _dish_table()
    for needle in alternatives:
        for dish in table.values():
            if needle in _fold(" ".join(_strings(dish))):
                return dish
    pytest.skip(
        f"No dish in safeplate.menu_symphony matches any of {alternatives!r}. "
        f"Dishes found: {sorted(table)}."
    )


def _cleared(result: object) -> bool | None:
    """Read a module's answer as "this dish is cleared", or None if unreadable."""
    if isinstance(result, bool):
        return result
    if isinstance(result, str):
        return result.strip().lower() in _CLEARED_WORDS
    for attribute in ("outcome", "verdict", "status"):
        value = getattr(result, attribute, None)
        if isinstance(value, str):
            return value.strip().lower() in _CLEARED_WORDS
    return None


def _first_answer(function: Any, dish: Any, allergen: str) -> bool | None:
    """Call an assessor with the argument orders a reasonable module might use."""
    for args in ((dish, [allergen]), (dish, allergen), (allergen, dish)):
        try:
            answer = _cleared(function(*args))
        except Exception:  # A guessed signature failing is information, not an error.
            continue
        if answer is not None:
            return answer
    return None


def _probe_cleared(dish: Any, allergen: str) -> bool | None:
    """Ask any assessor the module exposes whether the dish is cleared.

    Returns None when the module exposes no such function, so the caller asserts
    only that nothing ever answers True.
    """
    for name in _PROBE_NAMES:
        function = getattr(menu_symphony, name, None)
        if not callable(function):
            continue
        answer = _first_answer(function, dish, allergen)
        if answer is not None:
            return answer
    return None


@pytest.fixture(scope="module")
def paella() -> Any:
    """Paëlla poisson chorizo et poulet, 425 g, plat JU0T2hac."""
    return _require("paella", "ju0t2hac")


@pytest.fixture(scope="module")
def bolognaise() -> Any:
    """Pâtes bolognaises, 450 g, plat p45jG3yE."""
    return _require("bolognaise", "bolognese", "p45jg3ye")


@pytest.fixture(scope="module")
def gnocchi() -> Any:
    """Gnocchis pesto vegan, 425 g, plat GEBbtKWD."""
    return _require("gnocchi", "gebbtkwd")


@pytest.mark.parametrize("dish_fixture", DISH_FIXTURES)
def test_every_dish_carries_the_atelier_declaration(
        dish_fixture: str, request: pytest.FixtureRequest) -> None:
    """All three dishes come from an atelier that handles the same ten allergens."""
    dish = request.getfixturevalue(dish_fixture)
    missing = sorted(set(SHARED_FACILITY_TERMS) - _facility(dish))

    assert not missing, (
        f"{dish_fixture}: every Symphony label ends with the same atelier line covering "
        f"ten allergen classes. These are not represented on this dish: {missing}."
    )


def test_fish_diner_is_not_cleared_for_the_paella(paella: Any) -> None:
    """Cabillaud is cod, bolded on the label as the paella's declared allergen."""
    derived = _declared(paella)

    assert "fish" in derived, (
        "The paella lists cabillaud, which is cod, and the label bolds it as the "
        f"declared allergen. Allergens derived from the dish: {sorted(derived)}."
    )
    assert not _claims_free_of(paella, "fish")
    assert _probe_cleared(paella, "fish") is not True


def test_milk_diner_is_not_cleared_for_the_bolognaise(bolognaise: Any) -> None:
    """Emmental and Parmesan each put milk in the bolognaise, and both are bolded."""
    text = _fold(" ".join(_strings(bolognaise)))

    assert "emmental" in text and "parmesan" in text, (
        "The bolognaise carries milk twice — emmental and Parmesan. Dropping either "
        "from the ingredient list loses a declared allergen."
    )
    assert "milk" in _declared(bolognaise), (
        f"Allergens derived from the dish: {sorted(_declared(bolognaise))}."
    )
    assert not _claims_free_of(bolognaise, "milk")
    assert _probe_cleared(bolognaise, "milk") is not True


def test_celery_diner_is_not_cleared_for_the_bolognaise(bolognaise: Any) -> None:
    """Céleri sits in the middle of the herb list and is a declared EU-14 allergen."""
    derived = _declared(bolognaise)

    assert "celery" in derived, (
        "Céleri is bolded on the bolognaise label. Nobody expects celery in a bolognese, "
        f"which is exactly why it has to be read off the label. Derived: {sorted(derived)}."
    )
    assert not _claims_free_of(bolognaise, "celery")
    assert _probe_cleared(bolognaise, "celery") is not True


def test_vegan_gnocchi_is_not_cleared_for_a_nut_allergy(gnocchi: Any) -> None:
    """Pignons de pin are pine nuts. Vegan is a claim about animal products only."""
    text = _fold(" ".join(_strings(gnocchi)))
    derived = _declared(gnocchi)

    assert "vegan" in text, "This fixture matched a dish that is not the vegan gnocchi."
    assert "pignon" in text, (
        "The label lists pignons de pin. Losing them from the ingredient list is what "
        "puts a nut-allergic diner in front of this plate."
    )
    assert "nuts" in derived, (
        "Pignons de pin are pine nuts, a tree nut, and the label does not bold them. "
        f"Vegan does not imply nut-free. Derived: {sorted(derived)}."
    )
    assert not _claims_free_of(gnocchi, "nuts")
    assert _probe_cleared(gnocchi, "nuts") is not True
    assert _probe_cleared(gnocchi, "tree nuts") is not True


def test_vegan_gnocchi_still_contains_gluten(gnocchi: Any) -> None:
    """The same reading error applies to gluten: the gnocchi and the yeast both carry it."""
    derived = _declared(gnocchi)

    assert "cereals containing gluten" in derived, (
        "Gluten is bolded twice on this label, on the gnocchi and on the levure "
        f"diététique. Vegan does not imply gluten-free. Derived: {sorted(derived)}."
    )
    assert _probe_cleared(gnocchi, "cereals containing gluten") is not True


@pytest.mark.parametrize("allergen", sorted(SHARED_FACILITY_TERMS))
@pytest.mark.parametrize("dish_fixture", DISH_FIXTURES)
def test_no_dish_is_ever_free_of_a_shared_facility_allergen(
        dish_fixture: str, allergen: str, request: pytest.FixtureRequest) -> None:
    """No Symphony dish can be declared free of any allergen the atelier handles."""
    dish = request.getfixturevalue(dish_fixture)

    assert allergen in (_declared(dish) | _facility(dish)), (
        f"{dish_fixture}: {allergen} is handled in the atelier that makes this dish, so "
        "it has to remain visible somewhere on the record."
    )
    assert not _claims_free_of(dish, allergen), (
        f"{dish_fixture}: nothing made in this atelier may be described as free of "
        f"{allergen}. For a severe allergy the honest answer is that it cannot be "
        "guaranteed."
    )
    assert _probe_cleared(dish, allergen) is not True, (
        f"{dish_fixture}: the module cleared this dish for {allergen} despite the "
        "shared-facility declaration."
    )
