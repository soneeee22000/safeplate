"""Which table a heard dish name is checked against.

Symphony's sealed trays are consulted before the generic dish table, so a loose
Symphony match steals generic dishes: "pesto pasta" once resolved to the vegan
gnocchi on the single word "pesto", and "pâtes carbonara" to the bolognaise on
the single word "pates". The dish table's own entries, and the manufacturer
lookup behind its pesto, were then unreachable. These tests pin the routing.
"""

from __future__ import annotations

import pytest

from safeplate import dishes, loop, menu_symphony

GENERIC: list[tuple[str, str]] = [
    ("pad thai", "pad thai"),
    ("tom yum", "tom yum"),
    ("falafel plate", "falafel plate"),
    ("pesto pasta", "pesto pasta"),
    ("Pesto Pasta", "pesto pasta"),
    ("carbonara", "carbonara"),
    ("pâtes carbonara", "carbonara"),
    ("pates carbonara", "carbonara"),
]

SYMPHONY: list[tuple[str, str]] = [
    ("gnocchi pesto vegan", "gnocchis pesto vegan"),
    ("Gnocchis pesto vegan", "gnocchis pesto vegan"),
    ("gnocchi's pesto", "gnocchis pesto vegan"),
    ("paella", "paella poisson chorizo et poulet"),
    ("paëlla poisson chorizo et poulet", "paella poisson chorizo et poulet"),
    ("pâtes bolognaises", "pates bolognaises"),
    ("bolognaise pasta", "pates bolognaises"),
]


@pytest.mark.parametrize(("heard", "key"), GENERIC)
def test_generic_dish_routes_to_the_dish_table(heard: str, key: str) -> None:
    """A dish the table knows is never hijacked by a Symphony keyword."""
    assert loop.route_packaged(heard) is None
    assert dishes.lookup(heard) is dishes.DISHES[key]


@pytest.mark.parametrize(("heard", "key"), SYMPHONY)
def test_symphony_tray_routes_to_symphony(heard: str, key: str) -> None:
    """Each sealed tray is still reached by the words a diner would use for it."""
    assert loop.route_packaged(heard) is menu_symphony.SYMPHONY_MENU[key]


@pytest.mark.parametrize("heard", ["pesto", "pates", "vegan", "poulet", "pâtes"])
def test_one_generic_word_is_not_a_symphony_match(heard: str) -> None:
    """A word shared with ordinary dishes cannot select a tray on its own."""
    assert menu_symphony.lookup(heard) is None


@pytest.mark.parametrize(
    ("heard", "key"),
    [("gnocchi", "gnocchis pesto vegan"), ("chorizo", "paella poisson chorizo et poulet"),
     ("bolognese", "pates bolognaises"), ("vegan pesto", "gnocchis pesto vegan")],
)
def test_distinctive_word_or_two_words_select_a_tray(heard: str, key: str) -> None:
    """One distinctive word, or two shared ones, is enough to name a tray."""
    assert menu_symphony.lookup(heard) is menu_symphony.SYMPHONY_MENU[key]


def test_plate_number_still_selects_a_tray() -> None:
    """The code printed on the sleeve is the strongest match there is."""
    tray = menu_symphony.SYMPHONY_MENU["gnocchis pesto vegan"]
    assert loop.route_packaged(tray.plate_number) is tray


@pytest.mark.parametrize("heard", ["", None, "   "])
def test_no_dish_name_routes_nowhere(heard: str | None) -> None:
    """An empty name selects no tray; the loop asks the diner instead."""
    assert loop.route_packaged(heard) is None
