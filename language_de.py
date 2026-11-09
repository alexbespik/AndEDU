"""Built-in German course (A1-A2), offline: ten units of words (with gender, plural, IPA and an example), phrases and
grammar drills, turned into topics by mcp_tools_language.unit_topic. Standard library only; never imports server.py.

Used by POST /api/language/seed (language_tts.build_router) and scripts/seed_german.py. Topic ids start with `de-`;
seeding never overwrites a lesson that already exists."""
import mcp_tools_language

LANG = "de"
COURSE_TITLE = "German A1-A2 (built in)"


def W(word, meaning, ipa, gender="", plural="", example=""):
    return {"word": word, "meaning": meaning, "ipa": ipa, "gender": gender, "plural": plural, "example": example}


def P(text, meaning, accepted=(), distractors=()):
    return {"text": text, "meaning": meaning, "accepted": list(accepted), "distractors": list(distractors)}


def blank(prompt, options, answer, explanation):
    return {"type": "fill_blank", "prompt": prompt, "options": options, "answer": answer, "explanation": explanation}


def conj(verb, tense, forms, prompt="Conjugate the verb"):
    return {"type": "conjugate", "prompt": prompt, "verb": verb, "tense": tense, "lang": LANG, "forms": forms}


PRONOUNS = ["ich", "du", "er/sie/es", "wir", "ihr", "sie/Sie"]

