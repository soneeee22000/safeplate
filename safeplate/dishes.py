"""What a dish is made of, and what can honestly come out of it.

The insight this file encodes: *some ingredients are the dish*. You can serve a
pad thai without peanuts. You cannot serve a pad thai without fish sauce — take
it out and what arrives is not pad thai, it is wet noodles. A waiter who says
"sure, no problem" to that is either lying or about to send back a dish nobody
ordered.

So each ingredient carries a role:

  structural    - removing it destroys the dish. The honest answer is no.
  substitutable - removable, but only if the kitchen has the alternative.
  removable     - comes out cleanly, nothing else changes.

Like `allergens.py`, this is data rather than generation. Gemma works out what
the diner asked for; this table decides whether it is possible. A 5B model
guessing at culinary structure is exactly the failure this project exists to
avoid.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .allergens import MATCH_ADVISORY, conflict_kind, normalise

Role = str  # "structural" | "substitutable" | "removable"


@dataclass(frozen=True)
class Ingredient:
    name: str
    allergens: tuple[str, ...] = ()
    role: Role = "removable"
    #: Why it cannot come out. Required for structural ingredients — this is the
    #: sentence the diner actually reads, so it has to be a reason, not a refusal.
    why: str = ""
    substitute: str | None = None


@dataclass(frozen=True)
class Dish:
    name: str
    cuisine: str
    ingredients: tuple[Ingredient, ...]
    #: Shared-equipment risks the kitchen must confirm; no label ever carries these.
    cross_contact_note: str = ""


DISHES: dict[str, Dish] = {
    "pad thai": Dish(
        name="Pad thai",
        cuisine="Thai",
        cross_contact_note="wok and fryer shared across the whole Thai section",
        ingredients=(
            Ingredient("fish sauce", ("fish",), "structural",
                       "Fish sauce is the salt and the backbone of pad thai. Without it "
                       "the dish has no seasoning base — it is not a garnish that can be "
                       "left off."),
            Ingredient("dried shrimp", ("crustaceans",), "substitutable",
                       substitute="omit and increase tamarind"),
            Ingredient("tamarind paste"),
            Ingredient("rice noodles"),
            Ingredient("egg", ("eggs",), "removable"),
            Ingredient("crushed peanuts", ("peanuts",), "removable"),
            Ingredient("bean sprouts"),
            Ingredient("garlic chives"),
        ),
    ),
    "tom yum": Dish(
        name="Tom yum",
        cuisine="Thai",
        cross_contact_note="stock pot shared with seafood service",
        ingredients=(
            Ingredient("fish sauce", ("fish",), "structural",
                       "Tom yum is seasoned entirely with fish sauce and lime. Removing it "
                       "leaves an unseasoned broth."),
            Ingredient("prawns", ("crustaceans",), "substitutable",
                       substitute="chicken tom yum"),
            Ingredient("lemongrass"),
            Ingredient("galangal"),
            Ingredient("chilli paste"),
        ),
    ),
    "carbonara": Dish(
        name="Spaghetti carbonara",
        cuisine="Italian",
        cross_contact_note="pasta water shared with all wheat pasta",
        ingredients=(
            Ingredient("egg yolk", ("eggs",), "structural",
                       "The sauce is egg yolk emulsified with pasta water. There is no "
                       "carbonara sauce without it — cream is a different dish."),
            Ingredient("pecorino", ("milk",), "structural",
                       "Pecorino is the other half of the emulsion and all of the salt."),
            Ingredient("guanciale", (), "substitutable", substitute="pancetta, or omit"),
            Ingredient("spaghetti", ("cereals containing gluten",), "substitutable",
                       substitute="gluten-free pasta if in stock"),
            Ingredient("black pepper"),
        ),
    ),
    "caesar salad": Dish(
        name="Caesar salad",
        cuisine="American",
        cross_contact_note="dressing made in a bowl also used for aioli",
        ingredients=(
            Ingredient("anchovy", ("fish",), "structural",
                       "Anchovy is what makes the dressing a Caesar. Left out, it is a "
                       "garlic mayonnaise on lettuce."),
            Ingredient("egg yolk", ("eggs",), "structural",
                       "The dressing is an emulsion built on raw egg yolk."),
            Ingredient("parmesan", ("milk",), "removable"),
            Ingredient("croutons", ("cereals containing gluten",), "removable"),
            Ingredient("romaine"),
        ),
    ),
    "moules marinieres": Dish(
        name="Moules marinières",
        cuisine="French",
        cross_contact_note="shellfish handled on the same board as the fish course",
        ingredients=(
            Ingredient("mussels", ("molluscs",), "structural",
                       "The mussels are the dish."),
            Ingredient("butter", ("milk",), "substitutable", substitute="olive oil"),
            Ingredient("white wine", ("sulphites",), "substitutable",
                       substitute="stock, though the flavour changes"),
            Ingredient("shallot"),
            Ingredient("parsley"),
        ),
    ),
    "pesto pasta": Dish(
        name="Pasta al pesto",
        cuisine="Italian",
        cross_contact_note="pesto blended in a machine also used for nut pastes",
        ingredients=(
            # Not tagged "nuts": Annex II does not list pine nuts. The advisory in
            # `allergens.ADVISORY_TERMS` still holds a nut-allergic diner.
            Ingredient("pine nuts", (), "structural",
                       "Pine nuts are what make pesto a pesto — they give it the body and "
                       "the fat. Without them it is chopped basil in oil."),
            Ingredient("parmesan", ("milk",), "substitutable", substitute="omit, add salt"),
            Ingredient("pasta", ("cereals containing gluten",), "substitutable",
                       substitute="gluten-free pasta if in stock"),
            Ingredient("basil"),
            Ingredient("garlic"),
        ),
    ),
    "falafel plate": Dish(
        name="Falafel plate",
        cuisine="Levantine",
        cross_contact_note="deep fryer shared with breaded and peanut-crusted items",
        ingredients=(
            Ingredient("chickpeas"),
            Ingredient("tahini sauce", ("sesame",), "substitutable",
                       substitute="serve with harissa instead"),
            Ingredient("pita", ("cereals containing gluten",), "removable"),
            Ingredient("parsley"),
            Ingredient("cumin"),
        ),
    ),
    "margherita pizza": Dish(
        name="Margherita pizza",
        cuisine="Italian",
        cross_contact_note="one oven and one peel for every pizza on the menu",
        ingredients=(
            Ingredient("mozzarella", ("milk",), "substitutable",
                       substitute="pizza marinara, which has no cheese by design"),
            Ingredient("wheat base", ("cereals containing gluten",), "structural",
                       "The base is the pizza. A gluten-free base is a different product "
                       "and we do not stock one."),
            Ingredient("tomato"),
            Ingredient("basil"),
        ),
    ),
}


@dataclass
class Finding:
    ingredient: Ingredient
    matched_avoid: str
    #: Matched only through an advisory (pine nuts for a tree-nut allergy), not
    #: through a declarable allergen or the diner naming the ingredient.
    advisory: bool = False

    @property
    def blocking(self) -> bool:
        return self.ingredient.role == "structural" and not self.advisory


@dataclass
class Assessment:
    """What the table concluded, before any human is asked."""

    dish: Dish | None
    findings: list[Finding] = field(default_factory=list)
    unknown_dish: bool = False

    @property
    def blocking(self) -> list[Finding]:
        return [item for item in self.findings if item.blocking]

    @property
    def adjustable(self) -> list[Finding]:
        return [item for item in self.findings if not item.blocking and not item.advisory]

    @property
    def advisory(self) -> list[Finding]:
        """Findings a person must confirm, because no regulation settles them."""
        return [item for item in self.findings if item.advisory]

    @property
    def outcome(self) -> str:
        """`cannot_assess`, `cannot_modify`, `advisory`, `modifiable`, or `already_clear`."""
        if self.unknown_dish:
            return "cannot_assess"
        if self.blocking:
            return "cannot_modify"
        if self.advisory:
            return "advisory"
        if self.adjustable:
            return "modifiable"
        return "already_clear"


def lookup(dish_name: str | None) -> Dish | None:
    """Find a dish by name, tolerating the wording a diner would actually use."""
    if not dish_name:
        return None

    key = dish_name.strip().lower()
    if key in DISHES:
        return DISHES[key]

    normalised = key.replace("è", "e").replace("é", "e").replace("-", " ")
    for name, dish in DISHES.items():
        if normalised == name or normalised in name or name in normalised:
            return dish
    return None


def _name_tokens(text: str) -> set[str]:
    """Lowercase words with accents stripped and punctuation turned into spaces."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return set(re.sub(r"[^a-z0-9]+", " ", plain).split())


