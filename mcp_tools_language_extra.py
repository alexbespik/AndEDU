"""More language tools for the &.edu MCP server: stories, AI dialogues, conjugation tables, script drills, minimal
pairs, dictation, vocabulary CSV import and translate drills from flashcards. Imported by mcp_server.py, which passes
in its HTTP helpers; every item goes through the backend's validation (server.normalize_practice). No file writes,
no model calls: roleplay_turn asks the backend's /api/language/roleplay."""
import csv
import io
import re

MAX_CARDS = 80


def _item(a, type_, default_prompt, **fields):
    return {"type": type_, "prompt": a.get("prompt") or default_prompt, "explanation": a.get("explanation", ""),
            **{k: v for k, v in fields.items() if v not in (None, "")}}


def parse_vocab_csv(text):
    """Rows of `word,meaning,ipa` (ipa optional; a header row and blank lines are skipped) -> [{word, meaning, ipa?}]."""
    out, seen = [], set()
    for row in csv.reader(io.StringIO(str(text or ""))):
        cells = [c.strip() for c in row]
        if len(cells) < 2 or not cells[0] or not cells[1]:
            continue
        if not out and cells[0].lower() == "word" and cells[1].lower() == "meaning":
            continue
        if cells[0] in seen:
            continue
        seen.add(cells[0])
        out.append({"word": cells[0], "meaning": cells[1], **({"ipa": cells[2].strip("/")} if len(cells) > 2 and cells[2].strip("/") else {})})
    return out[:MAX_CARDS]


def vocab_cards(words, lang):
    """Flashcards in the shape the Languages workspace reads: the IPA follows the meaning on the back."""
    return [{"front": w["word"], "back": w["meaning"] + (f"  /{w['ipa']}/" if w.get("ipa") else ""), "lang": lang} for w in words]


def meaning_of(back):
    """A card's back without IPA (/.../, [...]) or trailing separators (as LanguageLab's meaningOf)."""
    text = re.sub(r"\[[^\]\n]{1,60}\]", "", re.sub(r"/[^/\n]{1,60}/", "", str(back or "")))
    return text.strip(" \t·—–-") or str(back or "").strip()


def translate_items(cards, lang=None):
    """One `translate` item per card: the student sees the meaning and types the word (answer = front)."""
    out, seen = [], set()
    for c in cards or []:
        front, source = str(c.get("front") or "").strip(), meaning_of(c.get("back"))
        if not front or not source or front in seen:
            continue
        seen.add(front)
        out.append({"type": "translate", "prompt": "Translate", "source": source, "answer": front,
                    **({"lang": c.get("lang") or lang} if c.get("lang") or lang else {})})
    return out


def minimal_pair_items(lang, pairs):
    """One `listen_choose` per pair (e.g. ship / sheep): the spoken word alternates between the two sides."""
    out = []
    for i, pr in enumerate(pairs or []):
        words = list(dict.fromkeys(str(w).strip() for w in (pr or []) if str(w).strip()))
        if len(words) >= 2:
            out.append({"type": "listen_choose", "prompt": "Which word did you hear?", "audio_text": words[i % len(words)],
                        "options": words[:6], "answer": words[i % len(words)], "lang": lang})
    return out


def dictation_items(lang, sentences):
    """One `listen_type` per sentence."""
    return [{"type": "listen_type", "prompt": "Type what you hear", "audio_text": str(s).strip(), "lang": lang}
            for s in sentences or [] if str(s).strip()]


def roleplay_body(a):
    """The /api/language/roleplay request for one turn; old field names are sent too so either server shape works."""
    lang, setting = a.get("lang") or "", a.get("setting") or ""
    return {"topicId": a["topic_id"], "persona": a["persona"], "setting": setting, "goal": a.get("goal", ""), "lang": lang,
            "level": a.get("level") or "A2", "scenario": setting or a["persona"], "target_lang": lang,
            "user_message": a.get("message", ""), "history": a.get("history") or []}