UNITS = [
    {
        "id": "de-01-hallo", "title": "German 1: Hallo! Greetings and sein", "level": "Beginner (A1)",
        "intro": "Say hello and goodbye, introduce yourself, say where you come from, and meet the verb sein (to be).",
        "words": [
            W("Hallo", "hello", "ˈhalo", example="Hallo, ich bin Anna."),
            W("tschüss", "bye", "tʃʏs", example="Tschüss, bis morgen!"),
            W("danke", "thank you", "ˈdaŋkə", example="Danke schön!"),
            W("bitte", "please; you're welcome", "ˈbɪtə", example="Ein Wasser, bitte."),
            W("ja", "yes", "jaː"),
            W("nein", "no", "naɪ̯n"),
            W("Name", "name", "ˈnaːmə", "m", "Namen", "Mein Name ist Paul."),
            W("Herr", "Mr; gentleman", "hɛʁ", "m", "Herren", "Guten Tag, Herr Müller!"),
            W("Frau", "Mrs; woman", "fʁaʊ̯", "f", "Frauen", "Guten Abend, Frau Schmidt!"),
            W("Tag", "day", "taːk", "m", "Tage", "Guten Tag!"),
            W("sein", "to be", "zaɪ̯n", example="Ich bin Student."),
            W("heißen", "to be called", "ˈhaɪ̯sn̩", example="Ich heiße Lena."),
            W("kommen", "to come", "ˈkɔmən", example="Ich komme aus Österreich."),
        ],
        "phrases": [
            P("Guten Morgen!", "Good morning!"),
            P("Wie heißt du?", "What is your name?", ["Wie ist dein Name?"]),
            P("Ich heiße Anna.", "My name is Anna.", ["Mein Name ist Anna.", "Ich bin Anna."], ["heißt", "bin", "Name"]),
            P("Woher kommst du?", "Where are you from?", ["Woher kommen Sie?"], ["Wo", "komme", "kommt"]),
            P("Ich komme aus Deutschland.", "I come from Germany.", ["Ich bin aus Deutschland."], ["kommst", "in", "nach"]),
            P("Wie geht es dir?", "How are you?", ["Wie geht's?", "Wie geht es Ihnen?", "Wie geht's dir?"], ["du", "ist", "mir"]),
            P("Mir geht es gut, danke.", "I am fine, thanks.", ["Mir geht's gut, danke.", "Gut, danke.", "Es geht mir gut, danke."], ["Ich", "bin", "dir"]),
            P("Wir sind Freunde.", "We are friends.", [], ["seid", "ist", "Freund"]),
        ],
        "notes": """## Grammar: sein (to be)

| Person | sein |
| --- | --- |
| ich | bin |
| du | bist |
| er / sie / es | ist |
| wir | sind |
| ihr | seid |
| sie / Sie | sind |

- **du** is for friends, family and children; **Sie** (always capitalized) is the polite form for adults you don't know.
- Professions and nationalities take no article: *Ich bin Student.* (not *ein Student* in everyday speech).
- Every noun is capitalized: *der Name, die Frau, der Tag*.""",
        "practice": [
            conj("sein", "Präsens (present)", [[p, f] for p, f in zip(PRONOUNS, ["bin", "bist", "ist", "sind", "seid", "sind"])]),
            blank("Du ___ sehr nett.", ["bist", "bin", "ist", "seid"], "bist", "du → **bist**: *Du bist sehr nett* (You are very nice)."),
            blank("Wir ___ aus Berlin.", ["sind", "seid", "ist", "bin"], "sind", "wir → **sind**; ihr → seid."),
            blank("___ heißen Sie? (polite: What is your name?)", ["Wie", "Wo", "Was", "Woher"], "Wie",
                  "German asks *how* someone is called: **Wie** heißen Sie?"),
        ],
    },
    {
        "id": "de-02-der-die-das", "title": "German 2: der, die, das — genders and plurals", "level": "Beginner (A1)",
        "intro": "Every German noun has a gender: der (masculine), die (feminine) or das (neuter). Learn each noun with its article and plural.",
        "words": [
            W("Mann", "man", "man", "m", "Männer", "Der Mann ist groß."),
            W("Kind", "child", "kɪnt", "n", "Kinder", "Das Kind spielt."),
            W("Tisch", "table", "tɪʃ", "m", "Tische", "Der Tisch ist neu."),
            W("Lampe", "lamp", "ˈlampə", "f", "Lampen", "Die Lampe ist hell."),
            W("Buch", "book", "buːx", "n", "Bücher", "Das Buch ist interessant."),
            W("Stuhl", "chair", "ʃtuːl", "m", "Stühle", "Der Stuhl ist bequem."),
            W("Tür", "door", "tyːɐ̯", "f", "Türen", "Die Tür ist zu."),
            W("Fenster", "window", "ˈfɛnstɐ", "n", "Fenster", "Das Fenster ist offen."),
            W("Schlüssel", "key", "ˈʃlʏsl̩", "m", "Schlüssel", "Wo ist der Schlüssel?"),
            W("Tasche", "bag", "ˈtaʃə", "f", "Taschen", "Die Tasche ist schwer."),
            W("Handy", "mobile phone", "ˈhɛndi", "n", "Handys", "Das Handy ist kaputt."),
            W("Leute", "people", "ˈlɔʏ̯tə", "pl", "", "Die Leute sind nett."),
        ],
        "phrases": [
            P("Das ist ein Buch.", "That is a book.", ["Das ist ein Buch"], ["eine", "einen", "sind"]),
            P("Der Tisch ist groß.", "The table is big.", [], ["Die", "Das", "sind"]),
            P("Die Lampe ist neu.", "The lamp is new.", [], ["Der", "Das", "sind"]),
            P("Das Kind ist klein.", "The child is small.", [], ["Der", "Die", "Kinder"]),
            P("Die Bücher sind alt.", "The books are old.", [], ["Das", "ist", "Buchs"]),
            P("Wo ist mein Schlüssel?", "Where is my key?", [], ["meine", "sind", "Wer"]),
            P("Ist das eine Tasche?", "Is that a bag?", [], ["ein", "einen", "Sind"]),
        ],
        "notes": """## Grammar: articles and plurals

| | masculine | feminine | neuter | plural |
| --- | --- | --- | --- | --- |
| the | **der** Tisch | **die** Lampe | **das** Buch | **die** Bücher |
| a | **ein** Tisch | **eine** Lampe | **ein** Buch | — |

- Always learn the article with the noun: *der Stuhl*, *die Tür*, *das Fenster*.
- Helpful patterns: nouns in **-e** are often feminine (*die Lampe, die Tasche*); **-chen** and **-lein** are always neuter.
- The plural article is always **die**. Plural endings vary: *-e (Tische), -er (Kinder), -en (Türen), -s (Handys)*, or none (*Fenster*), often with an umlaut (*Bücher, Stühle, Männer*).
- *Leute* (people) exists only in the plural.""",
        "practice": [
            blank("___ Fenster ist offen.", ["Das", "Der", "Die"], "Das", "**das** Fenster: neuter."),
            blank("___ Tür ist zu.", ["Die", "Der", "Das"], "Die", "**die** Tür: feminine."),
            blank("___ Stuhl ist bequem.", ["Der", "Die", "Das"], "Der", "**der** Stuhl: masculine."),
            blank("ein Kind, zwei ___", ["Kinder", "Kinds", "Kinden", "Kindes"], "Kinder", "das Kind → die **Kinder** (plural -er)."),
            blank("ein Buch, drei ___", ["Bücher", "Buchs", "Buche", "Büchen"], "Bücher", "das Buch → die **Bücher** (umlaut + -er)."),
        ],
    },
    {
        "id": "de-03-essen", "title": "German 3: Food and the Akkusativ", "level": "Beginner (A1)",
        "intro": "Order food and drinks, say what you eat, and use the accusative case for the thing you eat, drink or buy.",
        "words": [
            W("Apfel", "apple", "ˈapfl̩", "m", "Äpfel", "Ich esse einen Apfel."),
            W("Brot", "bread", "bʁoːt", "n", "Brote", "Das Brot ist frisch."),
            W("Käse", "cheese", "ˈkɛːzə", "m", "", "Ich kaufe den Käse."),
            W("Milch", "milk", "mɪlç", "f", "", "Die Milch ist kalt."),
            W("Wasser", "water", "ˈvasɐ", "n", "", "Ein Wasser, bitte."),
            W("Kaffee", "coffee", "ˈkafe", "m", "Kaffees", "Der Kaffee ist heiß."),
            W("Tee", "tea", "teː", "m", "Tees", "Trinkst du gern Tee?"),
            W("Suppe", "soup", "ˈzʊpə", "f", "Suppen", "Die Suppe ist lecker."),
            W("Ei", "egg", "aɪ̯", "n", "Eier", "Ich esse ein Ei."),
            W("Banane", "banana", "baˈnaːnə", "f", "Bananen", "Die Banane ist gelb."),
            W("essen", "to eat", "ˈɛsn̩", example="Er isst gern Obst."),
            W("trinken", "to drink", "ˈtʁɪŋkn̩", example="Wir trinken Wasser."),
            W("möchten", "would like", "ˈmœçtn̩", example="Ich möchte einen Tee."),
        ],
        "phrases": [
            P("Ich esse einen Apfel.", "I am eating an apple.", [], ["ein", "einem", "isst"]),
            P("Ich trinke einen Kaffee.", "I am drinking a coffee.", [], ["ein", "trinkt", "eine"]),
            P("Ich möchte eine Suppe, bitte.", "I would like a soup, please.", [], ["einen", "ein", "möchtest"]),
            P("Isst du gern Käse?", "Do you like eating cheese?", ["Magst du Käse?"], ["Esst", "Esse", "gerne"]),
            P("Er trinkt keine Milch.", "He doesn't drink milk.", [], ["kein", "nicht", "trinke"]),
            P("Wir kaufen den Käse.", "We are buying the cheese.", [], ["der", "dem", "kauft"]),
            P("Ich habe keinen Hunger.", "I am not hungry.", [], ["kein", "bin", "hat"]),
        ],
        "notes": """## Grammar: the accusative (Akkusativ)

The direct object (what you eat, drink, buy, have) is in the accusative. **Only the masculine changes**:

| | masculine | feminine | neuter | plural |
| --- | --- | --- | --- | --- |
| nominative | der / ein / kein | die / eine / keine | das / ein / kein | die / — / keine |
| accusative | **den / einen / keinen** | die / eine / keine | das / ein / kein | die / — / keine |

- *Der Apfel ist rot.* → *Ich esse **einen** Apfel.*
- **kein** negates a noun (*keine Milch, keinen Hunger*); **nicht** negates a verb or adjective.
- *essen* changes its vowel: du **isst**, er **isst**.""",
        "practice": [
            conj("essen", "Präsens (present)", [[p, f] for p, f in zip(PRONOUNS, ["esse", "isst", "isst", "essen", "esst", "essen"])]),
            blank("Ich esse ___ Apfel.", ["einen", "ein", "eine", "einem"], "einen", "der Apfel is masculine: accusative **einen**."),
            blank("Ich nehme ___ Suppe.", ["eine", "einen", "ein", "einer"], "eine", "die Suppe is feminine: the accusative stays **eine**."),
            blank("Sie kauft ___ Käse.", ["den", "der", "dem", "des"], "den", "der Käse → accusative **den** Käse."),
            blank("Ich habe ___ Hunger.", ["keinen", "kein", "nicht", "keine"], "keinen", "der Hunger is masculine: accusative **keinen**."),
        ],
    },
    {
        "id": "de-04-familie", "title": "German 4: Family and possessives", "level": "Beginner (A1)",
        "intro": "Talk about your family with mein, dein, sein, ihr, unser, and the verb haben (to have).",
        "words": [
            W("Familie", "family", "faˈmiːli̯ə", "f", "Familien", "Meine Familie ist groß."),
            W("Mutter", "mother", "ˈmʊtɐ", "f", "Mütter", "Meine Mutter ist Ärztin."),
            W("Vater", "father", "ˈfaːtɐ", "m", "Väter", "Mein Vater kocht gern."),
            W("Eltern", "parents", "ˈɛltɐn", "pl", "", "Meine Eltern wohnen in Köln."),
            W("Bruder", "brother", "ˈbʁuːdɐ", "m", "Brüder", "Mein Bruder ist zehn."),
            W("Schwester", "sister", "ˈʃvɛstɐ", "f", "Schwestern", "Ich habe eine Schwester."),
            W("Sohn", "son", "zoːn", "m", "Söhne", "Ihr Sohn heißt Tim."),
            W("Tochter", "daughter", "ˈtɔxtɐ", "f", "Töchter", "Seine Tochter ist klein."),
            W("Oma", "grandma", "ˈoːma", "f", "Omas", "Meine Oma ist achtzig."),
            W("Opa", "grandpa", "ˈoːpa", "m", "Opas", "Mein Opa liest viel."),
            W("Geschwister", "siblings", "ɡəˈʃvɪstɐ", "pl", "", "Hast du Geschwister?"),
            W("haben", "to have", "ˈhaːbn̩", example="Wir haben zwei Kinder."),
        ],
        "phrases": [
            P("Das ist meine Mutter.", "This is my mother.", [], ["mein", "meinen", "sind"]),
            P("Mein Bruder heißt Max.", "My brother is called Max.", ["Mein Bruder ist Max."], ["Meine", "heiße", "Meinen"]),
            P("Hast du Geschwister?", "Do you have siblings?", [], ["Habt", "hat", "Hat"]),
            P("Ich habe eine Schwester.", "I have a sister.", [], ["einen", "ein", "hat"]),
            P("Unsere Eltern wohnen in Wien.", "Our parents live in Vienna.", [], ["Unser", "wohnt", "im"]),
            P("Wie alt ist dein Vater?", "How old is your father?", [], ["deine", "sind", "Wo"]),
            P("Ihre Tochter ist fünf Jahre alt.", "Her daughter is five years old.", [], ["Ihr", "sind", "Jahr"]),
        ],
        "notes": """## Grammar: possessives and haben

| | masc. / neut. | fem. / plural |
| --- | --- | --- |
| my | mein | meine |
| your (du) | dein | deine |
| his / its | sein | seine |
| her / their | ihr | ihre |
| our | unser | unsere |
| your (polite) | Ihr | Ihre |

- Possessives take the endings of *ein*: *mein Vater* (der), *meine Mutter* (die), *meine Eltern* (plural).
- In the accusative masculine they add **-en**: *Ich besuche **meinen** Bruder.*
- **haben**: ich habe, du hast, er hat, wir haben, ihr habt, sie/Sie haben.""",
        "practice": [
            conj("haben", "Präsens (present)", [[p, f] for p, f in zip(PRONOUNS, ["habe", "hast", "hat", "haben", "habt", "haben"])]),
            blank("Das ist ___ Vater. (my)", ["mein", "meine", "meinen", "meinem"], "mein", "der Vater: **mein** Vater."),
            blank("Das sind ___ Eltern. (our)", ["unsere", "unser", "unseren", "unserem"], "unsere", "Plural: **unsere** Eltern."),
            blank("Ich besuche ___ Bruder. (my)", ["meinen", "mein", "meine", "meinem"], "meinen", "besuchen takes the accusative: der Bruder → **meinen** Bruder."),
        ],
    },
    {
        "id": "de-05-stadt", "title": "German 5: In the city — Dativ and prepositions", "level": "Beginner (A1)",
        "intro": "Find your way around town and use the dative after mit, zu, von, aus, bei, nach and neben (where something is).",
        "words": [
            W("Stadt", "city; town", "ʃtat", "f", "Städte", "Die Stadt ist schön."),
            W("Bahnhof", "train station", "ˈbaːnˌhoːf", "m", "Bahnhöfe", "Wo ist der Bahnhof?"),
            W("Straße", "street", "ˈʃtʁaːsə", "f", "Straßen", "Die Straße ist lang."),
            W("Museum", "museum", "muˈzeːʊm", "n", "Museen", "Das Museum ist heute offen."),
            W("Apotheke", "pharmacy", "apoˈteːkə", "f", "Apotheken", "Die Apotheke ist neben der Bank."),
            W("Supermarkt", "supermarket", "ˈzuːpɐˌmaʁkt", "m", "Supermärkte", "Wir gehen zum Supermarkt."),
            W("Kino", "cinema", "ˈkiːno", "n", "Kinos", "Das Kino ist neu."),
            W("Bank", "bank", "baŋk", "f", "Banken", "Die Bank ist geschlossen."),
            W("Bus", "bus", "bʊs", "m", "Busse", "Ich fahre mit dem Bus."),
            W("Park", "park", "paʁk", "m", "Parks", "Der Park ist groß."),
            W("links", "left", "lɪŋks", example="Gehen Sie nach links."),
            W("rechts", "right", "ʁɛçts", example="Die Bank ist rechts."),
            W("geradeaus", "straight ahead", "ɡəʁaːdəˈʔaʊ̯s", example="Gehen Sie geradeaus."),
        ],
        "phrases": [
            P("Wo ist der Bahnhof?", "Where is the train station?", [], ["die", "den", "Wohin"]),
            P("Ich fahre mit dem Bus.", "I am going by bus.", [], ["den", "der", "fährt"]),
            P("Die Apotheke ist neben der Bank.", "The pharmacy is next to the bank.", [], ["die", "den", "dem"]),
            P("Wir gehen zum Supermarkt.", "We are going to the supermarket.", [], ["zur", "in", "gehe"]),
            P("Nach dem Kino gehen wir nach Hause.", "After the cinema we are going home.", [], ["das", "den", "zu"]),
            P("Gehen Sie geradeaus und dann links.", "Go straight ahead and then left.", [], ["rechts", "Geht", "oder"]),
            P("Er kommt aus der Stadt.", "He is coming from the town.", [], ["die", "dem", "kommst"]),
        ],
        "notes": """## Grammar: the dative (Dativ)

After **aus, bei, mit, nach, seit, von, zu** the noun is always in the dative:

| | masculine | feminine | neuter | plural |
| --- | --- | --- | --- | --- |
| dative | **dem / einem** | **der / einer** | **dem / einem** | **den** (+ -n) |

- *mit dem Bus, mit der Bahn, mit dem Auto*.
- Short forms: **zum** = zu dem, **zur** = zu der, **vom** = von dem, **beim** = bei dem.
- **neben, vor, hinter, an, auf, in** take the dative when they say *where* something is: *neben **der** Bank*.
- *nach Hause* = (going) home; *zu Hause* = at home.""",
        "practice": [
            blank("Ich fahre mit ___ Bus.", ["dem", "den", "der", "des"], "dem", "mit + dative; der Bus → mit **dem** Bus."),
            blank("Die Bank ist neben ___ Kino.", ["dem", "das", "den", "der"], "dem", "Where? neben + dative; das Kino → neben **dem** Kino."),
            blank("Wir gehen ___ Apotheke.", ["zur", "zum", "nach", "in"], "zur", "zu + die Apotheke (dative der) → **zur** Apotheke."),
            blank("Er kommt aus ___ Schule.", ["der", "die", "dem", "den"], "der", "aus + dative; die Schule → aus **der** Schule."),
        ],
    },
    {
        "id": "de-06-alltag", "title": "German 6: Daily routine — separable verbs and time", "level": "Beginner (A1)",
        "intro": "Describe your day, tell the time, and send the prefix of separable verbs to the end of the sentence.",
        "words": [
            W("aufstehen", "to get up", "ˈaʊ̯fˌʃteːən", example="Ich stehe um sieben Uhr auf."),
            W("anrufen", "to call (on the phone)", "ˈanˌʁuːfn̩", example="Ich rufe dich morgen an."),
            W("einkaufen", "to go shopping", "ˈaɪ̯nˌkaʊ̯fn̩", example="Wir kaufen am Samstag ein."),
            W("fernsehen", "to watch TV", "ˈfɛʁnˌzeːən", example="Er sieht am Abend fern."),
            W("anfangen", "to begin", "ˈanˌfaŋən", example="Der Kurs fängt um neun Uhr an."),
            W("frühstücken", "to have breakfast", "ˈfʁyːˌʃtʏkn̩", example="Wir frühstücken um acht."),
            W("Uhr", "clock; o'clock", "uːɐ̯", "f", "Uhren", "Es ist acht Uhr."),
            W("Stunde", "hour", "ˈʃtʊndə", "f", "Stunden", "Der Film dauert zwei Stunden."),
            W("Minute", "minute", "miˈnuːtə", "f", "Minuten", "Ich komme in zehn Minuten."),
            W("Morgen", "morning", "ˈmɔʁɡn̩", "m", "Morgen", "Am Morgen trinke ich Kaffee."),
            W("Abend", "evening", "ˈaːbn̩t", "m", "Abende", "Am Abend lese ich."),
            W("Woche", "week", "ˈvɔxə", "f", "Wochen", "Die Woche hat sieben Tage."),
            W("heute", "today", "ˈhɔʏ̯tə", example="Heute ist Montag."),
            W("morgen", "tomorrow", "ˈmɔʁɡn̩", example="Morgen habe ich frei."),
        ],
        "phrases": [
            P("Ich stehe um sieben Uhr auf.", "I get up at seven o'clock.", [], ["aufstehe", "am", "steht"]),
            P("Wann fängt der Film an?", "When does the film start?", ["Wann beginnt der Film?"], ["anfängt", "den", "Wie"]),
            P("Am Abend sehe ich fern.", "In the evening I watch TV.", ["Ich sehe am Abend fern."], ["Im", "fernsehe", "sieht"]),
            P("Wie spät ist es?", "What time is it?", ["Wie viel Uhr ist es?"], ["Wann", "sind", "Uhr"]),
            P("Es ist halb acht.", "It is half past seven.", ["Es ist sieben Uhr dreißig."], ["sieben", "Uhr", "nach"]),
            P("Heute kaufe ich ein.", "Today I am going shopping.", ["Ich kaufe heute ein."], ["einkaufe", "kauft", "Morgen"]),
            P("Ruf mich morgen an!", "Call me tomorrow!", ["Ruf mich morgen an."], ["Rufst", "mir", "auf"]),
        ],
        "notes": """## Grammar: separable verbs and word order

- Separable verbs split: the prefix goes to the **end**. *aufstehen* → *Ich stehe um sieben Uhr **auf**.*
- In the infinitive (and after modal verbs) they stay together: *Ich muss früh **aufstehen**.*
- Not every prefix separates: *frühstücken* is a normal verb (*Ich frühstücke*).
- **The verb is always the second element.** If the sentence starts with a time, the subject moves after the verb:
  *Am Abend **sehe ich** fern.*

## Telling the time

- *Es ist acht Uhr* (8:00) · *Viertel nach acht* (8:15) · ***halb neun*** (8:30: half *to* nine) · *Viertel vor neun* (8:45).
- *um* + time = at: *um sieben Uhr*. *am* + part of the day: *am Morgen, am Abend*.""",
        "practice": [
            blank("Ich ___ um sieben Uhr auf.", ["stehe", "aufstehe", "steht", "stehen"], "stehe", "Separable: the verb part is conjugated, the prefix **auf** goes to the end."),
            blank("Der Unterricht fängt um neun Uhr ___.", ["an", "auf", "ein", "mit"], "an", "anfangen → *fängt … **an***."),
            blank("„Es ist halb neun“ means it is ___.", ["8:30", "9:30", "9:00", "8:00"], "8:30", "**halb neun** = half way to nine = 8:30."),
            blank("Am Abend ___ ich fern.", ["sehe", "fernsehe", "siehst", "sieht"], "sehe", "Time first, then the verb (position 2), then the subject: *Am Abend **sehe** ich fern.*"),
        ],
    },
    {
        "id": "de-07-hobbys", "title": "German 7: Hobbies and modal verbs", "level": "Beginner (A1-A2)",
        "intro": "Talk about what you like doing, and what you can, want, must or may do: modal verbs send the main verb to the end.",
        "words": [
            W("Hobby", "hobby", "ˈhɔbi", "n", "Hobbys", "Mein Hobby ist Lesen."),
            W("Sport", "sport", "ʃpɔʁt", "m", "", "Sport macht Spaß."),
            W("Musik", "music", "muˈziːk", "f", "", "Ich höre gern Musik."),
            W("Spiel", "game; match", "ʃpiːl", "n", "Spiele", "Das Spiel beginnt um acht."),
            W("Lied", "song", "liːt", "n", "Lieder", "Das Lied ist schön."),
            W("Gitarre", "guitar", "ɡiˈtaʁə", "f", "Gitarren", "Sie spielt Gitarre."),
            W("Fußball", "football (soccer)", "ˈfuːsˌbal", "m", "", "Wir spielen Fußball."),
            W("schwimmen", "to swim", "ˈʃvɪmən", example="Im Sommer schwimme ich viel."),
            W("spielen", "to play", "ˈʃpiːlən", example="Die Kinder spielen im Park."),
            W("können", "can; to be able to", "ˈkœnən", example="Ich kann gut kochen."),
            W("wollen", "to want to", "ˈvɔlən", example="Wir wollen ins Kino gehen."),
            W("müssen", "to have to; must", "ˈmʏsn̩", example="Du musst heute lernen."),
            W("dürfen", "to be allowed to; may", "ˈdʏʁfn̩", example="Hier darf man nicht rauchen."),
            W("gern", "gladly; (to like) doing", "ɡɛʁn", example="Ich lese gern."),
        ],
        "phrases": [
            P("Ich spiele gern Fußball.", "I like playing football.", [], ["spielt", "gerne", "Spiel"]),
            P("Kannst du schwimmen?", "Can you swim?", [], ["Kann", "schwimmst", "Können"]),
            P("Ich will Gitarre lernen.", "I want to learn the guitar.", ["Ich möchte Gitarre lernen."], ["lerne", "willst", "wollen"]),
            P("Wir müssen heute arbeiten.", "We have to work today.", ["Heute müssen wir arbeiten."], ["muss", "arbeitet", "müsst"]),
            P("Darf ich hier fotografieren?", "May I take photos here?", [], ["Darfst", "fotografiere", "dürfen"]),
            P("Am Wochenende hört sie Musik.", "At the weekend she listens to music.", ["Sie hört am Wochenende Musik."], ["hören", "hörst", "Im"]),
            P("Er kann sehr gut singen.", "He can sing very well.", [], ["singt", "können", "kannst"]),
        ],
        "notes": """## Grammar: modal verbs

| | können | wollen | müssen | dürfen |
| --- | --- | --- | --- | --- |
| ich | kann | will | muss | darf |
| du | kannst | willst | musst | darfst |
| er / sie / es | kann | will | muss | darf |
| wir | können | wollen | müssen | dürfen |
| ihr | könnt | wollt | müsst | dürft |
| sie / Sie | können | wollen | müssen | dürfen |

- The modal is in position 2; the main verb goes to the **end** in the infinitive: *Ich **kann** gut **schwimmen**.*
- *ich* and *er/sie/es* have the same form and no ending: *ich kann, er kann*.
- **gern** + verb = to like doing: *Ich spiele **gern** Fußball.*""",
        "practice": [
            conj("können", "Präsens (present)", [[p, f] for p, f in zip(PRONOUNS, ["kann", "kannst", "kann", "können", "könnt", "können"])]),
            blank("Ich ___ heute nicht kommen. (must)", ["muss", "müssen", "musst", "müsst"], "muss", "ich → **muss** (no ending)."),
            blank("Wir ___ ins Kino gehen. (want)", ["wollen", "will", "willst", "wollt"], "wollen", "wir → **wollen**."),
            blank("Ich kann gut ___.", ["schwimmen", "schwimme", "schwimmt", "schwimmst"], "schwimmen", "After a modal verb the main verb is an infinitive at the end."),
        ],
    },
    {
        "id": "de-08-wohnung", "title": "German 8: At home — two-way prepositions", "level": "Elementary (A2)",
        "intro": "Describe your flat and where things are. in, an, auf, unter, neben … take the dative for where (Wo?) and the accusative for where to (Wohin?).",
        "words": [
            W("Wohnung", "flat; apartment", "ˈvoːnʊŋ", "f", "Wohnungen", "Die Wohnung hat drei Zimmer."),
            W("Zimmer", "room", "ˈtsɪmɐ", "n", "Zimmer", "Das Zimmer ist hell."),
            W("Küche", "kitchen", "ˈkʏçə", "f", "Küchen", "Wir essen in der Küche."),
            W("Bad", "bathroom", "baːt", "n", "Bäder", "Das Bad ist klein."),
            W("Bett", "bed", "bɛt", "n", "Betten", "Das Bett ist bequem."),
            W("Sofa", "sofa", "ˈzoːfa", "n", "Sofas", "Die Katze liegt auf dem Sofa."),
            W("Schrank", "cupboard; wardrobe", "ʃʁaŋk", "m", "Schränke", "Die Teller sind im Schrank."),
            W("Regal", "shelf", "ʁeˈɡaːl", "n", "Regale", "Die Bücher stehen im Regal."),
            W("Wand", "wall", "vant", "f", "Wände", "Das Bild hängt an der Wand."),
            W("Boden", "floor", "ˈboːdn̩", "m", "Böden", "Die Tasche liegt auf dem Boden."),
            W("legen", "to lay; to put (flat)", "ˈleːɡn̩", example="Ich lege das Handy auf den Tisch."),
            W("liegen", "to lie; to be lying", "ˈliːɡn̩", example="Das Handy liegt auf dem Tisch."),
            W("stellen", "to put (upright)", "ˈʃtɛlən", example="Er stellt die Flasche in den Kühlschrank."),
            W("stehen", "to stand", "ˈʃteːən", example="Die Flasche steht im Kühlschrank."),
            W("hängen", "to hang", "ˈhɛŋən", example="Das Bild hängt an der Wand."),
        ],
        "phrases": [
            P("Das Buch liegt auf dem Tisch.", "The book is lying on the table.", ["Das Buch ist auf dem Tisch."], ["den", "legt", "der"]),
            P("Ich lege das Buch auf den Tisch.", "I am putting the book on the table.", [], ["dem", "liege", "die"]),
            P("Die Katze schläft unter dem Bett.", "The cat is sleeping under the bed.", [], ["den", "das", "schlaft"]),
            P("Er stellt die Lampe neben das Sofa.", "He puts the lamp next to the sofa.", [], ["dem", "steht", "der"]),
            P("Das Bild hängt an der Wand.", "The picture is hanging on the wall.", [], ["die", "den", "auf"]),
            P("Wir gehen in die Küche.", "We are going into the kitchen.", [], ["der", "im", "gehe"]),
            P("Die Milch steht im Kühlschrank.", "The milk is in the fridge.", ["Die Milch ist im Kühlschrank."], ["in", "stellt", "den"]),
        ],
        "notes": """## Grammar: two-way prepositions (Wechselpräpositionen)

**an, auf, hinter, in, neben, über, unter, vor, zwischen**

| Question | Case | Verbs | Example |
| --- | --- | --- | --- |
| **Wo?** (where: position) | dative | liegen, stehen, hängen, sein | *Das Buch liegt auf **dem** Tisch.* |
| **Wohin?** (where to: movement) | accusative | legen, stellen, hängen, gehen | *Ich lege das Buch auf **den** Tisch.* |

- Short forms: **im** = in dem, **ins** = in das, **am** = an dem, **ans** = an das.
- Pairs: *legen → liegen* (flat), *stellen → stehen* (upright), *hängen → hängen*.""",
        "practice": [
            blank("Der Schlüssel liegt auf ___ Tisch.", ["dem", "den", "der", "das"], "dem", "Wo? → dative: der Tisch → auf **dem** Tisch."),
            blank("Ich stelle die Vase auf ___ Regal.", ["das", "dem", "den", "der"], "das", "Wohin? → accusative: das Regal stays **das**."),
            blank("Wohin gehst du? – In ___ Küche.", ["die", "der", "dem", "den"], "die", "Wohin? → accusative: die Küche → in **die** Küche."),
            blank("Das Handy ___ auf dem Sofa.", ["liegt", "legt", "legen", "liegen"], "liegt", "Position (auf **dem** Sofa): **liegen**, er liegt."),
        ],
    },
    {
        "id": "de-09-perfekt", "title": "German 9: What happened? The Perfekt", "level": "Elementary (A2)",
        "intro": "Talk about the past the way Germans speak: haben or sein plus the past participle at the end.",
        "words": [
            W("gemacht", "done; made (machen)", "ɡəˈmaxt", example="Was hast du gemacht?"),
            W("gegessen", "eaten (essen)", "ɡəˈɡɛsn̩", example="Ich habe Pizza gegessen."),
            W("getrunken", "drunk (trinken)", "ɡəˈtʁʊŋkn̩", example="Er hat Tee getrunken."),
            W("gesehen", "seen (sehen)", "ɡəˈzeːən", example="Wir haben den Film gesehen."),
            W("gekauft", "bought (kaufen)", "ɡəˈkaʊ̯ft", example="Sie hat ein Kleid gekauft."),
            W("gearbeitet", "worked (arbeiten)", "ɡəˈʔaʁbaɪ̯tət", example="Ich habe lange gearbeitet."),
            W("gegangen", "gone; walked (gehen)", "ɡəˈɡaŋən", example="Wir sind nach Hause gegangen."),
            W("gefahren", "driven; travelled (fahren)", "ɡəˈfaːʁən", example="Sie ist nach Hamburg gefahren."),
            W("geschlafen", "slept (schlafen)", "ɡəˈʃlaːfn̩", example="Hast du gut geschlafen?"),
            W("aufgestanden", "got up (aufstehen)", "ˈaʊ̯fɡəˌʃtandn̩", example="Ich bin früh aufgestanden."),
            W("gestern", "yesterday", "ˈɡɛstɐn", example="Gestern war ich müde."),
            W("Wochenende", "weekend", "ˈvɔxn̩ˌʔɛndə", "n", "Wochenenden", "Am Wochenende habe ich gelesen."),
            W("Urlaub", "holiday; vacation", "ˈuːɐ̯ˌlaʊ̯p", "m", "Urlaube", "Im Urlaub sind wir geschwommen."),
        ],
        "phrases": [
            P("Ich habe gestern Pizza gegessen.", "I ate pizza yesterday.", ["Gestern habe ich Pizza gegessen."], ["bin", "esse", "gegesst"]),
            P("Wir sind nach Berlin gefahren.", "We travelled to Berlin.", [], ["haben", "gefahrt", "fahren"]),
            P("Hast du den Film gesehen?", "Have you seen the film?", ["Hast du den Film schon gesehen?"], ["Bist", "gesieht", "der"]),
            P("Sie ist um sechs Uhr aufgestanden.", "She got up at six o'clock.", [], ["hat", "aufgesteht", "steht"]),
            P("Am Wochenende habe ich viel gearbeitet.", "At the weekend I worked a lot.", ["Ich habe am Wochenende viel gearbeitet."], ["bin", "gearbeit", "Im"]),
            P("Er hat einen Kaffee getrunken.", "He drank a coffee.", [], ["ist", "getrinkt", "ein"]),
            P("Was hast du im Urlaub gemacht?", "What did you do on holiday?", [], ["bist", "gemachen", "machst"]),
        ],
        "notes": """## Grammar: the Perfekt (spoken past)

**haben / sein** in position 2 + **past participle at the end**: *Ich **habe** gestern Pizza **gegessen**.*

- Regular verbs: **ge-** + stem + **-t**: machen → *gemacht*, kaufen → *gekauft*, arbeiten → *gearbeitet*.
- Irregular verbs: **ge-** + (changed) stem + **-en**: essen → *gegessen*, trinken → *getrunken*, sehen → *gesehen*.
- Separable verbs put **-ge-** after the prefix: aufstehen → *auf**ge**standen*.
- **sein** with verbs of movement or change of state: *Ich **bin** gegangen, gefahren, aufgestanden.* Most other verbs take **haben**.""",
        "practice": [
            blank("Ich ___ nach Hause gegangen.", ["bin", "habe", "hat", "ist"], "bin", "gehen is movement: Perfekt with **sein**; ich → bin."),
            blank("Wir ___ ein Auto gekauft.", ["haben", "sind", "hat", "seid"], "haben", "kaufen takes **haben**; wir → haben."),
            blank("Hast du gut ___?", ["geschlafen", "geschlaft", "schlafen", "geschläft"], "geschlafen", "schlafen is irregular: **geschlafen**."),
            blank("Er ist um sieben Uhr ___.", ["aufgestanden", "aufgesteht", "aufstehen", "geaufstanden"], "aufgestanden", "Separable verb: auf + **ge** + standen."),
        ],
    },
    {
        "id": "de-10-weil-dass-wenn", "title": "German 10: weil, dass, wenn — linking ideas", "level": "Elementary (A2)",
        "intro": "Give reasons, report what you think, and set conditions. After weil, dass and wenn the verb goes to the end.",
        "words": [
            W("weil", "because", "vaɪ̯l", example="Ich lerne, weil ich eine Prüfung habe."),
            W("dass", "that (conjunction)", "das", example="Ich weiß, dass du recht hast."),
            W("wenn", "if; when(ever)", "vɛn", example="Wenn ich Zeit habe, lese ich."),
            W("aber", "but", "ˈaːbɐ", example="Ich bin müde, aber glücklich."),
            W("denn", "because (normal word order)", "dɛn", example="Ich gehe, denn es ist spät."),
            W("oder", "or", "ˈoːdɐ", example="Kaffee oder Tee?"),
            W("und", "and", "ʊnt", example="Anna und Paul sind Freunde."),
            W("glauben", "to believe; to think", "ˈɡlaʊ̯bn̩", example="Ich glaube, er kommt."),
            W("wissen", "to know (a fact)", "ˈvɪsn̩", example="Weißt du das?"),
            W("krank", "ill; sick", "kʁaŋk", example="Ich bin krank."),
            W("müde", "tired", "ˈmyːdə", example="Bist du müde?"),
            W("Wetter", "weather", "ˈvɛtɐ", "n", "", "Das Wetter ist schön."),
            W("Regen", "rain", "ˈʁeːɡn̩", "m", "", "Der Regen hört nicht auf."),
        ],
        "phrases": [
            P("Ich bleibe zu Hause, weil ich krank bin.", "I am staying at home because I am ill.", [], ["ist", "bist", "Haus"]),
            P("Ich glaube, dass er heute kommt.", "I think that he is coming today.", ["Ich glaube, er kommt heute."], ["kommen", "das", "kommst"]),
            P("Wenn es regnet, nehme ich den Bus.", "If it rains, I take the bus.", [], ["nimmt", "dem", "regnen"]),
            P("Ich bin müde, denn ich habe schlecht geschlafen.", "I am tired because I slept badly.",
              ["Ich bin müde, weil ich schlecht geschlafen habe."], ["bist", "geschlaft", "hat"]),
            P("Weißt du, dass Anna Geburtstag hat?", "Do you know that it is Anna's birthday?", [], ["Wisst", "das", "habe"]),
            P("Wir gehen spazieren, wenn das Wetter schön ist.", "We go for a walk when the weather is nice.", [], ["sind", "der", "gehst"]),
            P("Er lernt Deutsch, weil er in Berlin arbeiten will.", "He is learning German because he wants to work in Berlin.", [], ["willst", "wollen", "arbeitet"]),
        ],
        "notes": """## Grammar: subordinate clauses

After **weil** (because), **dass** (that) and **wenn** (if, when) the conjugated verb goes to the **end** of its clause:

- *Ich bleibe zu Hause, **weil** ich krank **bin**.*
- *Ich glaube, **dass** er heute **kommt**.*
- With a modal verb, the modal is last: *…, weil er in Berlin arbeiten **will**.*
- A clause first counts as position 1, so the main verb comes right after the comma: *Wenn es regnet, **nehme** ich den Bus.*
- **und, aber, oder, denn** do not change the word order: *…, **denn** ich **habe** schlecht geschlafen.*
- *dass* (conjunction) has two s; *das* is the article or "that" as a pronoun.""",
        "practice": [
            blank("Ich komme nicht, weil ich keine Zeit ___.", ["habe", "hast", "haben", "hat"], "habe", "After **weil** the verb goes to the end: … weil ich keine Zeit **habe**."),
            blank("Ich weiß, ___ du recht hast.", ["dass", "das", "weil", "wenn"], "dass", "The conjunction *that* is **dass** (two s)."),
            blank("___ ich Zeit habe, komme ich.", ["Wenn", "Denn", "Aber", "Oder"], "Wenn", "**Wenn** starts a subordinate clause; denn, aber and oder cannot."),
            blank("Ich bin müde, denn ich ___ schlecht geschlafen.", ["habe", "hat", "bin", "ist"], "habe", "**denn** keeps normal word order: *ich habe … geschlafen*."),
        ],
    },
]