def strong_match(dish_name: str | None) -> Dish | None:
    """Find a dish only when every word of its table name was heard.

    Stricter than `lookup`: this decides whether the table owns a name before any
    other menu is consulted, so a fragment such as "pasta" must not claim it.
    "pâtes carbonara" still resolves, because it contains all of "carbonara".
    """
    if not dish_name:
        return None

    heard = _name_tokens(dish_name)
    if not heard:
        return None
    for name, dish in DISHES.items():
        if _name_tokens(name) <= heard:
            return dish
    return None


def assess(dish_name: str | None, avoid: list[str]) -> Assessment:
    """Decide whether the diner's request is possible, before asking anyone.

    Args:
        dish_name: The dish as Gemma heard it, or None if none was named.
        avoid: Ingredients or allergens the diner cannot eat.

    Returns:
        The findings, and an outcome the loop branches on.
    """
    dish = lookup(dish_name)
    if dish is None:
        return Assessment(dish=None, unknown_dish=True)

    findings = [
        finding for ingredient in dish.ingredients
        if (finding := _finding(ingredient, avoid)) is not None
    ]
    return Assessment(dish=dish, findings=findings)


def _finding(ingredient: Ingredient, avoid: list[str]) -> Finding | None:
    """The strongest conflict between one ingredient and the diner's terms.

    A direct match outranks an advisory one, so "nuts, pine nuts" still refuses
    a dish whose pine nuts cannot come out.
    """
    advisory: Finding | None = None
    for term in avoid:
        kind = conflict_kind(term, list(ingredient.allergens), ingredient.name)
        if kind is None:
            continue
        if kind != MATCH_ADVISORY:
            return Finding(ingredient=ingredient, matched_avoid=term)
        advisory = advisory or Finding(ingredient=ingredient, matched_avoid=term,
                                       advisory=True)
    return advisory


def allergens_present(dish: Dish) -> set[str]:
    """Every declarable allergen the dish carries, for the evidence trail."""
    return {normalise(name) for item in dish.ingredients for name in item.allergens}
