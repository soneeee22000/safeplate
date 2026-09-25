"""The languages a diner is served in, and the three sentences no model may write.

Two things live here. The first is a small table of languages: four the product
is built for, and a few more that walk into a Paris restaurant often enough to
name. Everything outside the table still works — `speech.py` already returns
whatever ISO 639-1 code Gemma heard, and this module hands that code back to the
generator unchanged rather than forcing the diner into English.

The second is `SAFETY_PHRASES`, and it is the reason this file exists. Almost
everything in a reply can be generated: if Gemma renders "we can leave out the
parmesan" a little stiffly in Urdu, nobody is hurt. Three sentences are not like
that. They are the ones a diner reads at the moment the agent has run out of
certainty — and, when Ollama is unreachable or the composed text was discarded,
they are read with no model in the loop at all. A translation that loses the
negation in the first sentence tells an allergic diner the opposite of the truth.
So those three are written out by hand, per language, and checked by a person.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LANGUAGE_CODE = "en"

#: Keys into `SAFETY_PHRASES`. Named, because a typo in a dict lookup for a
#: safety sentence should fail at the call site rather than return nothing.
NO_GUARANTEE = "no_guarantee"
SHARED_WORKSHOP = "shared_workshop"
SPEAK_TO_STAFF = "speak_to_staff"


@dataclass(frozen=True)
class Language:
    code: str
    english_name: str
    #: What its own speakers call it. A diner who cannot read English cannot find
    #: their language in a list written in English.
    endonym: str
    rtl: bool = False
    #: True for the four the product is built and reviewed for; False for the
    #: ones it merely detects and passes through.
    priority: bool = False
    #: Appended to the generation instruction where the model otherwise drifts
    #: into a romanised transliteration or the wrong Chinese character set.
    script_note: str = ""


PRIORITY_LANGUAGES: dict[str, Language] = {
    "my": Language(
        "my", "Burmese", "မြန်မာဘာသာ", priority=True,
        script_note="Write in Burmese script, not romanised transliteration.",
    ),
    "en": Language("en", "English", "English", priority=True),
    "ur": Language(
        "ur", "Urdu", "اردو", rtl=True, priority=True,
        script_note="Write in the Urdu Perso-Arabic (Nastaliq) script, not romanised "
                    "transliteration.",
    ),
    "zh": Language(
        "zh", "Mandarin Chinese", "中文", priority=True,
        script_note="Write in Simplified Chinese characters.",
    ),
    # Auto-detected rather than priority: these three are common enough in a Paris
    # dining room to name, so the interface can label them and get the text
    # direction right — but their safety sentences have not been human-checked, so
    # they fall back to English. Sharing one table keeps that distinction to a
    # single flag instead of two lookups that can disagree.
    "fr": Language("fr", "French", "Français"),
    "ar": Language(
        "ar", "Arabic", "العربية", rtl=True,
        script_note="Write in Arabic script, not romanised transliteration.",
    ),
    "es": Language("es", "Spanish", "Español"),
}

PRIORITY_CODES: tuple[str, ...] = tuple(
    code for code, language in PRIORITY_LANGUAGES.items() if language.priority
)

# ---------------------------------------------------------------------------
# NOT MACHINE TRANSLATED, AND NOT TO BE REGENERATED.
#
# These are the sentences that get read when the model is unavailable, so they
# cannot come from the model. They were written by hand and must be signed off by
# a native speaker of each language — Burmese, Urdu and Mandarin — before this is
# used in a real service. Until that sign-off happens, treat them as drafts:
# they are careful, they are not yet verified, and nobody on this project is a
# native speaker of all three.
#
# Two known translation choices for a reviewer to rule on:
#   - "workshop" is rendered as "kitchen" in Burmese, Urdu and Chinese. The
#     labelling sense of the French `atelier` has no everyday equivalent in any
#     of the three, and "factory" would be wrong about a restaurant.
#   - `{allergen}` is substituted with an EU-14 name in English, so the finished
#     sentence is mixed-script. A reviewer should decide whether the allergen
#     names need translating too; leaving them in English is at least
#     unambiguous to kitchen staff reading over the diner's shoulder.
# ---------------------------------------------------------------------------
SAFETY_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        NO_GUARANTEE: "We cannot guarantee this dish is free of {allergen}.",
        SHARED_WORKSHOP: "This is made in a workshop that also handles {allergen}.",
        SPEAK_TO_STAFF: "Please speak to a member of staff before ordering.",
    },
    "my": {
        NO_GUARANTEE: "ဤဟင်းလျာတွင် {allergen} မပါဝင်ကြောင်း ကျွန်ုပ်တို့ အာမမခံနိုင်ပါ။",
        SHARED_WORKSHOP: "ဤဟင်းလျာကို {allergen} ကိုပါ ကိုင်တွယ်သည့် မီးဖိုချောင်တွင် ပြုလုပ်ထားပါသည်။",
        SPEAK_TO_STAFF: "ကျေးဇူးပြု၍ မှာယူခြင်းမပြုမီ ဝန်ထမ်းတစ်ဦးဦးနှင့် စကားပြောပါ။",
    },
    "ur": {
        NO_GUARANTEE: "ہم ضمانت نہیں دے سکتے کہ اس کھانے میں {allergen} شامل نہیں ہے۔",
        SHARED_WORKSHOP: "یہ ایسے باورچی خانے میں تیار کیا جاتا ہے جہاں {allergen} بھی "
                         "استعمال ہوتا ہے۔",
        SPEAK_TO_STAFF: "براہِ کرم آرڈر دینے سے پہلے عملے کے کسی رکن سے بات کریں۔",
    },
    "zh": {
        NO_GUARANTEE: "我们无法保证这道菜不含{allergen}。",
        SHARED_WORKSHOP: "这道菜是在同时处理{allergen}的厨房中制作的。",
        SPEAK_TO_STAFF: "请在点餐前与工作人员沟通。",
    },
}


def _canonical(code: str) -> str:
    """Reduce a language tag to the ISO 639-1 code this module keys on.

    Gemma returns tags like ``en-US`` and ``zh_Hans`` as readily as ``en``, and
    `speech.py` passes them through with only a lowercase and a length cap.
    """
    cleaned = code.strip().lower().replace("_", "-")
    base = cleaned.split("-")[0]
    return base or DEFAULT_LANGUAGE_CODE


def _lookup(code: str) -> Language | None:
    return PRIORITY_LANGUAGES.get(_canonical(code))


def is_rtl(code: str) -> bool:
    """True when the language is written right to left.

    Unknown codes are reported as left to right, which is the safer default: a
    right-to-left page rendered left to right is awkward, the reverse is unreadable.
    """
    language = _lookup(code)
    return language.rtl if language else False


def display_name(code: str) -> str:
    """The name to show a speaker of that language, in their own script.

    Falls back to the bare code, which is still more useful to a waiter than a
    blank label.
    """
    language = _lookup(code)
    return language.endonym if language else _canonical(code)


def english_name(code: str) -> str:
    """The language's name in English, for staff-facing labels.

    Falls back to the bare code when the language is not in the table.
    """
    language = _lookup(code)
    return language.english_name if language else _canonical(code)


def generation_instruction(code: str) -> str:
    """The sentence to append to a generation prompt so Gemma answers in `code`.

    Args:
        code: An ISO 639-1 code, as `speech.py` extracted it from the diner's audio.

    Returns:
        A complete instruction, including a script note where the model needs one.
    """
    language = _lookup(code)
    if language is None:
        return (
            f"Write the message in the language with ISO 639-1 code "
            f"'{_canonical(code)}' — the language the diner spoke. Do not answer in "
            "English unless that is the language."
        )

    instruction = f"Write the message in {language.english_name} ({language.endonym})."
    return f"{instruction} {language.script_note}" if language.script_note else instruction


def safety_phrase(key: str, code: str, *, allergen: str = "") -> str:
    """One of the three hand-written safety sentences, in the diner's language.

    Args:
        key: `NO_GUARANTEE`, `SHARED_WORKSHOP` or `SPEAK_TO_STAFF`.
        code: The diner's language. Anything without a checked translation gets
            English, because a machine-translated safety sentence is worse than
            one the diner has to ask a colleague to read.
        allergen: The allergen named in the sentence. Ignored by `SPEAK_TO_STAFF`.

    Returns:
        The sentence, with the allergen substituted.
    """
    phrases = SAFETY_PHRASES.get(_canonical(code), SAFETY_PHRASES[DEFAULT_LANGUAGE_CODE])
    return phrases[key].format(allergen=allergen)
