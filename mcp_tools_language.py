"""Language tools for the &.edu MCP server (gamified exercises). Imported by mcp_server.py, which passes in
its HTTP helpers; every tool goes through the backend's validation (server.normalize_practice)."""
import re
import unicodedata


def _slug(text):
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:70] or "language-unit"


def _item(a, **fields):
    return {"prompt": a.get("prompt") or fields.pop("default_prompt"), "explanation": a.get("explanation", ""),
            **{k: v for k, v in fields.items() if k != "default_prompt" and v not in (None, "")}}


# Noun articles by grammatical gender (m, f, n, pl) for languages whose cards show them; others may pass `article`.
ARTICLES = {"de": {"m": "der", "f": "die", "n": "das", "pl": "die"}}


def _article(w, lang):
    return w.get("article") or ARTICLES.get(str(lang).split("-")[0], {}).get(w.get("gender") or "")


def _front(w, lang):
    """The word as it is learned: German nouns with their article (der Apfel), everything else as given."""
    art = _article(w, lang)
    return f"{art} {w['word']}" if art and not w["word"].lower().startswith(art.lower() + " ") else w["word"]


def _plural(w, lang):
    pl = str(w.get("plural") or "").strip()
    art = ARTICLES.get(str(lang).split("-")[0], {}).get("pl")
    return f"{art} {pl}" if pl and art and not pl.lower().startswith(art + " ") else pl


def _card(w, lang):
    meaning = w["meaning"] + (" (plural)" if w.get("gender") == "pl" and "plural" not in w["meaning"] else "")
    back = meaning + (f"  /{w['ipa'].strip('/')}/" if w.get("ipa") else "")
    hint = " ".join(x for x in ((f"Plural: {_plural(w, lang)}." if w.get("plural") else ""), w.get("example") or "") if x)
    card = {"front": _front(w, lang), "back": back, "lang": lang, **({"hint": hint[:200]} if hint else {})}
    if w.get("gender"):  # kept for clients; the article is in `front` either way
        card["gender"], card["article"] = w["gender"], _article(w, lang)
    return card


def unit_topic(a):
    """A complete language unit (topic JSON) from a word list and optional phrases; no model calls."""
    lang, words, phrases = a["lang"], a.get("words") or [], a.get("phrases") or []
    ipa = lambda w: ('/' + w['ipa'].strip('/') + '/') if w.get('ipa') else ''
    if any(w.get("gender") or w.get("plural") for w in words):  # nouns with gender: article and plural columns
        rows = "\n".join(f"| {_front(w, lang)} | {_plural(w, lang) or '—'} | {w['meaning']} | {ipa(w)} |" for w in words)
        table = f"| Word | Plural | Meaning | Pronunciation |\n| --- | --- | --- | --- |\n{rows}\n"
    else:
        rows = "\n".join(f"| {w['word']} | {w['meaning']} | {ipa(w)} |" for w in words)
        table = f"| Word | Meaning | Pronunciation |\n| --- | --- | --- |\n{rows}\n"
    md = f"# {a['title']}\n\n{a.get('intro', '')}\n\n## Words\n\n{table}"
    if phrases:
        md += "\n## Phrases\n\n" + "\n".join(f"- **{p['text']}**: {p['meaning']}" for p in phrases) + "\n"
    if a.get("notes"):
        md += f"\n{a['notes'].strip()}\n"
    practice = []
    if len(words) >= 3:
        practice.append({"type": "match_pairs", "prompt": "Match each word to its meaning", "pairs": [[_front(w, lang), w["meaning"]] for w in words[:8]]})
    all_tiles = [t for p in phrases for t in re.findall(r"[\w'’]+", p["text"])]
    for i, p in enumerate(phrases[:8]):
        tiles = re.findall(r"[\w'’]+", p["text"])
        extra = (list(p.get("distractors") or []) or [t for t in dict.fromkeys(all_tiles) if t not in tiles][:3]
                 or [w["word"] for w in words if w["word"] not in tiles][:3])
        practice.append({"type": "translate", "prompt": "Translate", "source": p["meaning"], "answer": p["text"], "accepted": p.get("accepted") or [], "lang": lang})
        if 4 <= len(tiles) + len(extra) <= 14:
            practice.append({"type": "word_bank", "prompt": "Build the sentence", "source": p["meaning"], "answer": p["text"], "bank": tiles + extra, "lang": lang})
        practice.append({"type": "listen_type", "prompt": "Type what you hear", "audio_text": p["text"], "lang": lang} if i % 2 == 0 else
                        {"type": "speak", "prompt": "Say it", "target": p["text"], "translation": p["meaning"], "ipa": p.get("ipa", ""), "lang": lang})
    practice += [dict(p) for p in a.get("practice") or [] if isinstance(p, dict)]  # extra items (fill_blank, conjugate, ...)
    out = {"id": a.get("id") or _slug(a["title"]), "title": a["title"], "category": a.get("category") or "Languages",
           "difficulty": a.get("level") or "Beginner", "summary": a.get("intro") or f"Words and phrases: {a['title']}.",
           "workspace": "language", "lang": lang, "markdownContent": md, "quiz": [], "practice": practice,
           "flashcards": [_card(w, lang) for w in words]}
    if isinstance(a.get("source"), dict):
        out["source"] = dict(a["source"])
    return out