def unit_topics():
    """Every unit as topic JSON (practice not yet normalized). Units are numbered on the Learn path via source.classSeq."""
    out = []
    for n, unit in enumerate(UNITS, 1):
        a = {**unit, "lang": LANG, "category": "Languages · German",
             "source": {"workspace": "language", "lang": LANG, "courseTitle": COURSE_TITLE, "classSeq": n,
                        "classTotal": len(UNITS), "builtin": "de"}}
        out.append(mcp_tools_language.unit_topic(a))
    return out


def seed(*, save, exists, normalize_practice):
    """Saves every unit whose id is not taken yet. save(topic) persists one topic (through the server's normalizer);
    exists(id) says whether a topic file is there; normalize_practice gives items their ids and drops invalid ones.
    Returns {created: [ids], skipped: [ids], dropped: {id: count}}."""
    created, skipped, dropped = [], [], {}
    for topic in unit_topics():
        if exists(topic["id"]):
            skipped.append(topic["id"])
            continue
        items = normalize_practice(topic["practice"])
        if len(items) != len(topic["practice"]):
            dropped[topic["id"]] = len(topic["practice"]) - len(items)
        save({**topic, "practice": items})
        created.append(topic["id"])
    return {"created": created, "skipped": skipped, "dropped": dropped}