def tools(call, q, S, STR, OBJ, ARR):
    LANG = lambda: STR("target language, BCP-47 such as es, fr, de, uk, ja")
    practice = lambda tid, items: call("POST", f"/api/topics/{q(tid)}/practice", {"items": items})
    PAIRS = lambda d: {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": d}
    STRS = lambda d: {"type": "array", "items": {"type": "string"}, "description": d}

    def from_flashcards(a):
        t = call("GET", f"/api/topics/{q(a['topic_id'])}")
        items = translate_items(t.get("flashcards") or [], a.get("lang"))
        if not items:
            return {"added": 0, "note": "This lesson has no flashcards to turn into translate items."}
        return practice(a["topic_id"], items)

    def vocab_csv(a):
        words = parse_vocab_csv(a["csv_text"])
        if not words:
            return {"added": 0, "note": "No rows of word,meaning[,ipa] found."}
        return call("POST", f"/api/topics/{q(a['topic_id'])}/flashcards", {"items": vocab_cards(words, a["lang"])})

    return [
        ("add_story", "Add a story read aloud line by line (each speaker gets their own voice) with comprehension questions "
         "inline. lines: 4-16 [{speaker, text, translation?}]; questions: [{after (0-based line index), question, options, answer}], "
         "answer must be one of options.",
         S(topic_id=STR("topic id"), title=STR("story title"), lang=LANG(), lines=ARR("[{speaker, text, translation?}]"),
           questions=ARR("[{after, question, options, answer}]"), explanation=STR("shown after the questions", optional=True)),
         lambda a: practice(a["topic_id"], [_item(a, "story", "Listen to the story and answer", title=a["title"], lang=a["lang"],
                                                  lines=a["lines"], questions=a["questions"])])),
        ("add_dialogue", "Add an AI roleplay dialogue: the student chats with a persona in the target language to reach a goal "
         "(ungraded; ends after the goal or 6 turns with a recap of corrections).",
         S(topic_id=STR("topic id"), persona=STR("who the partner is, e.g. 'a baker in Seville'"), setting=STR("where it happens"),
           goal=STR("what the student must achieve"), lang=LANG(), level=STR("CEFR level A1-C2", optional=True)),
         lambda a: practice(a["topic_id"], [_item(a, "dialogue", f"Talk with {a['persona']}", persona=a["persona"], setting=a["setting"],
                                                  goal=a["goal"], lang=a["lang"], level=a.get("level") or "A2")])),
        ("add_conjugation", "Add a conjugation table: the student types each form (lenient on case and punctuation, notes accents).",
         S(topic_id=STR("topic id"), verb=STR("infinitive, e.g. hablar"), tense=STR("e.g. present"), lang=LANG(),
           forms=PAIRS("3-8 [[pronoun, form], ...], e.g. [['yo', 'hablo'], ['tú', 'hablas']]")),
         lambda a: practice(a["topic_id"], [_item(a, "conjugate", f"Conjugate {a['verb']} ({a['tense']})", verb=a["verb"], tense=a["tense"],
                                                  lang=a["lang"], forms=a["forms"])])),
        ("add_script_drill", "Add a script drill: match 4-10 glyphs to their romanization; each glyph is read aloud.",
         S(topic_id=STR("topic id"), script=STR("writing system", enum=["hiragana", "katakana", "cyrillic", "hangul", "greek", "arabic", "devanagari"]),
           pairs=PAIRS("[[glyph, romanization], ...]"), lang=STR("language to read the glyphs in (defaults by script)", optional=True)),
         lambda a: practice(a["topic_id"], [_item(a, "script_match", "Match each letter to its sound", script=a["script"], pairs=a["pairs"],
                                                  lang=a.get("lang"))])),
        ("add_minimal_pairs", "Add listening drills for sounds that are easy to confuse (ship / sheep): one 'which word did you hear' "
         "item per pair.",
         S(topic_id=STR("topic id"), lang=LANG(), pairs=PAIRS("[[word, similar word], ...]")),
         lambda a: practice(a["topic_id"], minimal_pair_items(a["lang"], a["pairs"]))),
        ("add_dictation", "Add dictation: one 'type what you hear' item per sentence.",
         S(topic_id=STR("topic id"), lang=LANG(), sentences=STRS("sentences in the target language")),
         lambda a: practice(a["topic_id"], dictation_items(a["lang"], a["sentences"]))),
        ("import_vocab_csv", "Import vocabulary from CSV text with rows word,meaning,ipa (ipa optional, header row allowed) as "
         "flashcards; Languages sessions turn them into meaning, listening and speaking exercises.",
         S(topic_id=STR("topic id"), lang=LANG(), csv_text=STR("CSV text")), vocab_csv),
        ("translate_drill_from_flashcards", "Turn a lesson's flashcards into translate items (the student sees the meaning and types "
         "the word). Offline: no model calls.",
         S(topic_id=STR("topic id"), lang=STR("language for cards without one", optional=True)), from_flashcards),
        ("roleplay_turn", "One turn with the AI roleplay partner (/api/language/roleplay): returns the reply and corrections "
         "[{said, better, why}]. Leave message empty to get the opening line.",
         S(topic_id=STR("topic id the dialogue belongs to"), persona=STR("who the partner is"), message=STR("the student's message", optional=True),
           history=ARR("earlier turns [{role: user|model, text}]", optional=True), lang=STR("target language", optional=True),
           setting=STR("where it happens", optional=True), goal=STR("what the student must achieve", optional=True),
           level=STR("CEFR level", optional=True)),
         lambda a: call("POST", "/api/language/roleplay", roleplay_body(a))),
    ]