def tools(call, q, S, STR, OBJ, ARR):
    LANG = lambda: STR("target language, BCP-47 such as es, fr, de, uk, ja")
    WORDS = {"type": "array", "items": {"type": "object"}, "description": "[{word, meaning, ipa?, example?, gender? (m|f|n|pl: German nouns get der/die/das), plural?}]"}
    practice = lambda tid, *items: call("POST", f"/api/topics/{q(tid)}/practice", {"items": list(items)})
    event = lambda payload: call("POST", "/api/agy/events", {"type": "SWITCH_STUDIO_MODE", "payload": {"mode": "language", **payload}})

    def vocab_set(a):
        words = a["words"]
        out = {"flashcards": call("POST", f"/api/topics/{q(a['topic_id'])}/flashcards", {"items": [_card(w, a["lang"]) for w in words]})}
        if len(words) >= 3:
            out["match_pairs"] = practice(a["topic_id"], {"type": "match_pairs", "prompt": "Match each word to its meaning",
                                                          "pairs": [[w["word"], w["meaning"]] for w in words[:8]]})
        out["note"] = "Sessions in Languages also turn every flashcard into meaning, listening and speaking exercises."
        return out

    def overview(a):
        units = []
        for t in call("GET", "/api/topics"):
            if ((t.get("source") or {}).get("workspace") or t.get("workspace")) != "language":
                continue
            kinds = {}
            for p in t.get("practice") or []:
                kinds[p.get("type")] = kinds.get(p.get("type"), 0) + 1
            units.append({"id": t["id"], "title": t.get("title"), "course": (t.get("source") or {}).get("courseTitle"),
                          "words": len(t.get("flashcards") or []), "langs": sorted({c.get("lang") for c in t.get("flashcards") or [] if c.get("lang")}),
                          "exercises": kinds})
        out = {"units": units}
        if a.get("user_id"):
            out["engagement"] = call("GET", f"/api/engage/{q(a['user_id'])}")
        return out

    return [
        ("add_translation_exercise", "gamified translation: the student types the translation of `source`. Typos and missing accents "
         "are forgiven; give other correct translations in `accepted`.",
         S(topic_id=STR("topic id"), source=STR("text to translate"), answer=STR("best translation"), lang=LANG(),
           accepted={"type": "array", "items": {"type": "string"}, "description": "other correct answers (up to 6)", "optional": True},
           source_lang=STR("language of `source` when it should be read aloud", optional=True),
           prompt=STR("instruction, default 'Translate'", optional=True), explanation=STR("shown after answering", optional=True)),
         lambda a: practice(a["topic_id"], _item(a, default_prompt="Translate", type="translate", source=a["source"], answer=a["answer"],
                                                 accepted=a.get("accepted") or [], lang=a["lang"], sourceLang=a.get("source_lang")))),
        ("add_word_bank", "Build-the-sentence exercise: the student taps word tiles in order. The bank is the answer's words plus distractors.",
         S(topic_id=STR("topic id"), answer=STR("the sentence, words separated by spaces"), lang=LANG(),
           distractors={"type": "array", "items": {"type": "string"}, "description": "2-5 wrong words"},
           source=STR("the meaning shown to the student, e.g. the English sentence", optional=True),
           prompt=STR("instruction", optional=True), explanation=STR("shown after answering", optional=True)),
         lambda a: practice(a["topic_id"], _item(a, default_prompt="Build the sentence", type="word_bank", answer=a["answer"],
                                                 bank=re.findall(r"[\w'’]+", a["answer"]) + list(a["distractors"]), source=a.get("source"), lang=a["lang"]))),
        ("add_listening_exercise", "Listening: the app reads `audio_text` aloud (never shown). kind 'type' = type what you hear; "
         "kind 'choose' = pick it from `options` (must include audio_text).",
         S(topic_id=STR("topic id"), audio_text=STR("what is said"), lang=LANG(), kind=STR("type | choose", enum=["type", "choose"]),
           options={"type": "array", "items": {"type": "string"}, "description": "for choose: 3-5 similar-sounding options", "optional": True},
           prompt=STR("instruction", optional=True), explanation=STR("shown after answering", optional=True)),
         lambda a: practice(a["topic_id"], _item(a, default_prompt="Type what you hear", type="listen_type", audio_text=a["audio_text"], lang=a["lang"])
                            if a["kind"] == "type" else
                            _item(a, default_prompt="What did you hear?", type="listen_choose", audio_text=a["audio_text"], lang=a["lang"],
                                  options=a.get("options") or [], answer=a["audio_text"]))),
        ("add_speaking_exercise", "Speaking: the student says `target` and the browser's speech recognition scores it (ungraded where unsupported).",
         S(topic_id=STR("topic id"), target=STR("word or phrase to say"), lang=LANG(), ipa=STR("IPA without slashes", optional=True),
           translation=STR("meaning", optional=True), prompt=STR("instruction", optional=True)),
         lambda a: practice(a["topic_id"], _item(a, default_prompt="Say it", type="speak", target=a["target"], lang=a["lang"],
                                                 ipa=a.get("ipa"), translation=a.get("translation")))),
        ("add_language_exercises", "Bulk-add language exercises of any type (translate, word_bank, listen_type, listen_choose, speak, "
         "match_pairs, fill_blank); see AGENTS.md for fields. Invalid items are dropped and counted.",
         S(topic_id=STR("topic id"), items=ARR("practice items")), lambda a: practice(a["topic_id"], *a["items"])),
        ("add_vocab_set", "Add vocabulary to a lesson: flashcards (read aloud, IPA on the back) plus a matching game. Sessions turn each word "
         "into meaning, listening and speaking exercises automatically.",
         S(topic_id=STR("topic id"), lang=LANG(), words=WORDS), vocab_set),
        ("build_language_unit", "Create a whole language unit offline (no model quota) from words and phrases: notes with a word table, "
         "flashcards, matching, translation, word-bank, listening and speaking exercises. It appears on the Languages > Learn path. Replaces any topic with the same id: check list_topics first.",
         S(title=STR("unit title, e.g. 'Spanish: At the café'"), lang=LANG(), words=WORDS,
           phrases={"type": "array", "items": {"type": "object"}, "description": "[{text (target language), meaning, accepted?, ipa?}]", "optional": True},
           intro=STR("one or two sentences", optional=True), level=STR("Beginner | Intermediate | Advanced", optional=True),
           id=STR("kebab-case id (default from title)", optional=True)),
         lambda a: call("POST", "/api/topics", unit_topic(a))),
        ("start_language_session", "Open a practice session on the student's screen (Languages > Practice): mode mixed | missed | listen | "
         "speak | new | unit (with unit_id).",
         S(mode=STR("session mode", optional=True, enum=["mixed", "missed", "listen", "speak", "new", "unit"]),
           unit_id=STR("topic id for mode unit", optional=True)),
         lambda a: event({"tab": "session", "sessionMode": a.get("mode", "mixed"), "unitId": a.get("unit_id")})),
        ("open_language_tab", "Show a Languages tab on the student's screen: path | practice | roleplay | words | cards | pronounce | courses.",
         S(tab=STR("tab", enum=["path", "practice", "roleplay", "words", "cards", "pronounce", "courses"])), lambda a: event({"tab": a["tab"]})),
        ("language_overview", "Every language unit with word counts, languages and exercise counts by type; with user_id also XP, "
         "streak and goals. (Crowns and word strength live in the student's browser.)",
         S(user_id=STR("profile id", optional=True)), overview),
        ("seed_language_course", "Install the built-in offline course for a language (German A1-A2: 10 units with genders, plurals, "
         "cases, separable and modal verbs, Perfekt, weil/dass/wenn). Never overwrites a lesson that already exists; admin-only with accounts.",
         S(lang=STR("course language", enum=["de"])), lambda a: call("POST", "/api/language/seed", {"lang": a.get("lang") or "de"})),
        ("start_roleplay", "Open a conversational Roleplay Partner session on the student's screen (Languages > Roleplay).",
         S(scenario=STR("scenario id or description", optional=True)),
         lambda a: event({"tab": "roleplay", "scenario": a.get("scenario")})),
        ("explain_answer", "Ask the pedagogical tutor for a structured linguistic explanation of a student answer (/api/tutor/explain-answer).",
         S(question=STR("the exercise prompt or question"),
           student_answer=STR("the student's submitted answer"),
           correct_answer=STR("the correct expected answer"),
           context=STR("sentence or dialogue context", optional=True),
           lang=LANG()),
         lambda a: call("POST", "/api/tutor/explain-answer", {
             "question": a["question"],
             "student_answer": a["student_answer"],
             "correct_answer": a["correct_answer"],
             "context": a.get("context", ""),
             "lang": a.get("lang", "en"),
         })),
        ("start_language_practice", "Start a practice session or open the Practice hub in the Languages workspace.",
         S(mode=STR("session mode", optional=True, enum=["mixed", "missed", "listen", "speak", "new", "unit"]),
           unit_id=STR("topic id for mode unit", optional=True)),
         lambda a: event({"tab": "practice", "sessionMode": a.get("mode", "mixed"), "unitId": a.get("unit_id")})),
    ]
