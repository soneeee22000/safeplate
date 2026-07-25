"""A real menu, transcribed from real packaging, where nothing can be removed.

`dishes.py` describes food a kitchen cooks. This file describes food a kitchen
reheats. Symphony.fr plats arrive frozen in a sealed tray and leave a microwave
on the same plate; there is no pass at which an ingredient could be left out.
So almost every ingredient here is `structural`, and that is not pessimism — it
is the difference between a chef who can omit the peanuts and a counter that
cannot take the cod out of a sealed paella.

Two properties of these labels drive everything below:

  * The workshop line — "Élaboré dans un atelier qui utilise ..." — names all
    ten allergen classes and appears on all three plats. No dish made in that
    workshop can ever be declared free of any of them. For a severe allergy the
    only honest verdict is that it cannot be guaranteed.
  * "Vegan" is a claim about animal products, not about allergens. The vegan
    gnocchi carry gluten in two places and tree nuts in the pesto, and the pine
    nuts are not bolded. A diner scanning the bold text will miss them.

The ingredient lists are transcribed verbatim in French, in label order, with an
English gloss. Nothing is inferred: an ingredient carries an allergen here only
where the label says so, or where the ingredient plainly is one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .allergens import EU_14, conflicts, expand, normalise
from .dishes import Ingredient, Role

PRODUCER = "Symphony.fr, 13B rue du Clos de Marolles, 28130 Pierres"

SHARED_FACILITY_FR = (
    "Élaboré dans un atelier qui utilise : gluten, céleri, moutarde, arachides, "
    "poisson, œufs, soja, lait, fruits à coque, sésame."
)
SHARED_FACILITY_EN = (
    "Made in a workshop that also handles: gluten, celery, mustard, peanuts, "
    "fish, eggs, soya, milk, tree nuts, sesame."
)

#: The ten classes the workshop declares, in label order.
SHARED_FACILITY_ALLERGENS: tuple[str, ...] = (
    "cereals containing gluten",
    "celery",
    "mustard",
    "peanuts",
    "fish",
    "eggs",
    "soybeans",
    "milk",
    "nuts",
    "sesame",
)

#: The four EU-14 allergens the workshop line says nothing about. Silence is not
#: absence — it only means the question has to go to a human instead.
OUTSIDE_WORKSHOP_DECLARATION: tuple[str, ...] = tuple(
    allergen for allergen in EU_14 if allergen not in SHARED_FACILITY_ALLERGENS
)

SEALED_TRAY_REASON = (
    "The plat is cooked, portioned and sealed at the factory, then reheated as it "
    "is. Individual ingredients cannot be taken out of it."
)

PINE_NUT_WHY = (
    "The pesto is made with pine nuts — pignons de pin — and pine nuts are tree "
    "nuts. They are printed in the ingredient list but not in bold, so a diner "
    "checking the bold allergen text will not see them. The dish is also sold as "
    "vegan, which describes animal products and says nothing about nuts. The nuts "
    "are blended into the sauce before the tray is sealed, so there is no version "
    "of this plat without them."
)

GLUTEN_IN_VEGAN_WHY = (
    "Vegan does not mean gluten-free. This plat declares gluten twice: in the "
    "gnocchi themselves and in the dietary yeast used for the pesto."
)

#: Allergens a "vegan" claim is routinely misread as excluding, and the sentence
#: that corrects the misreading.
VEGAN_MISREAD_WHY: dict[str, str] = {
    "nuts": PINE_NUT_WHY,
    "cereals containing gluten": GLUTEN_IN_VEGAN_WHY,
}

# The words printed on French packaging and spoken by French diners. `allergens.py`
# is the authority on the EU-14 and is not edited from here; this table only adds
# the label vocabulary that file does not already resolve.
LABEL_FRENCH_TERMS: dict[str, str] = {
    "gluten": "cereals containing gluten",
    "soja": "soybeans",
    "lait": "milk",
    "fruits à coque": "nuts",
    "fruits a coque": "nuts",
    "pignons de pin": "nuts",
    "pignon de pin": "nuts",
    "cabillaud": "fish",
}


@dataclass(frozen=True)
class LabelIngredient(Ingredient):
    """An ingredient as it is printed, not as a kitchen would handle it.

    Defaults differ from `Ingredient` on purpose: in a sealed ready-meal the
    resting state of every ingredient is structural.
    """

    #: The English rendering, for a diner who does not read French.
    gloss: str = ""
    #: True when the label sets the ingredient in bold as a declared allergen.
    declared: bool = False
    role: Role = "structural"
    why: str = SEALED_TRAY_REASON


# Parallel to `dishes.Dish` rather than a subclass of it: this ingredient tuple is
# narrowed to `LabelIngredient`, which a subclass cannot do without breaking the
# base type's contract.
@dataclass(frozen=True)
class PackagedDish:
    """One plat, as sold: a name, a weight, a plate number and a fixed recipe."""

    name: str
    cuisine: str
    ingredients: tuple[LabelIngredient, ...]
    weight_grams: int
    plate_number: str
    producer: str = PRODUCER
    #: Sold with a vegan claim. Says nothing about allergens.
    marketed_vegan: bool = False
    cross_contact_note: str = (
        "one workshop declaring all ten allergen classes, on every plat it makes"
    )


@dataclass(frozen=True)
class SharedFacility:
    """The workshop declaration, which is identical on every Symphony plat."""

    declaration_fr: str
    declaration_en: str
    allergens: tuple[str, ...]


SHARED_FACILITY = SharedFacility(
    declaration_fr=SHARED_FACILITY_FR,
    declaration_en=SHARED_FACILITY_EN,
    allergens=SHARED_FACILITY_ALLERGENS,
)


@dataclass(frozen=True)
class LabelConflict:
    """An ingredient on the label that the diner said they cannot eat."""

    ingredient: LabelIngredient
    matched_avoid: str

    @property
    def declared(self) -> bool:
        """True when the label bolded it; False when it is listed but not flagged."""
        return self.ingredient.declared


@dataclass(frozen=True)
class LabelReport:
    """What one label says about one diner. No outcome here means safe."""

    dish: PackagedDish
    label_conflicts: tuple[LabelConflict, ...]
    shared_facility: SharedFacility
    #: The diner's terms the workshop declaration already covers.
    shared_facility_matches: tuple[str, ...]
    vegan_misreads: tuple[str, ...]

    @property
    def declared_conflicts(self) -> tuple[LabelConflict, ...]:
        """Conflicts the label sets in bold as declared allergens."""
        return tuple(item for item in self.label_conflicts if item.declared)

    @property
    def undeclared_conflicts(self) -> tuple[LabelConflict, ...]:
        """Conflicts present in the ingredient list but never bolded."""
        return tuple(item for item in self.label_conflicts if not item.declared)

    @property
    def outcome(self) -> str:
        """`label_conflict`, `cannot_guarantee`, or `outside_the_declaration`.

        `outside_the_declaration` is the weakest of the three and still is not a
        clearance: it means the workshop line is silent on this allergen, so a
        human has to answer instead of a label.
        """
        if self.label_conflicts:
            return "label_conflict"
        if self.shared_facility_matches:
            return "cannot_guarantee"
        return "outside_the_declaration"


SYMPHONY_MENU: dict[str, PackagedDish] = {
    "paella poisson chorizo et poulet": PackagedDish(
        name="Paëlla poisson chorizo et poulet",
        cuisine="Spanish",
        weight_grams=425,
        plate_number="JU0T2hac",
        ingredients=(
            LabelIngredient("riz", gloss="rice"),
            LabelIngredient("blanc de poulet (origine Union Européenne)",
                            gloss="chicken breast (EU origin)"),
            LabelIngredient("cabillaud", ("fish",), gloss="cod", declared=True,
                            why="The cod is cooked into the rice and sealed in the tray "
                                "at the factory. Nobody downstream can take it back out — "
                                "this plat is reheated, not assembled to order."),
            LabelIngredient("chorizo", gloss="chorizo sausage"),
            LabelIngredient("huile d'olive", gloss="olive oil"),
            LabelIngredient("poivrons", gloss="peppers"),
            LabelIngredient("oignons", gloss="onions"),
            LabelIngredient("petits pois", gloss="garden peas"),
            LabelIngredient("sel", gloss="salt"),
            LabelIngredient("piment doux fumé", gloss="sweet smoked paprika"),
            LabelIngredient("safran", gloss="saffron"),
            LabelIngredient("poivre", gloss="pepper"),
        ),
    ),
    "pates bolognaises": PackagedDish(
        name="Pâtes bolognaises (spécialité du chef Symphony)",
        cuisine="Italian",
        weight_grams=450,
        plate_number="p45jG3yE",
        ingredients=(
            LabelIngredient("fusilli", ("cereals containing gluten",),
                            gloss="fusilli pasta", declared=True,
                            why="The fusilli are the dish, and they arrive already sauced "
                                "in a sealed tray. Symphony does not make a gluten-free "
                                "version of this plat."),
            LabelIngredient("bœuf haché (origine France)",
                            gloss="minced beef (French origin)"),
            LabelIngredient("carottes", gloss="carrots"),
            LabelIngredient("purée de tomates", gloss="tomato purée"),
            LabelIngredient("huile d'olive", gloss="olive oil"),
            LabelIngredient("concentré de tomate", gloss="tomato paste"),
            LabelIngredient("emmental", ("milk",), gloss="Emmental cheese", declared=True,
                            why="The Emmental is melted through the sauce before the tray "
                                "is sealed. It is not a topping that can be left off."),
            LabelIngredient("purée d'oignons", gloss="onion purée"),
            LabelIngredient("purée de carottes", gloss="carrot purée"),
            LabelIngredient("Parmesan", ("milk",), gloss="Parmesan cheese", declared=True,
                            why="The Parmesan is mixed into the sauce at the factory, not "
                                "grated over the plate at service. It leaves only if the "
                                "whole dish does."),
            LabelIngredient("glucose", gloss="glucose"),
            LabelIngredient("échalotes", gloss="shallots"),
            LabelIngredient("ail frais", gloss="fresh garlic"),
            LabelIngredient("sel", gloss="salt"),
            LabelIngredient("basilic", gloss="basil"),
            LabelIngredient("paprika", gloss="paprika"),
            LabelIngredient("céleri", ("celery",), gloss="celery", declared=True,
                            why="Celery is part of the seasoning base of the bolognaise. "
                                "The label declares it because it must; the sauce is "
                                "already cooked, so it cannot be cooked without it."),
            LabelIngredient("origan", gloss="oregano"),
            LabelIngredient("poivre", gloss="pepper"),
            LabelIngredient("romarin", gloss="rosemary"),
            LabelIngredient("piment en poudre", gloss="chilli powder"),
            LabelIngredient("laurier", gloss="bay leaf"),
        ),
    ),
    "gnocchis pesto vegan": PackagedDish(
        name="Gnocchis pesto vegan",
        cuisine="Italian",
        weight_grams=425,
        plate_number="GEBbtKWD",
        marketed_vegan=True,
        ingredients=(
            LabelIngredient("gnocchis", ("cereals containing gluten",), gloss="gnocchi",
                            declared=True,
                            why="The gnocchi are the dish and they contain wheat. The "
                                "vegan claim on the sleeve is about animal products; it "
                                "does not touch the gluten."),
            LabelIngredient("épinards fermes", gloss="firm spinach"),
            LabelIngredient("huile d'olive", gloss="olive oil"),
            LabelIngredient("basilic", gloss="basil"),
            LabelIngredient("pignons de pin", ("nuts",), gloss="pine nuts",
                            declared=False, why=PINE_NUT_WHY),
            LabelIngredient("gran prosociano violife",
                            gloss="Violife Gran Prosociano, a vegan hard-cheese "
                                  "alternative"),
            LabelIngredient("levure diététique", ("cereals containing gluten",),
                            gloss="dietary yeast", declared=True,
                            why="The label declares gluten in the dietary yeast. It is "
                                "blended into the pesto before sealing, so it is the "
                                "second unremovable source of gluten in this plat."),
            LabelIngredient("jus de citron", gloss="lemon juice"),
            LabelIngredient("ail en poudre", gloss="garlic powder"),
            LabelIngredient("sel", gloss="salt"),
            LabelIngredient("poivre", gloss="pepper"),
        ),
    ),
}


def shared_facility(dish: PackagedDish) -> SharedFacility:
    """Return the workshop declaration that applies to a plat.

    Every Symphony plat carries the same line, so the answer never varies. The
    argument is kept because callers must reach this per dish rather than assume
    a global truth: another producer's menu would not share one workshop.
    """
    del dish  # Deliberately unused; see the docstring.
    return SHARED_FACILITY


def facility_matches(avoid: list[str]) -> tuple[str, ...]:
    """The diner's terms that the workshop declaration already covers.

    A match means the allergen is handled in the room where the food is made, so
    no label can rule it out.
    """
    return tuple(
        term for term in avoid
        if any(a in SHARED_FACILITY_ALLERGENS for a in _all_allergens(term))
    )


def to_allergen(term: str) -> str:
    """Map a French label term or a spoken word to its EU-14 allergen.

    Falls through to `allergens.normalise`, which handles diner speech and the
    general label vocabulary. Returns the term unchanged when it is not an
    allergen at all.
    """
    key = term.strip().lower()
    if key in LABEL_FRENCH_TERMS:
        return LABEL_FRENCH_TERMS[key]
    for phrase, allergen in LABEL_FRENCH_TERMS.items():
        if phrase in key:
            return allergen
    return normalise(key)


def _all_allergens(term: str) -> tuple[str, ...]:
    """Every EU-14 allergen a term could mean, French label words included."""
    key = term.strip().lower()
    if key in LABEL_FRENCH_TERMS:
        return (LABEL_FRENCH_TERMS[key],)
    for phrase, allergen in LABEL_FRENCH_TERMS.items():
        if phrase in key:
            return (allergen,)
    return expand(key)


def matches(term: str, ingredient: LabelIngredient) -> bool:
    """True when an ingredient is something the diner said to avoid."""
    if any(allergen in ingredient.allergens for allergen in _all_allergens(term)):
        return True
    return conflicts(term, list(ingredient.allergens), ingredient.name)


def vegan_misreads(dish: PackagedDish, avoid: list[str]) -> tuple[str, ...]:
    """Explain the allergens a vegan claim is read as excluding but does not.

    Args:
        dish: The plat under assessment.
        avoid: What the diner cannot eat, in any language.

    Returns:
        A sentence per misread allergen the dish actually contains, in the words
        a diner would read. Empty when the plat makes no vegan claim.
    """
    if not dish.marketed_vegan:
        return ()

    targets = {allergen for term in avoid for allergen in _all_allergens(term)}
    present = {name for item in dish.ingredients for name in item.allergens}
    return tuple(
        why for allergen, why in VEGAN_MISREAD_WHY.items()
        if allergen in targets and allergen in present
    )


def report(dish: PackagedDish, avoid: list[str]) -> LabelReport:
    """Read one Symphony label against one diner's allergens.

    Args:
        dish: The plat, as transcribed from its packaging.
        avoid: Allergens or ingredients the diner cannot eat, in any language.

    Returns:
        The conflicts printed on the label, the workshop risk that is present on
        every plat, and any vegan misread this dish invites.
    """
    found: list[LabelConflict] = []
    for ingredient in dish.ingredients:
        matched = next((term for term in avoid if matches(term, ingredient)), None)
        if matched is not None:
            found.append(LabelConflict(ingredient=ingredient, matched_avoid=matched))

    return LabelReport(
        dish=dish,
        label_conflicts=tuple(found),
        shared_facility=shared_facility(dish),
        shared_facility_matches=facility_matches(avoid),
        vegan_misreads=vegan_misreads(dish, avoid),
    )


#: Words a diner or the model might use for each plat. Substring matching is not
#: enough: Gemma returns things like "gnocchi's pesto" and "bolognaise pasta",
#: neither of which contains, nor is contained by, the name on the sleeve.
DISH_KEYWORDS: dict[str, frozenset[str]] = {
    "paella poisson chorizo et poulet": frozenset(
        {"paella", "paëlla", "chorizo", "poulet"}
    ),
    "pates bolognaises": frozenset(
        {"bolognaise", "bolognaises", "bolognese", "bolognesa", "fusilli", "pates",
         "pâtes", "bolo"}
    ),
    "gnocchis pesto vegan": frozenset(
        {"gnocchi", "gnocchis", "gnocchy", "pesto", "vegan"}
    ),
}

_STRIP = str.maketrans(
    {"ë": "e", "é": "e", "è": "e", "ê": "e", "â": "a", "à": "a", "ô": "o", "î": "i",
     "ç": "c", "'": " ", "’": " ", "-": " ", ",": " ", ".": " "}
)


def _tokens(text: str) -> set[str]:
    """Lowercase words with accents and punctuation flattened."""
    return {word for word in text.lower().translate(_STRIP).split() if word}


def lookup(dish_name: str | None) -> PackagedDish | None:
    """Find a plat by name, by plate number, or by the words a diner would use.

    Matching is by distinctive keyword rather than substring, because the dish
    name that reaches this function came out of a language model and rarely
    matches the sleeve exactly.
    """
    if not dish_name:
        return None

    key = dish_name.strip().lower()
    for dish in SYMPHONY_MENU.values():
        if key == dish.plate_number.lower():
            return dish
    if key in SYMPHONY_MENU:
        return SYMPHONY_MENU[key]

    spoken = _tokens(key)
    best_name, best_score = None, 0
    for name, keywords in DISH_KEYWORDS.items():
        score = len(spoken & keywords)
        if score > best_score:
            best_name, best_score = name, score

    return SYMPHONY_MENU[best_name] if best_name else None


def allergens_present(dish: PackagedDish) -> set[str]:
    """Every declarable allergen printed in the ingredient list, bolded or not."""
    return {normalise(name) for item in dish.ingredients for name in item.allergens}
