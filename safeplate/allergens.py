"""The EU 14 declarable allergens, and the synonyms that hide them.

Regulation (EU) No 1169/2011 Annex II. This is data, not a prompt: whether an
ingredient is a declarable allergen is never a question put to the model. The
model reads and speaks; this file decides.
"""

from __future__ import annotations

EU_14: tuple[str, ...] = (
    "cereals containing gluten",
    "crustaceans",
    "eggs",
    "fish",
    "peanuts",
    "soybeans",
    "milk",
    "nuts",
    "celery",
    "mustard",
    "sesame",
    "sulphites",
    "lupin",
    "molluscs",
)

# Ingredient or colloquial term -> declarable allergen. Deliberately includes the
# words diners actually say ("nuoc mam", "parmesan") alongside label vocabulary
# ("casein", "semolina"), because both arrive here: one from speech, one from OCR.
SYNONYMS: dict[str, str] = {
    # fish
    "fish sauce": "fish", "nuoc mam": "fish", "nam pla": "fish", "anchovy": "fish",
    "anchovies": "fish", "worcestershire": "fish", "bonito": "fish", "katsuobushi": "fish",
    "colatura": "fish", "garum": "fish", "poisson": "fish",
    # crustaceans / molluscs
    "shrimp": "crustaceans", "prawn": "crustaceans", "dried shrimp": "crustaceans",
    "crevette": "crustaceans", "crab": "crustaceans", "lobster": "crustaceans",
    "shrimp paste": "crustaceans", "kapi": "crustaceans",
    "mussel": "molluscs", "mussels": "molluscs", "moules": "molluscs",
    "squid": "molluscs", "calamari": "molluscs", "oyster": "molluscs",
    "oyster sauce": "molluscs", "clam": "molluscs", "scallop": "molluscs",
    # milk
    "casein": "milk", "caseinate": "milk", "whey": "milk", "lactose": "milk",
    "butter": "milk", "beurre": "milk", "cream": "milk", "crème": "milk",
    "cheese": "milk", "fromage": "milk", "parmesan": "milk", "pecorino": "milk",
    "mozzarella": "milk", "ghee": "milk", "yoghurt": "milk", "yogurt": "milk",
    # eggs
    "egg": "eggs", "oeuf": "eggs", "œuf": "eggs", "jaune d'oeuf": "eggs",
    "egg yolk": "eggs", "albumen": "eggs", "mayonnaise": "eggs", "aioli": "eggs",
    # gluten
    "wheat": "cereals containing gluten", "blé": "cereals containing gluten",
    "flour": "cereals containing gluten", "farine": "cereals containing gluten",
    "semolina": "cereals containing gluten", "semoule": "cereals containing gluten",
    "barley": "cereals containing gluten", "rye": "cereals containing gluten",
    "spelt": "cereals containing gluten", "couscous": "cereals containing gluten",
    "breadcrumbs": "cereals containing gluten", "pasta": "cereals containing gluten",
    "soy sauce": "cereals containing gluten", "seitan": "cereals containing gluten",
    # nuts / peanuts
    "peanut": "peanuts", "arachide": "peanuts", "groundnut": "peanuts",
    "cacahuète": "peanuts", "peanut oil": "peanuts",
    "almond": "nuts", "amande": "nuts", "hazelnut": "nuts", "noisette": "nuts",
    "walnut": "nuts", "noix": "nuts", "cashew": "nuts", "pistachio": "nuts",
    "pine nut": "nuts", "pine nuts": "nuts", "pignon": "nuts", "pecan": "nuts",
    # sesame / soy / others
    "tahini": "sesame", "tahina": "sesame", "sesame oil": "sesame", "sésame": "sesame",
    "soy": "soybeans", "soya": "soybeans", "tofu": "soybeans", "edamame": "soybeans",
    "miso": "soybeans", "tempeh": "soybeans",
    "celeriac": "celery", "céleri": "celery",
    "dijon": "mustard", "moutarde": "mustard",
    "sulphur dioxide": "sulphites", "e220": "sulphites", "e221": "sulphites",
    "e202": "sulphites",
}


#: Words diners use that cover more than one declarable allergen. Deliberately
#: generous: someone who says "nuts" may or may not mean peanuts too, and the
#: safe reading of that ambiguity is the wider one. Erring wide costs a diner a
#: dish; erring narrow costs them an ambulance.
GROUPS: dict[str, tuple[str, ...]] = {
    "nuts": ("nuts", "peanuts"),
    "nut": ("nuts", "peanuts"),
    "tree nut": ("nuts",),
    "tree nuts": ("nuts",),
    "treenuts": ("nuts",),
    "fruits a coque": ("nuts",),
    "fruits à coque": ("nuts",),
    "fruit a coque": ("nuts",),
    "shellfish": ("crustaceans", "molluscs"),
    "seafood": ("fish", "crustaceans", "molluscs"),
    "fruits de mer": ("crustaceans", "molluscs"),
    "dairy": ("milk",),
    "lactose": ("milk",),
    "laitier": ("milk",),
    "produits laitiers": ("milk",),
    "gluten": ("cereals containing gluten",),
    "wheat": ("cereals containing gluten",),
    "sulfites": ("sulphites",),
}


def expand(term: str) -> tuple[str, ...]:
    """Every declarable allergen a diner's word could mean.

    Single-allergen terms come back as a one-tuple; broad words like "seafood"
    come back as all the allergens they cover.
    """
    key = term.strip().lower()
    if key in GROUPS:
        return GROUPS[key]
    for phrase, allergens in GROUPS.items():
        if phrase in key:
            return allergens
    return (normalise(key),)


def normalise(term: str) -> str:
    """Map an ingredient or spoken term to its declarable allergen, if any.

    Returns the EU-14 allergen name, or the lowercased term unchanged when it is
    not a known allergen or synonym.
    """
    key = term.strip().lower()
    if key in EU_14:
        return key
    if key in SYNONYMS:
        return SYNONYMS[key]
    # Broad diner words resolve to their principal allergen here; callers that
    # need every allergen a word covers should use `expand` instead.
    if key in GROUPS:
        return GROUPS[key][0]
    # "no fish sauce please" and "contains anchovy paste" both need substring reach.
    for synonym, allergen in SYNONYMS.items():
        if synonym in key:
            return allergen
    return key


def conflicts(avoid: str, ingredient_allergens: list[str], ingredient_name: str) -> bool:
    """True when an ingredient is something the diner said to avoid."""
    targets = expand(avoid)
    if any(target in ingredient_allergens for target in targets):
        return True
    # Direct naming: the diner said "fish sauce" and this ingredient is fish sauce.
    if normalise(ingredient_name) in targets:
        return True
    return avoid.strip().lower() in ingredient_name.lower()
