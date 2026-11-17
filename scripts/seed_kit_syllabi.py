#!/usr/bin/env python3
"""
Sample library lessons for the six liberal-arts kits: literature, art_history, music, classics, rhetoric, polity.
Four classes per kit (24 lessons), class 1 the basics, class 4 the hardest. Nothing here calls a model.

    python3 scripts/seed_kit_syllabi.py --dry-run   # normalize every lesson offline against a throwaway data folder; writes nothing
    python3 scripts/seed_kit_syllabi.py             # POST each lesson to the running backend (ANDEDU_API, default 127.0.0.1:8090)

With accounts on, set ANDEDU_TOKEN to an admin session token. The lessons are library topics with ids
kit-<kit-with-dashes>-class-<1..4>; running it again updates them in place. Practice answer keys are computed or
checked by the server from the fields written here. Quoted literary passages are public domain (before 1900) and short.
"""
import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = os.environ.get("ANDEDU_API", "http://127.0.0.1:8090").rstrip("/")
TOKEN = os.environ.get("ANDEDU_TOKEN", "")

# kit -> (workspace the lessons open in = the kit's mode id, category, course name)
KIT_META = {
    "literature": ("literature", "Literature", "Literature"),
    "art_history": ("art_history", "Art history", "Art history"),
    "music": ("music", "Music", "Music theory"),
    "classics": ("classics", "Classics", "Classics"),
    "rhetoric": ("rhetoric", "Rhetoric", "Rhetoric"),
    "polity": ("polity", "Political science", "Political science"),
}
DIFFICULTY = {1: "Introductory", 2: "Introductory", 3: "Intermediate", 4: "Advanced"}


def q(question, options, correct, hint, explanation):
    return {"question": question, "options": options, "correctAnswer": correct, "hint": hint, "explanation": explanation}


def cs(label, formula):
    return {"label": label, "formula": formula}


_WORDSWORTH = [
    "The world is too much with us; late and soon,", "Getting and spending, we lay waste our powers;",
    "Little we see in Nature that is ours;", "We have given our hearts away, a sordid boon!",
    "This Sea that bares her bosom to the moon,", "The winds that will be howling at all hours,",
    "And are up-gathered now like sleeping flowers,", "For this, for everything, we are out of tune;",
    "It moves us not.—Great God! I'd rather be", "A Pagan suckled in a creed outworn;",
    "So might I, standing on this pleasant lea,", "Have glimpses that would make me less forlorn;",
    "Have sight of Proteus rising from the sea;", "Or hear old Triton blow his wreathed horn.",
]

# ---------------------------------------------------------------------------------------------------------------
# Literature
# ---------------------------------------------------------------------------------------------------------------
LITERATURE = [
    {
        "title": "Reading a poem closely: stress, meter and rhyme",
        "summary": "Hear the beat of a line, name its meter and label its end rhymes.",
        "md": """# Reading a poem closely

A poem is made of sound as much as sense. Before you ask what a poem means, listen to how it moves. Three tools
give you a first, reliable grip: stress, meter and rhyme.

## Syllables and stress

Every English word of more than one syllable has a natural stress. In *water* the first syllable is heavy and the
second light; in *delay* it is the other way round. We mark a stressed syllable with 1 and an unstressed one with 0.
Say a line aloud, exaggerate the beat, and write the pattern down.

## Feet and meter

Poets group syllables into small units called **feet**. The commonest foot in English is the **iamb**: an unstressed
syllable followed by a stressed one (0 1), as in *de-LAY* or *the TIME*. Other feet include the trochee (1 0), the
dactyl (1 0 0), the anapest (0 0 1) and the spondee (1 1). The **meter** of a line names the foot and the number of
feet: one foot is a monometer, two a dimeter, three a trimeter, four a tetrameter, five a pentameter.

Iambic pentameter is therefore five iambs, ten syllables, in the rhythm da-DUM da-DUM da-DUM da-DUM da-DUM. It is
the line of Shakespeare's sonnets, and it sits close to the rhythm of natural English speech. Here is the opening of
Sonnet 12:

> When I do count the clock that tells the time,

Read it with the beat and the pattern appears: when (0) I (1) do (0) count (1) the (0) clock (1) that (0) tells (1)
the (0) time (1). Ten syllables, five iambs. Real poets vary the pattern now and then, which keeps the verse alive,
so treat the pattern as a norm against which variations stand out.

## Rhyme and rhyme scheme

Rhyme repeats the final sounds of words, usually at the ends of lines. To describe the pattern, give the first
line-ending sound the letter A. Each new sound gets the next letter, and a repeated sound reuses its letter. The
opening stanza of Thomas Gray's "Elegy Written in a Country Churchyard" (1751) ends its lines with *day*, *lea*,
*way* and *me*. Lines 1 and 3 share a sound and lines 2 and 4 share another, so the scheme is ABAB.

Rhyme is judged by sound, not spelling. *Day* and *way* rhyme although they begin differently, while a pair such as
*love* and *prove* only looks as if it should.

## A close-reading routine

1. Read the poem aloud twice, once for sense and once for rhythm.
2. Mark the stresses on one or two lines and name the meter.
3. Label the rhyme scheme of the first stanza.
4. Notice where the pattern breaks. A broken pattern is usually a signal: the poet wants you to slow down or look again.

Practice on short passages first. Soon you will hear the beat before you mark it.
""",
        "cheat": [cs("Iamb", r"0\;1 \quad (\text{da-DUM})"), cs("Pentameter", r"5 \text{ feet} = 10 \text{ syllables (iambic)}"),
                  cs("Rhyme letters", r"\text{ABAB: lines 1 and 3 rhyme; lines 2 and 4 rhyme}")],
        "quiz": [
            q("How many feet does a line of pentameter have?", ["Four", "Five", "Six", "Eight"], 1,
              "Penta- means five.", "Pentameter has five feet; in iambic pentameter that gives ten syllables."),
            q("Which pattern describes an iamb?", ["Stressed then unstressed", "Unstressed then stressed", "Two stressed syllables", "Two unstressed then one stressed"], 1,
              "Think of the word delay.", "An iamb is unstressed then stressed (0 1), as in de-LAY."),
            q("In the scheme ABAB, which lines rhyme with each other?", ["Lines 1 and 2", "Lines 1 and 3, and lines 2 and 4", "Lines 1 and 4", "All four lines"], 1,
              "Same letter, same sound.", "Both A lines rhyme (1 and 3) and both B lines rhyme (2 and 4)."),
        ],
        "practice": [
            {"type": "scansion", "prompt": "Mark each syllable of the line: 1 for stressed, 0 for unstressed.",
             "line": "When I do count the clock that tells the time", "meter": "iambic pentameter",
             "stress_pattern": "0 1 0 1 0 1 0 1 0 1", "explanation": "Five iambs make ten syllables; the beat falls on I, count, clock, tells and time."},
            {"type": "rhyme_scheme_audit", "prompt": "Give the end-rhyme scheme of this stanza from Gray's Elegy (one letter per line).",
             "lines": ["The curfew tolls the knell of parting day,", "The lowing herd wind slowly o'er the lea,",
                       "The plowman homeward plods his weary way,", "And leaves the world to darkness and to me."],
             "rhyme_scheme": "A B A B", "explanation": "Day and way rhyme (A); lea and me rhyme (B)."},
        ],
    },
    {
        "title": "The sonnet and its turn",
        "summary": "Compare Petrarchan and Shakespearean sonnets and find the volta, the turn of thought.",
        "md": """# The sonnet and its turn

The sonnet is a fourteen-line poem, usually in iambic pentameter, with a fixed rhyme scheme. It came into English from
Italian in the sixteenth century, and its compact size is the point: fourteen lines are enough to state a problem,
complicate it and answer it. Two forms matter most.

## The Petrarchan sonnet

Named after the Italian poet Petrarch, this form has two parts. The **octave** (eight lines) rhymes ABBAABBA. The
**sestet** (six lines) follows with a new pattern, often CDECDE or CDCDCD. The octave sets up a situation or
complaint, and the sestet answers or reflects on it.

## The Shakespearean sonnet

The English form uses three quatrains and a final couplet: ABAB CDCD EFEF GG. Each quatrain can develop a new image or
step in the argument, and the couplet delivers a summary or a surprise. Shakespeare published his 154 sonnets in 1609.

## The volta

In both forms the poem usually pivots at a point called the **volta**, Italian for "turn". In a Petrarchan sonnet
the turn normally comes at line 9, where the sestet begins. In a Shakespearean sonnet it often falls at line 9 as
well, or at the couplet in line 13. Signals include words such as *but*, *yet*, *so* and *then*, a change of
addressee, a shift of tense or a change in tone from complaint to hope.

## An example

William Wordsworth's "The world is too much with us" (1807) is a Petrarchan sonnet. Its octave complains that people
spend their lives "getting and spending" and have lost touch with nature: the sea, the winds, the whole natural
world leave them unmoved. Line 8 ends on the sentence "we are out of tune". Then line 9 begins:

> It moves us not.—Great God! I'd rather be
> A Pagan suckled in a creed outworn;

The mood changes at once. The speaker stops describing and starts wishing, and he turns to address God. This is the
volta. The sestet that follows rhymes CDCDCD (*be*, *outworn*, *lea*, *forlorn*, *sea*, *horn*), a pattern entirely
different from the octave's ABBAABBA.

## How to find a turn

Read the poem once for its main claim. Then ask where the claim is qualified, reversed or answered. Mark the line
where the grammar, the imagery or the mood changes most strongly. Check it against the rhyme scheme, since the
sound pattern often changes at the same place. Remember that critics sometimes argue over the exact line, so
support your choice with evidence from the text.
""",
        "cheat": [cs("Petrarchan", r"8 + 6 \text{ lines: ABBAABBA, then CDECDE or CDCDCD}"), cs("Shakespearean", r"4 + 4 + 4 + 2 \text{ lines: ABAB CDCD EFEF GG}"),
                  cs("Volta", r"\text{the turn, usually at line 9 (or line 13)}")],
        "quiz": [
            q("How many lines does a sonnet have?", ["Ten", "Twelve", "Fourteen", "Sixteen"], 2,
              "Octave plus sestet is 8 + 6.", "Both the Petrarchan and Shakespearean forms have fourteen lines."),
            q("How does a Shakespearean sonnet normally end?", ["With a sestet", "With a rhyming couplet", "With a single unrhymed line", "With a refrain"], 1,
              "The scheme ends GG.", "The final two lines rhyme as a couplet (GG)."),
            q("What is the volta?", ["The title of a sonnet", "The final rhyme", "The turn of thought or mood", "A foot of three syllables"], 2,
              "It is Italian for a turn.", "The volta is the pivot where the poem changes direction."),
        ],
        "practice": [
            {"type": "volta_spot", "prompt": "Which line of Wordsworth's sonnet (0 is the first) is the turn?", "lines": _WORDSWORTH,
             "target_index": 8, "explanation": "Line 9 (index 8), \"It moves us not\", ends the complaint and begins the wish."},
            {"type": "rhyme_scheme_audit", "prompt": "Give the rhyme scheme of the sestet (lines 9 to 14), one letter per line, starting at A.",
             "lines": _WORDSWORTH[8:], "rhyme_scheme": "A B A B A B",
             "explanation": "Be, lea and sea rhyme (A); outworn, forlorn and horn rhyme (B)."},
        ],
    },
    {
        "title": "Telling time: story order and plot order",
        "summary": "Separate the order events happened in from the order a narrator tells them.",
        "md": """# Telling time: story order and plot order

Stories rarely tell events in the order they happened. A narrator can open at the end, interrupt a scene with a
memory, or hint at what is coming. To read narrative well, learn to keep two orders apart.

## Fabula and syuzhet

Russian Formalist critics of the 1920s distinguished the **fabula** (the story: events in the order they happened)
from the **syuzhet** (the plot: events in the order the text presents them). A detective novel is the plain
example. The crime happened first in the fabula, but the book may reveal it last in the syuzhet.

## Tools that reorder time

- **Analepsis** (flashback): the narrative jumps back to an earlier event.
- **Prolepsis** (flash-forward): it jumps ahead, as when a narrator says "she would regret it".
- **In medias res** ("into the middle of things"): the text starts partway through the action. The Latin phrase comes from Horace, who praised Homer for it. The *Iliad* opens in the tenth year of the Trojan War, not at its beginning.
- **Ellipsis**: stretches of time are skipped entirely.

Reordering is never random. A flashback can explain a character's choice, delay a revelation or create suspense.

## Example: Dickens

Charles Dickens begins *A Christmas Carol* (1843) with the blunt sentence "Marley was dead: to begin with." The
syuzhet starts on Christmas Eve, a few hours before the ghost appears, and tells us that Marley died seven years
earlier. Later the Ghost of Christmas Past takes Scrooge back to his lonely schooldays and to the warm workshop of
his employer Fezziwig. So the order in which we learn about Scrooge's life is scrambled; the fabula runs from
schooldays to apprenticeship to Marley's death, to the refused invitation and finally to the transformed Scrooge
sending the prize turkey on Christmas morning.

## Reconstructing the fabula

1. List every event the text mentions, with the place where it appears.
2. Look for time markers: dates, "years earlier", tenses, seasons.
3. Use cause and effect. A cause comes before its effect, so a marriage precedes the quarrel it provokes.
4. Put the events in order and check the result against the text.

## Why the difference matters

When you compare fabula and syuzhet you can see what the author withholds and when. Ask what a reader knows at each
point, and how the order shapes sympathy, suspense and irony. Shakespeare's *Romeo and Juliet* is told mostly in
chronological order, which is why its tragedy feels like a chain of events that nobody can stop. Try rebuilding the
chain below.
""",
        "cheat": [cs("Fabula", r"\text{events in the order they happened}"), cs("Syuzhet", r"\text{events in the order the text tells them}"),
                  cs("In medias res", r"\text{begin in the middle of the action}")],
        "quiz": [
            q("What does fabula mean in narrative theory?", ["The order events are told", "The order events happened", "The narrator's voice", "The moral of the story"], 1,
              "Fabula = story; syuzhet = plot.", "The fabula is the chronological sequence of events; the syuzhet is the order of telling."),
            q("A flashback is technically called:", ["Prolepsis", "Ellipsis", "Analepsis", "Apostrophe"], 2,
              "Ana- means back.", "Analepsis jumps back to an earlier time; prolepsis jumps forward."),
            q("In which ancient poem does the action begin in medias res, in the tenth year of the war?", ["The Iliad", "Genesis", "The Canterbury Tales", "Pride and Prejudice"], 0,
              "Think of Troy.", "The Iliad opens in the tenth year of the Trojan War with the quarrel of Achilles and Agamemnon."),
        ],
        "practice": [
            {"type": "chronology_unravel", "prompt": "Put the events of Romeo and Juliet in the order they happened.",
             "events": [{"id": "e4", "text": "Juliet drinks the Friar's potion and seems to die."},
                        {"id": "e1", "text": "Romeo and Juliet meet at the Capulets' feast."},
                        {"id": "e6", "text": "Juliet wakes and kills herself."},
                        {"id": "e3", "text": "Romeo kills Tybalt and is banished from Verona."},
                        {"id": "e2", "text": "Friar Laurence secretly marries Romeo and Juliet."},
                        {"id": "e5", "text": "Romeo drinks poison in the tomb."}],
             "canonical_order": ["e1", "e2", "e3", "e4", "e5", "e6"],
             "explanation": "They meet, marry in secret, Romeo kills Tybalt, the potion follows, then the two deaths."},
            {"type": "chronology_unravel", "prompt": "Put the events of Scrooge's life in the order they happened (not the order Dickens tells them).",
             "events": [{"id": "s1", "text": "Scrooge refuses his nephew's invitation to Christmas dinner."},
                        {"id": "s3", "text": "The boy Scrooge is left alone at school at Christmas."},
                        {"id": "s5", "text": "Scrooge wakes and sends the prize turkey to the Cratchits."},
                        {"id": "s2", "text": "Jacob Marley dies."},
                        {"id": "s4", "text": "Scrooge is apprenticed to Mr Fezziwig."}],
             "canonical_order": ["s3", "s4", "s2", "s1", "s5"],
             "explanation": "Schooldays, apprenticeship, Marley's death seven years before the story, the refused invitation, then the turkey."},
        ],
    },
    {
        "title": "Sound and shape: meter that bends",
        "summary": "Scan a trochaic line, spot a truncated foot and read rhyme in a short triplet.",
        "md": """# Sound and shape: meter that bends

Once you can scan a regular iambic line, the interesting work begins: noticing where the rules bend and what the
bend does. This class looks at a different foot, at lines that stop short, and at stanzas shorter than a quatrain.

## Trochaic meter

A **trochee** reverses the iamb: stressed then unstressed (1 0). Trochaic verse sounds more urgent and incantatory,
and English uses it for chants, spells and nursery rhymes. William Blake opens "The Tyger" (1794) with

> Tyger Tyger, burning bright

Scan it: Ty (1) ger (0) Ty (1) ger (0) burn (1) ing (0) bright (1). That is seven syllables, three and a half
trochees. The last foot is missing its unstressed syllable. A line that stops early in this way is called
**catalectic**, and the line is trochaic tetrameter, catalectic. The sudden stop on a stressed syllable makes the
line hit like a hammer, which suits Blake's image of a forge.

## Substitution and variation

Poets often replace one expected foot with another. A common move is the trochaic substitution at the start of an
iambic line, which gives the line an energetic opening. Another is a **spondee**, two stressed syllables in a row,
which slows the line down. These variations are expressive. When a line changes its rhythm, ask what the change
emphasizes.

## Lines that run on

Two further terms describe how sentences meet line endings.

- **Caesura**: a pause inside a line, often marked by punctuation.
- **Enjambment**: a sentence runs over the end of a line without a pause, so the reader's momentum carries into the next line.

A line that ends with a full stop or comma is called end-stopped. A poem that mixes the two creates a pattern of
tension and rest.

## Short stanzas

Not every stanza has four lines. A **couplet** has two, a **tercet** three and a **triplet** is a tercet with a
single rhyme throughout (AAA). Alfred Tennyson's "The Eagle" (1851) is a six-line poem in two triplets. Its first
reads:

> He clasps the crag with crooked hands;
> Close to the sun in lonely lands,
> Ring'd with the azure world, he stands.

The ends *hands*, *lands* and *stands* give the scheme AAA. The heavy, repeated rhyme feels like the eagle's grip on
the rock. Notice also how the stressed words (*clasps*, *crag*, *crooked*) stack up with hard consonants.

## Putting it together

When you analyse a poem, work in this order: scan one line, name the meter and any variation, label the rhyme
scheme, then ask how sound and sense work together. The best answers always link a technical observation to an
effect on meaning.
""",
        "cheat": [cs("Trochee", r"1\;0"), cs("Dactyl / anapest", r"1\;0\;0 \quad / \quad 0\;0\;1"), cs("Catalectic", r"\text{a line missing its final unstressed syllable}")],
        "quiz": [
            q("A trochee is:", ["Unstressed then stressed", "Stressed then unstressed", "Three stressed syllables", "Two unstressed syllables"], 1,
              "It reverses the iamb.", "A trochee is stressed then unstressed (1 0)."),
            q("What is enjambment?", ["A pause in the middle of a line", "A sentence running over the end of a line", "A repeated first word", "A line of ten syllables"], 1,
              "The sense carries on past the line break.", "In enjambment the sentence continues into the next line without a pause."),
            q("A tercet with one rhyme sound throughout has the scheme:", ["ABA", "ABB", "AAA", "ABC"], 2,
              "One sound, one letter.", "A triplet repeats the same rhyme in all three lines: AAA."),
        ],
        "practice": [
            {"type": "scansion", "prompt": "Mark each syllable of Blake's line: 1 for stressed, 0 for unstressed.",
             "line": "Tyger Tyger, burning bright", "meter": "trochaic tetrameter (catalectic)",
             "stress_pattern": "1 0 1 0 1 0 1", "explanation": "Three trochees and a final stressed syllable: seven syllables."},
            {"type": "rhyme_scheme_audit", "prompt": "Give the rhyme scheme of this triplet (one letter per line).",
             "lines": ["He clasps the crag with crooked hands;", "Close to the sun in lonely lands,", "Ring'd with the azure world, he stands."],
             "rhyme_scheme": "A A A", "explanation": "Hands, lands and stands all share one rhyme."},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------
# Art history
# ---------------------------------------------------------------------------------------------------------------
ART_HISTORY = [
    {
        "title": "Looking closely: formal analysis and style",
        "summary": "Describe line, colour and composition, then name a style from what you see.",
        "md": """# Looking closely: formal analysis and style

Art history starts with careful looking. Before you ask who made a work or what it means, describe what is in front
of you in plain terms. This method is called **formal analysis**, and it gives you evidence to support every later
claim.

## The elements

- **Line**: edges and contours; straight or curved, thick or thin, sharp or soft.
- **Shape and form**: flat outlines (shape) and the illusion of volume (form).
- **Colour**: described by hue (the colour name), value (how light or dark) and saturation (how intense).
- **Texture**: real surface (thick paint, rough stone) or implied texture.
- **Space**: the depth of the scene, from shallow to deep. **Linear perspective**, developed in fifteenth-century Florence, uses lines converging at a vanishing point to create convincing depth.

## Composition

Composition is how the elements are arranged. Ask where your eye goes first. That spot is the **focal point**. See
whether the design is symmetrical or balanced off-centre, whether strong diagonals create movement, and whether the
frame is crowded or open. A calm, stable image often uses horizontals and verticals; a dynamic one uses diagonals.

## From description to style

A **style** is a recognisable set of choices shared by artists of a time or place. You identify a style by
matching traits. Three examples:

- **Renaissance** (Italy, fourteenth to sixteenth century): linear perspective, balanced and symmetrical compositions, idealised bodies based on anatomical study, and a revival of Greek and Roman models.
- **Baroque** (seventeenth century): strong contrasts of light and dark, diagonals, movement and heightened emotion.
- **Impressionism** (France, from the 1870s): loose, visible brushstrokes, the changing effects of natural light, and everyday modern scenes often painted outdoors. The name comes from a critic's mocking reaction to Claude Monet's *Impression, Sunrise*, shown in 1874.

## A routine for any image

1. Describe first: subject, medium and size if known, and the elements above.
2. Find the focal point and explain how the composition leads you to it.
3. List the traits that suggest a style or period.
4. Only then interpret: what might the choices be saying?

Keep description and interpretation apart. "The figure is placed off-centre in a dark room" is a description; "the
artist wants us to feel isolated" is an interpretation that needs the description as its support.

Use specific words. Instead of "nice colours", write "warm, saturated reds against cool blue shadows". Precision is
what turns an impression into an argument.
""",
        "cheat": [cs("Colour", r"\text{hue} + \text{value} + \text{saturation}"), cs("Focal point", r"\text{where the eye lands first}"),
                  cs("Style", r"\text{a set of shared traits} \Rightarrow \text{a period or movement}")],
        "quiz": [
            q("In describing colour, what does value mean?", ["How intense it is", "Its name", "How light or dark it is", "How expensive the pigment was"], 2,
              "Think of light and dark.", "Value is lightness or darkness; saturation is intensity and hue is the colour's name."),
            q("What does linear perspective use to create depth?", ["Lines converging at a vanishing point", "Thick brushstrokes", "Gold backgrounds", "Symmetry"], 0,
              "Think of railway lines meeting on the horizon.", "Linear perspective draws parallel lines converging at a vanishing point."),
            q("The Impressionists' first group exhibition took place in Paris in:", ["1774", "1824", "1874", "1924"], 2,
              "Monet's Impression, Sunrise was shown there.", "The first Impressionist exhibition was in 1874."),
        ],
        "practice": [
            {"type": "stylistic_taxonomy", "prompt": "Which period do these traits point to?",
             "traits": ["linear perspective creating deep space", "balanced, symmetrical composition", "idealised bodies based on anatomical study",
                        "revival of Greek and Roman models"],
             "period": "Renaissance", "options": ["Gothic", "Renaissance", "Baroque", "Impressionism"],
             "explanation": "Perspective, balance and a revival of classical models mark the Renaissance."},
            {"type": "stylistic_taxonomy", "prompt": "Which movement do these traits point to?",
             "traits": ["loose, visible brushstrokes", "the changing effects of natural light", "everyday scenes painted outdoors"],
             "period": "Impressionism", "options": ["Impressionism", "Neoclassicism", "Baroque", "Renaissance"],
             "explanation": "Broken brushwork and the study of light are the hallmarks of Impressionism."},
        ],
    },
    {
        "title": "Architecture vocabulary: orders, arches and vaults",
        "summary": "Name the Greek orders and the parts of a Gothic cathedral.",
        "md": """# Architecture vocabulary: orders, arches and vaults

Buildings have their own vocabulary, and using it correctly is the quickest way to sound precise in an essay. This
class covers two systems: the Greek orders and the structure of a Gothic cathedral.

## The Greek orders

An **order** is a complete system of column and the beam it carries. The column has a shaft, a capital on top, and
sometimes a base. The beam above is the entablature. The three Greek orders differ most clearly in their capitals.

- **Doric**: the sturdiest and simplest. A plain, cushion-like capital, and the shaft stands directly on the platform with no base. The Parthenon in Athens, built in the fifth century BCE, has Doric columns.
- **Ionic**: slimmer and more elegant, with a capital that ends in two scrolls called **volutes**. The small Temple of Athena Nike on the Athenian Acropolis is Ionic.
- **Corinthian**: the most ornate, with a capital of stylised acanthus leaves. The huge Temple of Olympian Zeus in Athens is Corinthian, although it was finished by the Roman emperor Hadrian.

Roman architects used all three and added their own variants, but the Greek names remain the basic tools.

## Arches, vaults and domes

An **arch** spans an opening with wedge-shaped stones that press against each other. Extend an arch in depth and you
have a **barrel vault**. Cross two barrel vaults and you get a **groin vault**. Rotate an arch around a centre and you
get a **dome**. Roman engineers perfected these forms in concrete, and the Pantheon in Rome still holds one of the
largest unreinforced concrete domes ever built.

## The Gothic cathedral

Gothic architecture began in northern France in the twelfth century. Its builders wanted height and light, and a
few connected inventions made that possible.

- **Pointed arch**: ends in a point, directs weight more steeply downward and can be built to different heights.
- **Rib vault**: a ceiling supported by a skeleton of crossing stone ribs, so the panels between them can be thinner.
- **Flying buttress**: an external half-arch that carries the sideways thrust of the vault to a pier outside the wall.
- **Rose window**: a large circular window filled with stone tracery and stained glass.

Because the buttresses took the load, the walls no longer had to be solid. They could be filled with glass, which
turned the interior into a space of coloured light.

## How to use the vocabulary

When you write about a building, begin with the overall form, then name the system that holds it up, and then the
decoration. State the term and the visible evidence together: "The Ionic order is recognisable by the paired
volutes of its capitals." A term without evidence is just a label.
""",
        "cheat": [cs("Doric", r"\text{plain capital, no base}"), cs("Ionic", r"\text{capital with paired volutes (scrolls)}"),
                  cs("Corinthian", r"\text{capital of acanthus leaves}")],
        "quiz": [
            q("Which Greek order has a capital with scrolls (volutes)?", ["Doric", "Ionic", "Corinthian", "Tuscan"], 1,
              "The name starts with an I.", "The Ionic capital has two volutes."),
            q("What does a flying buttress do?", ["Lights the nave", "Carries the vault's sideways thrust outside the wall", "Supports a dome from within", "Decorates the porch"], 1,
              "It is an external half-arch.", "It transfers the outward thrust of the vault to a pier outside the wall."),
            q("Gothic architecture first appeared in which region?", ["Northern France", "Southern Spain", "Greece", "Egypt"], 0,
              "Think of the twelfth century and Paris.", "Gothic began in northern France in the twelfth century."),
        ],
        "practice": [
            {"type": "label_architecture", "prompt": "Match each Athenian temple to the Greek order of its columns.",
             "solution": {"Parthenon": "Doric", "Temple of Athena Nike": "Ionic", "Temple of Olympian Zeus": "Corinthian"},
             "explanation": "The Parthenon is Doric, the Nike temple Ionic and the Olympian Zeus temple Corinthian."},
            {"type": "label_architecture", "prompt": "Match each description to the Gothic structural element.",
             "solution": {"external half-arch carrying the thrust of the vault": "flying buttress", "ceiling supported by crossing stone ribs": "rib vault",
                          "large circular stained-glass window": "rose window", "arch that ends in a point": "pointed arch"},
             "explanation": "These four elements together made tall, light-filled Gothic interiors possible."},
        ],
    },
    {
        "title": "Symbols and iconography",
        "summary": "Decode the attributes that identify saints and gods in images.",
        "md": """# Symbols and iconography

Much of the art made before the modern era was made for viewers who were expected to recognise the subject at a
glance. Artists did not label figures with names; they gave each one a recognisable object or animal called an
**attribute**. **Iconography** is the study of these subjects and symbols, and learning a handful of attributes
unlocks a large part of European art.

## How attributes work

An attribute usually refers to the story or legend of the figure: the instrument of martyrdom, a tool of the
trade, a miracle, or an animal companion. Because many figures look alike (a young man in a robe, a woman with a
book), the attribute is the key to identification. The same figure may carry different attributes in different
periods, but a few are remarkably stable.

## Christian saints

- **Saint Peter** carries one or two keys, from Christ's promise to give him the keys of the kingdom of heaven.
- **Saint Catherine of Alexandria** stands beside a spiked wheel, the instrument of her intended execution.
- **Saint Lawrence** holds a gridiron, the instrument of his martyrdom.
- **Saint Sebastian** is shown tied to a post or tree and pierced by arrows.

Painters also use colour symbolism: the Virgin Mary is often in blue, and a lily commonly signals her purity.

## Greek and Roman gods

Classical art taught Renaissance and later artists a standard code.

- **Zeus** (Roman Jupiter) holds a thunderbolt.
- **Poseidon** (Neptune) holds a trident, a three-pronged spear.
- **Hermes** (Mercury) carries the caduceus, a staff with two intertwined snakes, and often wears winged sandals.
- **Athena** (Minerva) wears a helmet and is accompanied by an owl, a symbol of wisdom.

## Reading an image

1. Identify the figures using their attributes.
2. Work out which story or scene the combination describes. Two figures with their attributes may be meeting in a known episode.
3. Ask why this moment was chosen and who commissioned it.
4. Look for symbols that add a layer of meaning, such as a skull for the shortness of life, or a lamb for sacrifice.

## Cautions

Not every object is a symbol. Some are just objects. And an attribute can be shared: a lion appears with Saint
Mark and with Saint Jerome, so you must check the whole picture. If an attribute is ambiguous, use context such as
the setting, the other figures and the dedication of the building.

Iconography is a form of detective work. The more attributes you know, the faster the clues add up.
""",
        "cheat": [cs("Saint Peter", r"\text{keys}"), cs("Zeus / Poseidon", r"\text{thunderbolt / trident}"), cs("Athena", r"\text{helmet and owl}")],
        "quiz": [
            q("What is an attribute in iconography?", ["A flaw in a painting", "An object or animal that identifies a figure", "A type of frame", "A painter's signature"], 1,
              "It is how you tell figures apart.", "An attribute is an identifying object or animal associated with a figure."),
            q("Which attribute identifies Saint Peter?", ["A wheel", "Keys", "A gridiron", "Arrows"], 1,
              "Keys to the kingdom of heaven.", "Peter holds keys, from Christ's promise to give him the keys of heaven."),
            q("Which bird accompanies the goddess Athena?", ["Eagle", "Dove", "Owl", "Peacock"], 2,
              "A symbol of wisdom.", "The owl is Athena's bird."),
        ],
        "practice": [
            {"type": "iconography_decode", "prompt": "Match each attribute to the saint it identifies.",
             "solution": {"keys": "Saint Peter", "wheel": "Saint Catherine", "gridiron": "Saint Lawrence", "arrows": "Saint Sebastian"},
             "explanation": "Each attribute recalls the saint's legend or martyrdom."},
            {"type": "iconography_decode", "prompt": "Match each attribute to the Greek god it identifies.",
             "solution": {"trident": "Poseidon", "thunderbolt": "Zeus", "caduceus": "Hermes", "owl": "Athena"},
             "explanation": "Classical attributes were fixed early and reused for centuries."},
        ],
    },
    {
        "title": "Naming periods from their traits",
        "summary": "Tell Neoclassicism and Cubism apart and place styles in sequence.",
        "md": """# Naming periods from their traits

Art history is often taught as a chain of periods, each partly a reaction to the one before. Placing a work in its
period is a skill built from two things: knowing the traits of each style and understanding what each style was
reacting against. This class puts the main European styles in order and drills two that students often mix up.

## A rough sequence

- **Gothic** (twelfth to fifteenth century): soaring cathedrals, pointed arches, stained glass.
- **Renaissance** (fourteenth to sixteenth century): perspective, balance and classical revival.
- **Baroque** (seventeenth century): drama, movement, strong light and dark.
- **Rococo** (early eighteenth century): light, playful, ornamental, pastel colours.
- **Neoclassicism** (later eighteenth century into the early nineteenth): a return to Greek and Roman clarity.
- **Romanticism** (early nineteenth century): emotion, nature and the sublime.
- **Impressionism** (1870s): light and everyday modern life.
- **Cubism** (about 1907 to 1914): fragmented forms and multiple viewpoints.

Dates overlap and national styles differ, so treat them as approximate.

## Neoclassicism

Neoclassicism arose in the mid-eighteenth century. Excavations at Herculaneum and Pompeii, begun in the 1730s and
1740s, made ancient Rome vivid to visitors, and Enlightenment thinkers admired reason and civic virtue. Artists
reacted against the Rococo's frivolity. Their works show clear outlines, shallow, stage-like space, restrained
colour, subjects from Greek and Roman history, and a serious moral tone. Jacques-Louis David's *Oath of the
Horatii* (1784) is a standard example: three brothers swear loyalty to Rome in a stark, geometric room.

## Cubism

Cubism was developed by Pablo Picasso and Georges Braque in Paris, starting about 1907. Instead of one fixed
viewpoint, a Cubist painter shows an object from several angles at once, breaking it into geometric facets. Early
Cubist work uses a restricted palette of browns, greys and ochres so that the viewer concentrates on structure. It
rejects the single-viewpoint perspective that had governed European painting since the Renaissance.

## Telling them apart

Ask three questions. How is space handled: a clear, ordered stage (Neoclassical) or a fractured, flattened surface
(Cubist)? How is colour used: restrained but natural, or deliberately muted and limited? What is the subject:
ancient history and moral lessons, or still lifes, guitars and portraits dissected into planes?

## Using the sequence

When you are unsure, work from the extremes. A work with deep perspective and idealised figures is earlier than one
that shows no single viewpoint. Link each style to its reaction: Neoclassicism rejected Rococo, Impressionism broke
from academic polish, and Cubism broke from perspective itself. Naming a style and its reaction shows real
understanding, not just memory.
""",
        "cheat": [cs("Neoclassicism", r"\text{clear lines, antique subjects, moral tone}"), cs("Cubism", r"\text{multiple viewpoints, geometric facets (Picasso, Braque)}"),
                  cs("Order", r"\text{Gothic} \to \text{Renaissance} \to \text{Baroque} \to \text{Neoclassicism} \to \text{Impressionism} \to \text{Cubism}")],
        "quiz": [
            q("Which artists developed Cubism?", ["Monet and Renoir", "Picasso and Braque", "David and Ingres", "Caravaggio and Rubens"], 1,
              "They worked together in Paris from about 1907.", "Pablo Picasso and Georges Braque developed Cubism."),
            q("What did Neoclassicism return to for its models?", ["Medieval manuscripts", "Greek and Roman antiquity", "Japanese prints", "Folk art"], 1,
              "The name contains 'classical'.", "Neoclassical artists took Greek and Roman art and history as their models."),
            q("Which style came first?", ["Cubism", "Impressionism", "Baroque", "Neoclassicism"], 2,
              "It is from the seventeenth century.", "Baroque (1600s) precedes Neoclassicism (late 1700s), Impressionism (1870s) and Cubism (about 1907)."),
        ],
        "practice": [
            {"type": "stylistic_taxonomy", "prompt": "Which movement do these traits point to?",
             "traits": ["objects shown from several viewpoints at once", "fragmented geometric facets", "restricted palette of browns and greys"],
             "period": "Cubism", "options": ["Cubism", "Fauvism", "Romanticism", "Rococo"],
             "explanation": "Several viewpoints and geometric facets define Cubism."},
            {"type": "stylistic_taxonomy", "prompt": "Which movement do these traits point to?",
             "traits": ["clear, crisp outlines", "subjects from Greek and Roman history", "restrained colour and a serious moral tone"],
             "period": "Neoclassicism", "options": ["Rococo", "Neoclassicism", "Impressionism", "Baroque"],
             "explanation": "Clarity and antique subjects with a moral lesson mark Neoclassicism, a reaction to the Rococo."},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------------------------------------------
MUSIC = [
    {
        "title": "Notes and intervals",
        "summary": "Measure the distance between two notes in semitones, names and cents.",
        "md": """# Notes and intervals

An **interval** is the distance between two pitches. Learning to name and hear intervals is the foundation of
everything else in music theory, from melody to harmony.

## Semitones and the octave

The smallest step on a piano, from one key to the very next (black or white), is a **semitone**. Two semitones make a
**whole tone**. Twelve semitones lead to the **octave**, where the note name repeats at a higher pitch. Going up an
octave doubles the frequency: concert A at 440 Hz has the A above it at 880 Hz.

## Naming intervals

We name an interval by counting letter names, which gives its number, and then add a quality such as perfect, major
or minor. Counting in semitones is a handy check:

| Semitones | Interval |
| --- | --- |
| 0 | unison |
| 1 | minor second |
| 2 | major second |
| 3 | minor third |
| 4 | major third |
| 5 | perfect fourth |
| 6 | tritone |
| 7 | perfect fifth |
| 8 | minor sixth |
| 9 | major sixth |
| 10 | minor seventh |
| 11 | major seventh |
| 12 | octave |

From C up to G, for instance, you count C D E F G: five letters, so a fifth. The distance is seven semitones, so it is
a perfect fifth. From E up to C, you count E F G A B C: six letters, a sixth, and eight semitones makes it a minor sixth.

## Ratios and cents

Intervals are also frequency ratios. The octave is 2:1. The just-intonation perfect fifth is 3:2 and the major third
is 5:4. Modern keyboards use **equal temperament**, which divides the octave into twelve identical semitones, each
with the ratio $2^{1/12}$, about 1.0595.

To compare tunings we use **cents**: one hundred cents equal an equal-tempered semitone, so an octave is 1200 cents.
For two frequencies $f_1$ and $f_2$,

$$\\text{cents} = 1200 \\log_2 \\frac{f_2}{f_1}.$$

A just 3:2 fifth is $1200 \\log_2 1.5 \\approx 702$ cents, only two cents wider than the equal-tempered fifth of 700.

## Hearing intervals

Memorise a familiar tune for each interval. Many people use the opening of "Twinkle, Twinkle, Little Star" for the
perfect fifth (the first two notes are the same, and then the melody leaps up a fifth), and the first change of note in
"Happy Birthday" (the second and third notes) for the major second. Practise both melodically (one note after the other) and harmonically
(together). A perfect fifth sounds open and stable, a minor second sounds tense, and a tritone sounds unsettled.

Name the interval by counting, check it by semitones, and confirm it by ear. With practice the three methods agree.
""",
        "cheat": [cs("Cents", r"\text{cents} = 1200 \log_2 (f_2 / f_1)"), cs("Equal-tempered semitone", r"f_2 / f_1 = 2^{1/12} \approx 1.0595"),
                  cs("Just fifth", r"3:2 \approx 702 \text{ cents}")],
        "quiz": [
            q("How many semitones are in a perfect fifth?", ["5", "6", "7", "8"], 2,
              "From C up to G.", "C to G spans seven semitones."),
            q("How many cents are in an octave?", ["100", "700", "1200", "2400"], 2,
              "Twelve semitones of 100 cents each.", "An octave is twelve semitones of 100 cents: 1200 cents."),
            q("What frequency ratio describes an octave?", ["3:2", "5:4", "2:1", "4:3"], 2,
              "Going up an octave doubles the frequency.", "The octave is 2:1."),
        ],
        "practice": [
            {"type": "ear_interval_id", "prompt": "Listen to the two notes and name the interval.", "notes": ["D4", "A4"],
             "explanation": "D to A is seven semitones: a perfect fifth."},
            {"type": "ear_interval_id", "prompt": "Listen to the two notes and name the interval.", "notes": ["E4", "C5"],
             "explanation": "E up to C is eight semitones: a minor sixth."},
        ],
    },
    {
        "title": "Triads and Roman numerals",
        "summary": "Build triads from thirds and label chords with Roman numerals in a key.",
        "md": """# Triads and Roman numerals

A **chord** is three or more notes sounded together. The simplest and most common chord is the **triad**: three
notes stacked in thirds. The lowest note is the **root**, the middle the **third**, the top the **fifth**.

## Four kinds of triad

The quality depends on the sizes of the two stacked thirds, counted in semitones:

- **Major**: major third (4) plus minor third (3). Root, +4, +7. Bright. C-E-G.
- **Minor**: minor third (3) plus major third (4). Root, +3, +7. Darker. C-E-flat-G.
- **Diminished**: two minor thirds. Root, +3, +6. Tense. B-D-F.
- **Augmented**: two major thirds. Root, +4, +8. Unsettled. C-E-G-sharp.

## Triads in a key

Build a triad on every note of a major scale, using only the notes of the scale, and the qualities fall into a fixed
pattern. In C major:

| Degree | Chord | Quality |
| --- | --- | --- |
| I | C | major |
| ii | D minor | minor |
| iii | E minor | minor |
| IV | F | major |
| V | G | major |
| vi | A minor | minor |
| vii° | B diminished | diminished |

## Roman numerals

Roman numerals name each chord by the scale degree of its root, so the same progression can be described in any
key. By convention, **upper-case** numerals mean major chords (I, IV, V) and **lower-case** numerals mean minor
chords (ii, iii, vi). A small circle marks diminished. In G major, I is G, IV is C and V is D. In C major they are
C, F and G. The numerals stay the same, which shows that the two progressions are the same in structure.

## Minor keys

In a minor key the main chords are i, iv and the dominant V. The dominant is usually major, because composers
raise the seventh note of the scale (the leading tone) to pull strongly back to the tonic. In A minor, i is A minor, iv
is D minor and V is E major, which contains G-sharp.

## Common progressions

I-IV-V-I is the basic cadential shape of tonal music. I-vi-IV-V is the familiar progression of a thousand songs from
the 1950s onward. Tonic chords (I) feel like home, dominant chords (V) create tension, and the subdominant (IV)
leads away from home before the dominant brings it back.

When you analyse, first find the key, then write the scale degree of each chord's root, and finally choose
upper or lower case from the chord quality. Check the result by playing it: if each numeral sounds like the right chord, you
have it.
""",
        "cheat": [cs("Major triad", r"0,\;4,\;7 \text{ semitones}"), cs("Minor triad", r"0,\;3,\;7 \text{ semitones}"),
                  cs("Diminished triad", r"0,\;3,\;6 \text{ semitones}")],
        "quiz": [
            q("Which chord is vi in C major?", ["D minor", "E minor", "A minor", "F major"], 2,
              "The sixth note of C major is A.", "The sixth degree of C major is A, and the triad on it is minor: A minor."),
            q("A minor triad is built from:", ["Major third then minor third", "Minor third then major third", "Two major thirds", "Two minor thirds"], 1,
              "Minor sits at the bottom.", "A minor triad has a minor third (3) below a major third (4)."),
            q("Which Roman numerals are major chords in a major key?", ["ii, iii and vi", "I, IV and V", "I, ii and V", "iii, IV and vii°"], 1,
              "Upper case means major.", "I, IV and V are the major triads of a major key."),
        ],
        "practice": [
            {"type": "roman_numeral_analysis", "prompt": "Label each chord with its Roman numeral.", "key": "G major",
             "chords": ["G", "Em", "C", "D"], "expected": ["I", "vi", "IV", "V"],
             "explanation": "G is the tonic (I), E minor is the sixth degree (vi), C is IV and D is V."},
            {"type": "roman_numeral_analysis", "prompt": "Label each chord with its Roman numeral.", "key": "A minor",
             "chords": ["Am", "Dm", "E", "Am"], "expected": ["i", "iv", "V", "i"],
             "explanation": "A minor is i, D minor is iv, and E major is the dominant V (with G-sharp)."},
        ],
    },
    {
        "title": "Figured bass and inversions",
        "summary": "Read the numbers under a bass line and realise the upper voices.",
        "md": """# Figured bass and inversions

In Baroque music (roughly 1600 to 1750), a keyboard player or lutenist often did not read a fully written
accompaniment. Instead they saw a single bass line with small numbers beneath it and filled in the chords
themselves. This shorthand is called **figured bass** or **thoroughbass**, and the practice is **basso continuo**.
Today it survives as a classroom tool for learning chord structure.

## Root position and inversions

A triad can have any of its notes in the bass. In **root position** the root is lowest. In **first inversion** the
third is lowest, and in **second inversion** the fifth is lowest. The names come from the intervals above the bass
note.

| Position | Bass note | Intervals above the bass | Figure |
| --- | --- | --- | --- |
| Root position | root | third and fifth | none (or 5/3) |
| First inversion | third | third and sixth | 6 |
| Second inversion | fifth | fourth and sixth | 6/4 |

A bass note with no figure means a plain root-position triad. The figure 6 is shorthand for 6/3: above the bass you
need a sixth and a third. The figure 6/4 asks for a sixth and a fourth above the bass.

## Realising a figure

To realise a figure, work in the key signature. Count up from the bass note to find each figured interval, using the
notes of the scale. Take a bass note B in C major with the figure 6. A sixth above B is G, and the implied third above B is D,
so the chord is G-B-D. That is the dominant chord, G major, in first inversion (V6). Now take G in the bass with
6/4 in C major: a sixth above G is E and a fourth above G is C. The chord C-E-G has its fifth in the bass, so it is a
tonic chord in second inversion (I6/4), often found just before a final cadence.

Then you choose the octaves. Keep the upper voices close together, usually within an octave of each other and not
too far above the bass, and avoid leaving large gaps between them.

## Why inversions matter

Inversions give composers smooth, stepwise bass lines. A first-inversion chord is lighter and less final than a
root-position chord, so composers use it to keep music moving. The second-inversion chord is unstable, and it
typically appears as a passing or cadential sound, not as a point of rest.

## Checking your work

1. Name the key and bass note, then count the figured intervals above the bass.
2. Write the upper notes and check that they spell a real triad.
3. Confirm the bass note is the third or fifth of that triad, which tells you the inversion.
4. Make sure the voices are in a sensible range.

Practise with a small keyboard, and you will soon hear the figure as a chord, not as a puzzle.
""",
        "cheat": [cs("First inversion", r"\text{bass = third; figure } 6\,(6/3)"), cs("Second inversion", r"\text{bass = fifth; figure } 6/4"),
                  cs("Root position", r"\text{bass = root; no figure or } 5/3")],
        "quiz": [
            q("What does the figure 6 under a bass note usually indicate?", ["Root position", "First inversion", "Second inversion", "A seventh chord"], 1,
              "It is shorthand for 6/3.", "A bare 6 means a sixth and a third above the bass: a first-inversion triad."),
            q("In a second-inversion triad, which chord member is in the bass?", ["The root", "The third", "The fifth", "The seventh"], 2,
              "The figure is 6/4.", "In second inversion the fifth of the chord is the lowest note."),
            q("What is basso continuo?", ["A solo for a bass singer", "A bass line with chords realised by keyboard or lute", "A kind of fugue", "A tuning system"], 1,
              "The harmony is improvised over a written bass.", "Basso continuo is a Baroque practice in which keyboard or lute players realise chords from a figured bass."),
        ],
        "practice": [
            {"type": "figured_bass_realize", "prompt": "In C major, realise the figure: write the two upper voices above the bass, both in octave 4.",
             "bass_note": "B2", "figures": "6", "solution": ["D4", "G4"],
             "explanation": "A sixth above B is G and the third is D: a G major triad in first inversion."},
            {"type": "figured_bass_realize", "prompt": "In C major, realise the figure: write the two upper voices above the bass, both in octave 4.",
             "bass_note": "G3", "figures": "6/4", "solution": ["C4", "E4"],
             "explanation": "A fourth above G is C and a sixth above G is E: a C major triad in second inversion."},
        ],
    },
    {
        "title": "Voice leading in four parts",
        "summary": "Check a four-voice progression for crossed voices and parallel fifths or octaves.",
        "md": """# Voice leading in four parts

Choral harmony is traditionally written for four voices: soprano (S), alto (A), tenor (T) and bass (B), from highest to
lowest. **Voice leading** is the study of how each voice moves from one chord to the next. Good voice leading makes
every line singable and keeps the voices independent, which is the whole idea of part writing.

## The four voices

Each voice has a comfortable range, and the voices stay in order from top to bottom. When two voices swap places,
the result is **voice crossing**: for instance, the alto singing higher than the soprano. It confuses the ear because
the lines no longer have a clear identity, so it is avoided.

## Types of motion

Compare the movement of any two voices between two chords.

- **Parallel**: both move in the same direction by the same interval.
- **Similar**: both move in the same direction by different intervals.
- **Contrary**: they move in opposite directions.
- **Oblique**: one voice stays while the other moves.

Contrary and oblique motion keep voices independent. Parallel motion, especially at certain intervals, fuses them.

## Parallel fifths and octaves

Two voices a perfect fifth apart (seven semitones, or an octave and a fifth) that both move to another perfect
fifth are in **parallel fifths**. Likewise two voices an octave apart that both move to another octave are in
**parallel octaves**. These perfect intervals are so stable and similar in sound that, when the voices move in
parallel, they seem to merge into one. The result sounds hollow and the independence of the lines is lost. Counterpoint
teachers have forbidden them for centuries.

Note that the interval is judged by pitch class, so a perfect twelfth (octave plus fifth) still counts as a fifth.
It is only a problem when both voices actually move: if one of them stays on the same note, the motion is oblique
and there is no parallel.

## A checking routine

1. For each chord, confirm the order S above A above T above B.
2. For each pair of chords, look at all six pairs of voices (S-A, S-T, S-B, A-T, A-B, T-B).
3. If both voices move, compute the interval between them before and after. If both are fifths or both are octaves, flag it.
4. Where possible, repair the problem: let the voices move by contrary motion or keep a common tone.

## Example

Take a C major chord with soprano C5 and bass C3, followed by a D minor chord with soprano D5 and bass D3. Soprano
and bass are two octaves apart in both chords, and each rises a step, so they form parallel octaves. A better
version lets the soprano move against the bass instead, which is contrary motion.

A conforming progression such as C major to G major, with the soprano holding G4 while the lower voices move, has
no defect. Practise by labelling each problem with a code: the kind of error, the voice pair and the chord pair.
""",
        "cheat": [cs("Voice order", r"S \ge A \ge T \ge B \text{ (no crossing)}"), cs("Perfect fifth", r"7 \text{ semitones (mod 12)}"),
                  cs("Octave", r"0 \text{ semitones (mod 12)}")],
        "quiz": [
            q("Which kind of motion best keeps two voices independent?", ["Parallel motion in fifths", "Parallel motion in octaves", "Contrary motion", "Moving together by the same interval"], 2,
              "The voices move in opposite directions.", "Contrary motion gives each voice its own direction."),
            q("In SATB writing, which voice is the highest?", ["Alto", "Tenor", "Bass", "Soprano"], 3,
              "The S comes first.", "Soprano is highest, then alto, tenor and bass."),
            q("Why are parallel perfect fifths and octaves avoided?", ["They are too quiet", "They merge the lines and reduce independence", "They are impossible to sing", "They break the key signature"], 1,
              "They are very stable and sound alike.", "Parallel perfect intervals blur two voices into one."),
        ],
        "practice": [
            {"type": "lint_satb_progression",
             "prompt": "List the voice-leading errors in this progression (codes like parallel_fifth:S_T:chord_1_to_2), or submit valid if there are none.",
             "chords": [{"s": "C5", "a": "G4", "t": "E4", "b": "C3"}, {"s": "D5", "a": "F4", "t": "A3", "b": "D3"}],
             "explanation": "Soprano and bass are two octaves apart in both chords and both rise a step: parallel octaves."},
            {"type": "lint_satb_progression",
             "prompt": "List the voice-leading errors in this progression (codes like parallel_octave:A_B:chord_2_to_3), or submit valid if there are none.",
             "chords": [{"s": "G4", "a": "E4", "t": "C4", "b": "C3"}, {"s": "G4", "a": "D4", "t": "B3", "b": "G2"}],
             "explanation": "The soprano holds G4, which makes oblique motion; the other pairs do not move into matching fifths or octaves. The progression is valid."},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------
# Classics
# ---------------------------------------------------------------------------------------------------------------
CLASSICS = [
    {
        "title": "Reading Roman inscriptions",
        "summary": "Expand the abbreviations found on Roman tombs and monuments.",
        "md": """# Reading Roman inscriptions

The Romans carved words on stone, bronze and tile everywhere: on tombs, milestones, temples, honorific statues and
public buildings. **Epigraphy** is the study of inscriptions, and it gives historians a voice that literary texts
cannot: ordinary people, local officials, freed slaves, soldiers and traders who never appear in the books.

## Why inscriptions are abbreviated

Carving is slow and costly, and stone space is limited, so Romans abbreviated heavily. Many formulas were so common
that every reader knew them. In an edition, scholars expand the abbreviations and show their expansion, a task
called transcription. A modern reader must learn the common formulas to read an inscription at all.

## The most common formulas

- **SPQR**: *Senatus Populusque Romanus*, the Senate and People of Rome. The phrase named the Roman state.
- **D M** or **D M S**: *Dis Manibus* or *Dis Manibus Sacrum*, "to the spirits of the departed" or "sacred to the spirits of the departed". It opens many tombstones from the first and second centuries CE.
- **H S E**: *hic situs est*, "here lies". A tombstone often ends with S T T L, *sit tibi terra levis*, "may the earth lie light on you".
- **IMP**: *imperator*, commander or emperor. **CAES**: *Caesar*. **AVG**: *Augustus*. **COS**: *consul*.
- **V A**: *vixit annos*, "lived (so many) years".
- **F**: *filius* (son) or *fecit* (made), depending on position, so context matters.

## How an epitaph is built

A typical tombstone has several parts. It begins with D M, then names the dead, gives the years of life (V A and a
number) and ends with the person who set up the stone, usually a spouse, child or heir, and the formula H S E. For
example: "D M S, Julia Secunda, vixit annos XXV, H S E." Some slabs add the occupation or a short verse.

## Reading steps

1. Copy the letters exactly as carved, including breaks in the lines.
2. Find the formulas you know (D M, H S E, SPQR).
3. Parse the rest: names usually appear in the nominative or the dative case, depending on whether the dead are addressed or are the dedicatee.
4. Expand each abbreviation and check the grammar. The expansion should be a real Latin phrase.

Note that Latin used **I** for both I and J, and **V** for both U and V, so an inscription reads VIXIT and IVLIA. Numbers use Roman numerals and may have a bar above the letters.

## Why it matters

A tombstone can tell us a person's age, rank, origin, trade and family. By collecting thousands of epitaphs,
historians estimate life expectancy, migration and the social standing of freedmen. Each short formula is a small,
exact piece of evidence about everyday Roman life.

When you expand, be careful: a wrong guess produces a phrase that no Roman would have written. Check each one
against a formula you know.
""",
        "cheat": [cs("SPQR", r"\text{Senatus Populusque Romanus}"), cs("D M S", r"\text{Dis Manibus Sacrum}"), cs("H S E", r"\text{hic situs est (here lies)}")],
        "quiz": [
            q("What does epigraphy study?", ["Coins", "Inscriptions", "Pottery", "Manuscripts"], 1,
              "Epi- means upon; graphein means to write.", "Epigraphy is the study of inscribed texts."),
            q("What does H S E stand for?", ["hic situs est", "honor sacer erat", "habet senatus ordinem", "his sacris edicta"], 0,
              "A tombstone formula.", "H S E expands to hic situs est, 'here lies'."),
            q("What does SPQR stand for?", ["Senatus Populusque Romanus", "Servus Populi Qui Regit", "Sacra Pax Quirini Romae", "Senator Primus Qui Regnat"], 0,
              "It names the state.", "SPQR is Senatus Populusque Romanus, the Senate and People of Rome."),
        ],
        "practice": [
            {"type": "epigraphy_transcribe", "prompt": "Expand the abbreviation into the full Latin phrase.", "inscription_raw": "D M S",
             "transcription": "Dis Manibus Sacrum", "language": "latin", "explanation": "Sacred to the spirits of the departed, a standard opening of a tombstone."},
            {"type": "epigraphy_transcribe", "prompt": "Expand the abbreviation into the full Latin phrase.", "inscription_raw": "H S E",
             "transcription": "hic situs est", "language": "latin", "explanation": "Here lies, a standard closing of an epitaph."},
        ],
    },
    {
        "title": "The Roman career ladder",
        "summary": "Follow the cursus honorum from military tribune to consul and censor.",
        "md": """# The Roman career ladder

During the Roman Republic (509 to 27 BCE), political life for upper-class men followed a recognised path of elected
offices called the **cursus honorum**, "the course of honours". Understanding the ladder explains how Roman
government worked and how ambition shaped it.

## Principles

Roman magistracies shared a few rules.

- **Annuality**: most offices lasted one year, so power changed hands often.
- **Collegiality**: each office was held by at least two men, each able to veto the other.
- **Election**: the voting assemblies chose the magistrates, although wealth and family strongly influenced the outcome.
- **Order**: by custom, and from 180 BCE by the *lex Villia annalis*, a man had to hold the lower offices before standing for the higher ones, and with minimum ages and gaps between posts.

## The steps

A young aristocrat began with military service, often as a **military tribune** serving on a general's staff, and
perhaps a minor board of junior magistrates. The main ladder then ran as follows.

1. **Quaestor**: a financial official who managed treasuries and supported provincial governors. Election to the quaestorship brought membership of the Senate (after Sulla's reforms of the 80s BCE).
2. **Aedile** (optional): in charge of public buildings, markets and the games. Lavish games won popular favour, so ambitious men often held this office.
3. **Praetor**: the chief judicial magistrate. Praetors presided over the law courts, and after their year they often governed provinces.
4. **Consul**: the highest office. Two consuls were elected each year, led the state and commanded armies. Holding the consulship made a man *consularis*, an elder statesman.
5. **Censor**: a rare and prestigious post, usually for former consuls. Two censors served about eighteen months and held the census, assigned citizens to classes and reviewed the membership of the Senate.

## Beyond the ladder

The **tribune of the plebs** was a separate office that protected ordinary citizens and could veto legislation. A
**dictator** was an emergency magistrate appointed for up to six months. Governors of provinces were called
**proconsuls** or **propraetors** after serving their year in Rome.

## Why it mattered

The system rewarded long careers, but it also created fierce competition: only two men became consul each year.
That was one reason Roman politicians raced for glory in war. In the late Republic generals such as Marius, Sulla,
Pompey and Caesar broke the rules about age, repeated terms and the order of offices. Their ambition helped to
wreck the Republic, and Augustus later kept the offices but concentrated real power in himself.

## Memory aid

Remember the sequence by function: money (quaestor), shows (aedile), law (praetor), leadership (consul), review of
the citizen body (censor). The ladder rises in prestige and in responsibility.
""",
        "cheat": [cs("Main ladder", r"\text{quaestor} \to (\text{aedile}) \to \text{praetor} \to \text{consul} \to (\text{censor})"),
                  cs("Consuls per year", r"2 \text{ (collegiality)}"), cs("Term", r"1 \text{ year (censors about 18 months)}")],
        "quiz": [
            q("How many consuls were elected each year?", ["One", "Two", "Three", "Ten"], 1,
              "Collegiality: two held the office together.", "Two consuls were elected each year."),
            q("Which office was chiefly responsible for the law courts?", ["Quaestor", "Aedile", "Praetor", "Censor"], 2,
              "Praetors presided over trials.", "The praetor was the chief judicial magistrate."),
            q("What did the censors do?", ["Commanded the army", "Held the census and reviewed the Senate's membership", "Collected taxes in provinces", "Presided over games"], 1,
              "Their name gives it away: census.", "Censors counted the citizens, assigned them to classes and revised the Senate list."),
        ],
        "practice": [
            {"type": "cursus_honorum_order", "prompt": "Order these offices from the first to the last of the career path.",
             "offices": ["Quaestor", "Praetor", "Consul", "Censor"], "solution": ["Quaestor", "Praetor", "Consul", "Censor"],
             "explanation": "Money, then law, then supreme command; the censorship crowned a career."},
            {"type": "cursus_honorum_order", "prompt": "Order these steps from the first to the last.",
             "offices": ["Military tribune", "Quaestor", "Praetor", "Consul"], "solution": ["Military tribune", "Quaestor", "Praetor", "Consul"],
             "explanation": "Young aristocrats served in the army before the elected ladder began."},
        ],
    },
    {
        "title": "Digging up the past: stratigraphy",
        "summary": "Reconstruct the order of layers in an excavation with a Harris matrix.",
        "md": """# Digging up the past: stratigraphy

Archaeology of the Classical world rests on a simple idea borrowed from geology: layers are laid down one after
another, so deeper layers are generally older. Excavators record these layers carefully, because once a dig is done
the evidence cannot be put back.

## The law of superposition

In an undisturbed sequence, a layer lying above another was deposited later. This is the **law of superposition**.
A floor is laid on a foundation, rubble collapses onto the floor, and soil and plants cover the rubble. Reading from
top to bottom runs backwards through time.

## Contexts

An archaeologist divides a site into **contexts**: the smallest recognisable units, such as a layer of soil, a wall,
a floor, a pit (a *cut*) and the material that fills it (a *fill*). Every context gets a number and a description.
A cut is an act of digging, and its fill is what later filled the hole. A cut is later than everything it slices
through, and earlier than its fill.

## The Harris matrix

In 1973 Edward Harris, working at Winchester in England, introduced a diagram to show the order of contexts. Each
context is a box and a line joins it to the context directly beneath it. Contexts at the same level but without a
physical link are not joined. The result is a flow chart of time, with the latest context at the top and the earliest
at the bottom. Two walls that both rest on the same foundation sit side by side in the matrix, and neither is
earlier than the other unless something else tells you so.

## Building a matrix

1. List every context.
2. For each one, ask what lies **directly** beneath it and what lies directly above it.
3. Record each direct relation as a pair: [above, below].
4. Do not record indirect relations. If A is above B and B is above C, the pair [A, C] is implied and should not be added.
5. Draw the pairs. Check that no loop appears, since a loop would mean one context is earlier than itself.

## Why it matters for the Classical world

Many ancient sites were occupied for centuries: a Roman villa might sit on an Iron Age field and beneath a medieval
farm. Stratigraphy lets archaeologists give a relative sequence even when no written record exists. Coins, pottery
and inscriptions inside the contexts supply dates, and radiocarbon dating can provide absolute dates for organic
material. Together they turn a muddle of soil into a timeline.

## Cautions

Layers can be disturbed by later pits, burrowing animals, ploughing and earlier excavators. A careful team records
such disturbances as contexts in their own right. Interpretation depends on seeing where a cut began, not just
what it contains. The matrix gives structure to that interpretation, and it makes disagreements visible, since
anyone can check each relation against the section drawings.
""",
        "cheat": [cs("Superposition", r"\text{upper layer is later than the layer it covers}"), cs("Matrix pair", r"[\text{above},\ \text{below}] = \text{direct contact only}"),
                  cs("Cut vs fill", r"\text{a cut is earlier than its fill}")],
        "quiz": [
            q("What does the law of superposition say?", ["Older layers lie above newer ones", "In an undisturbed sequence, upper layers are later", "Layers are always horizontal", "Pottery dates every layer"], 1,
              "Think of a stack of plates.", "In an undisturbed sequence the upper layer was laid down after the layer beneath it."),
            q("In a Harris matrix, which relations do you record?", ["Every layer above every other layer", "Only direct above-below contacts", "Only layers with datable finds", "Only walls"], 1,
              "Indirect relations are implied.", "The matrix records direct relations; indirect ones follow by transitivity."),
            q("What is a 'cut' in archaeology?", ["A saw mark on stone", "An act of digging, such as a pit or ditch", "A wall's top course", "A type of pottery"], 1,
              "Its fill is what later filled the hole.", "A cut is a dug feature, such as a pit, and it is earlier than its own fill."),
        ],
        "practice": [
            {"type": "harris_matrix_build",
             "prompt": "Topsoil lies directly over a rubble layer; the rubble lies directly over a mosaic floor; the floor lies directly over a make-up layer. Give each [above, below] pair of directly touching layers.",
             "strata": ["Topsoil", "Rubble", "Mosaic floor", "Make-up layer"],
             "solution": [["Topsoil", "Rubble"], ["Rubble", "Mosaic floor"], ["Mosaic floor", "Make-up layer"]],
             "explanation": "A simple stack gives three direct relations."},
            {"type": "harris_matrix_build",
             "prompt": "Plough soil lies directly over both a ditch fill and a road surface. The ditch fill and the road surface each lie directly over natural clay. Give each [above, below] pair of directly touching layers.",
             "strata": ["Plough soil", "Ditch fill", "Road surface", "Natural clay"],
             "solution": [["Plough soil", "Ditch fill"], ["Plough soil", "Road surface"], ["Ditch fill", "Natural clay"], ["Road surface", "Natural clay"]],
             "explanation": "A diamond shape: two contexts side by side, each in contact with the layers above and below."},
        ],
    },
    {
        "title": "Athenian democracy and the lot",
        "summary": "See how Athens used tribes and lotteries to share offices among citizens.",
        "md": """# Athenian democracy and the lot

Classical Athens (fifth and fourth centuries BCE) gave ordinary male citizens an unusual amount of direct power. A
remarkable feature of the system was **sortition**: choosing officials by lottery. The idea was that every citizen was
equally able to serve, and a lottery avoided bribery and the dominance of the rich and famous.

## Tribes and the Council

Around 508 BCE the reformer Cleisthenes reorganised the citizens into **ten tribes**, each a mix of people from
the city, the coast and the inland districts. The traditional list of the ten includes Erechtheis, Aigeis, Pandionis,
Leontis, Akamantis, Oineis, Kekropis, Hippothontis, Aiantis and Antiochis. The tribes became the basis of the
state: military regiments, the Council and many boards of officials were organised by tribe.

The **Council** (*Boule*) had 500 members, 50 from each tribe, chosen by lot for one year. A citizen could serve at
most twice in a lifetime. The Council prepared the agenda for the **Assembly** (*Ekklesia*), where all citizens
could speak and vote, and supervised daily administration.

## The allotment machine

Athenians used a device called a **kleroterion**, a stone slab with rows of slots. Each citizen's name tablet was
placed in a slot, and a mechanism of black and white balls selected the winners. Fragments of these devices were found in
the Agora. Citizens also drew lots to sit as jurors in the large people's courts, in which hundreds of jurors
voted on a case. Jury pay, introduced in the fifth century, allowed poorer citizens to take part.

## What was not drawn by lot

Not every office was allotted. The ten **generals** (*strategoi*) were elected, because military skill and
experience mattered. Some finance posts, such as the treasurers of the military and festival funds, were also
elected. The system treated
offices that needed expertise differently from those that needed fairness. Even so, elected leaders were
answerable to the people and were examined when they left office.

## Limits

Athenian democracy was direct and limited. Only adult male citizens took part, perhaps a fifth or less of the total
population. Women, enslaved people and foreign residents (metics) were excluded. Plato mocked rule by lot; Aristotle,
who treated it as a mark of one constitution among others, wrote that choosing by lot is characteristic of democracy and election
of oligarchy.

## A fair draw

A sortition has rules: each tribe fills its own quota from its own pool, nobody is chosen twice, and only registered
candidates can be drawn. These are the checks for the exercise below. Notice that the rules protect the equal
standing of the tribes, even though the individual winners are random.
""",
        "cheat": [cs("Tribes", r"10 \text{ tribes (Cleisthenes, c. 508 BCE)}"), cs("Council size", r"10 \times 50 = 500"),
                  cs("Elected, not drawn", r"\text{the ten generals (strategoi)}")],
        "quiz": [
            q("How many tribes did Cleisthenes create?", ["Four", "Ten", "Twelve", "Fifty"], 1,
              "The Council had fifty from each.", "Cleisthenes organised the citizens into ten tribes."),
            q("How many members did the Athenian Council have?", ["100", "300", "500", "1000"], 2,
              "Ten tribes with fifty each.", "The Boule had 500 members, 50 from each of ten tribes."),
            q("Which officials were elected, not chosen by lot?", ["Jurors", "Councillors", "Generals", "All magistrates"], 2,
              "Skill mattered for these posts.", "The ten generals (strategoi) were elected."),
        ],
        "practice": [
            {"type": "athenian_sortition_sim", "prompt": "Draw by lot: choose the stated number of councillors from each tribe.",
             "candidates": {"Akamantis": ["Aristion", "Demaratos", "Eukles", "Philon"], "Oineis": ["Hegesias", "Kleon", "Menon"]},
             "quotas": {"Akamantis": 2, "Oineis": 1}, "explanation": "Each tribe fills its own quota from its own pool, with no duplicates."},
            {"type": "athenian_sortition_sim", "prompt": "Draw by lot: choose the stated number of jurors from each tribe.",
             "candidates": {"Kekropis": ["Alkimos", "Brasidas", "Charmides", "Dion", "Euthymos"], "Aiantis": ["Glaukon", "Hippias", "Isagoras", "Lykon"],
                            "Antiochis": ["Mnesias", "Nikarchos", "Pheidias"]},
             "quotas": {"Kekropis": 3, "Aiantis": 2, "Antiochis": 1}, "explanation": "Pick exactly the quota from each tribe's listed citizens; nobody is chosen twice."},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------
# Rhetoric
# ---------------------------------------------------------------------------------------------------------------
RHETORIC = [
    {
        "title": "Persuasion and figures of speech",
        "summary": "Meet the three appeals and learn to name simile, metaphor and hyperbole.",
        "md": """# Persuasion and figures of speech

**Rhetoric** is the art of effective, persuasive speech and writing. It began in ancient Greece, where citizens had
to argue their own cases in court and speak in the Assembly. Aristotle, in his *Rhetoric* (fourth century BCE),
defined it as the ability to see, in each case, the available means of persuasion.

## The three appeals

Aristotle identified three kinds of proof a speaker can use.

- **Ethos**: the credibility and character of the speaker. We believe people we trust. A doctor speaking on health has ethos on that topic.
- **Pathos**: the emotions of the audience. A speaker moves listeners by stirring fear, pity, pride or anger as the occasion warrants.
- **Logos**: reason and evidence, the logic of the argument itself.

Strong persuasion usually combines all three. An argument with logos alone can seem cold; one with pathos alone
can seem manipulative; one with ethos alone asks the audience to take everything on trust.

## Three occasions

Aristotle also named three branches of oratory. **Deliberative** speech urges the audience to do something in the
future (an assembly debate). **Forensic** speech judges the past (a law court). **Epideictic** speech praises or
blames in the present (a funeral oration).

## Figures of speech

Speakers decorate and sharpen their words with **figures**. A figure that changes the meaning of words is called a
**trope**. Common tropes include:

- **Simile**: an explicit comparison using *like* or *as*. Robert Burns wrote, "O my Luve is like a red, red rose / That's newly sprung in June" (1794).
- **Metaphor**: a comparison without *like* or *as*, which says one thing is another: "All the world's a stage."
- **Hyperbole**: deliberate exaggeration, as in "I have told you a million times".
- **Irony**: saying one thing while meaning another, often the opposite.
- **Personification**: giving human qualities to something that is not human.

## Why figures work

Figures make an idea vivid and memorable. A simile lets the audience see a new idea in terms of a familiar one.
Hyperbole signals strong feeling. Irony invites the audience to share the speaker's judgement. But a figure is not
proof: an image can illustrate a claim, but it cannot establish it.

## How to spot them

1. Read the passage and ask whether any phrase is not meant literally.
2. Find the comparison. If it uses *like* or *as*, it is a simile; if it states the identity outright, it is a metaphor.
3. Ask whether the claim is larger than reality could be: hyperbole.
4. Ask whether the surface meaning conflicts with the clear intention: irony.

Practise on speeches and advertising. You will find that persuasion is full of figures, and that naming them is the
first step toward judging whether they are fair.
""",
        "cheat": [cs("Ethos", r"\text{credibility of the speaker}"), cs("Pathos", r"\text{emotion of the audience}"), cs("Logos", r"\text{reason and evidence}")],
        "quiz": [
            q("Which appeal relies on the speaker's credibility?", ["Logos", "Pathos", "Ethos", "Kairos"], 2,
              "Think of the word ethics.", "Ethos is the appeal to the speaker's character and credibility."),
            q("Which figure uses 'like' or 'as' to compare?", ["Metaphor", "Simile", "Hyperbole", "Irony"], 1,
              "It is the explicit comparison.", "A simile compares two things using like or as."),
            q("Which branch of oratory judges past actions, as in a law court?", ["Deliberative", "Epideictic", "Forensic", "Pastoral"], 2,
              "Forensic comes from the forum.", "Forensic speech judges what happened in the past."),
        ],
        "practice": [
            {"type": "trope_hunter", "prompt": "Name the figure of speech.", "passage": "O my Luve is like a red, red rose that's newly sprung in June.",
             "target_trope": "simile", "options": ["simile", "metaphor", "hyperbole", "irony"],
             "explanation": "The comparison is stated with the word like."},
            {"type": "trope_hunter", "prompt": "Name the figure of speech.", "passage": "I've told you a million times to shut that door.",
             "target_trope": "hyperbole", "options": ["hyperbole", "irony", "metaphor", "understatement"],
             "explanation": "A deliberate exaggeration for emphasis."},
        ],
    },
    {
        "title": "Stasis: where the argument stands",
        "summary": "Find the central question of a dispute: fact, definition, quality, policy or procedure.",
        "md": """# Stasis: where the argument stands

When people argue, they often talk past each other because they are really disputing different questions. Ancient
teachers of rhetoric developed a tool to find the central question: **stasis theory**. *Stasis* is Greek for a "stand" or
"standstill", the point at which the two sides collide.

## Where it comes from

The method is credited to Hermagoras of Temnos (second century BCE) and was taught by Roman writers such as Cicero
and the author of the *Rhetorica ad Herennium*. The classical list has four stases: conjecture, definition, quality and procedure (in Latin *translatio*). Modern teachers
often add a fifth, policy, for arguments about what to do next. We use all five here.

## The five stases

1. **Conjecture**: *Did it happen?* The dispute is about facts. "Did the defendant take the money?"
2. **Definition**: *What should we call it?* The facts are agreed, but the name is not. "Was it theft or only borrowing?"
3. **Quality**: *How serious or justified was it?* The act and its name are agreed, but its seriousness, motive or excuse are in question. "He took the money, but to pay for medicine."
4. **Policy**: *What should we do?* The question is about future action or rules. "Should the city ban cars from the old centre?"
5. **Procedure** (the classical *translatio*): *Is this the right place, time or authority?* The case itself is challenged. "Does this court have jurisdiction?"

## Order matters

The first four questions are asked in sequence because each depends on the last; procedure is the exception,
since a challenge to the forum is usually raised first, before the case is argued at all. If the facts are disputed, there is no point
arguing about justification until they are settled. If the facts are agreed, move to definition; once the name is
agreed, ask about quality. A speaker who skips ahead may waste time, and a listener who does not notice the
stage may feel that the other side is dodging.

## An example

A man admits he took books from a library and says he intended to return them. The facts are not disputed, so
conjecture is closed. The real issue is whether his act should be called theft or borrowing: that is **definition**.
Suppose instead he admits taking an expensive device but says he did it to save a child's life. The facts and
the name are accepted, so the case turns on **quality**: was the act justified?

## Using the tool

1. State the position of each side in one sentence.
2. Identify what they both accept.
3. Find the first point at which they disagree. That point is the stasis.
4. Build your argument for that question and answer the other side's best point on it.

## Why it helps

Stasis theory is useful in law, in politics and in everyday discussions. It trains you to ask what the argument is
really about. It also helps you to avoid straw-man replies, since you answer the actual question your opponent
raises, not the one you wish they had.

Next time you read an editorial, label its central dispute. Many apparently endless debates are simply two people
disagreeing at different stases.
""",
        "cheat": [cs("Conjecture", r"\text{Did it happen? (fact)}"), cs("Definition", r"\text{What is it called?}"), cs("Quality", r"\text{How serious or justified is it?}")],
        "quiz": [
            q("Which stasis asks 'Did it happen?'", ["Definition", "Conjecture", "Quality", "Policy"], 1,
              "It is about the facts.", "Conjecture is the dispute over whether an act occurred."),
            q("Who is credited with systematising stasis theory?", ["Hermagoras", "Homer", "Herodotus", "Hesiod"], 0,
              "He lived in the second century BCE.", "Hermagoras of Temnos is credited with the system."),
            q("What question does the stasis of policy ask?", ["Did it happen?", "What should be done?", "What do we call it?", "Is this the right court?"], 1,
              "It looks forward.", "Policy concerns future action or rules."),
        ],
        "practice": [
            {"type": "stasis_classify", "prompt": "Which question does this case turn on?",
             "case": "He admits he took the books from the library but says it was borrowing, not theft.",
             "correct_stasis": "definition", "explanation": "The facts are agreed; the dispute is what to call the act."},
            {"type": "stasis_classify", "prompt": "Which question does this case turn on?",
             "case": "The defendant admits he broke the window, and agrees it is damage, but says he did it to rescue a child trapped inside.",
             "correct_stasis": "quality", "explanation": "Fact and name are accepted; the dispute is whether the act was justified."},
        ],
    },
    {
        "title": "Arranging a speech: the parts of an oration",
        "summary": "Put the classical parts of a speech in order and know what each one does.",
        "md": """# Arranging a speech: the parts of an oration

Roman teachers divided rhetoric into five tasks, called the **canons**: invention (finding arguments), arrangement
(ordering them), style, memory and delivery. This class is about arrangement, which the Romans called *dispositio*.

## The six parts

Cicero (in *De Inventione*) and the anonymous *Rhetorica ad Herennium* describe a speech in parts. The full
classical form has six.

1. **Exordium** (introduction): wins the goodwill and attention of the audience and shows what the speech is about.
2. **Narratio** (statement of facts): tells the relevant events clearly and briefly, in a way that favours your case.
3. **Partitio** (division): previews the points that follow, or says where agreement and disagreement lie.
4. **Confirmatio** (proof): presents your strongest arguments and evidence for your claim.
5. **Refutatio** (refutation): answers the opposing arguments.
6. **Peroratio** (conclusion): summarises, appeals to the emotions, and leaves the audience ready to act.

Sources differ on details: some join the partitio to the narration, and some fold the refutation into the proofs. The order given here is the one
most often taught.

## Why this order

The order follows the needs of a listener. First the audience must be willing to listen (exordium). Then they need
the facts (narratio) and a map of what is coming (partitio). Next they weigh the proof and the reply to the other
side (confirmatio, refutatio). Finally the speaker draws the threads together and moves them to act (peroratio).

## Flexibility

A speech does not always use all six. A short speech might drop the partitio. A speaker facing a hostile audience
may delay the proof, or begin with a story. Roman writers advise adapting the form to the case. Strong arguments
can be put first to impress or last to be remembered, and the weakest sit in the middle where they are least noticed.

## A model in miniature

A student arguing for a later school start time might open with a story about a tired classmate (exordium), state the current
schedule and the facts of teenage sleep (narratio), announce three reasons (partitio), argue each with data
(confirmatio), answer the objection that buses cannot change (refutatio) and end with a call to adopt the change at
the next board meeting (peroratio).

## Using arrangement

When you write or analyse a speech, label each paragraph with its function. If a paragraph has none, it may not
belong. Check the beginning and the end first, since audiences remember them best. Then verify that the proof comes
after the facts it depends on. A well-arranged speech feels inevitable, because each part prepares the next.
""",
        "cheat": [cs("Six parts", r"\text{exordium, narratio, partitio, confirmatio, refutatio, peroratio}"), cs("Arrangement", r"\text{dispositio, the second of five canons}"),
                  cs("Canons", r"\text{invention, arrangement, style, memory, delivery}")],
        "quiz": [
            q("What is the job of the exordium?", ["To refute the opponent", "To win goodwill and attention", "To list the proofs", "To summarise at the end"], 1,
              "It is the introduction.", "The exordium opens the speech and wins the audience's goodwill."),
            q("Which part answers the opposing arguments?", ["Narratio", "Partitio", "Refutatio", "Exordium"], 2,
              "It has the root of refute.", "The refutatio replies to the other side."),
            q("Which canon of rhetoric is dispositio?", ["Invention", "Arrangement", "Memory", "Delivery"], 1,
              "It means putting things in order.", "Dispositio is arrangement, the second canon."),
        ],
        "practice": [
            {"type": "dispositio_sort", "prompt": "Put the parts of a classical oration in order.",
             "parts": ["exordium", "narratio", "partitio", "confirmatio", "refutatio", "peroratio"],
             "solution": ["exordium", "narratio", "partitio", "confirmatio", "refutatio", "peroratio"],
             "explanation": "Win the audience, tell the facts, preview, prove, reply, conclude."},
            {"type": "dispositio_sort", "prompt": "A short speech uses only four parts. Put them in order.",
             "parts": ["exordium", "narratio", "confirmatio", "peroratio"],
             "solution": ["exordium", "narratio", "confirmatio", "peroratio"],
             "explanation": "Even a short speech opens, states the facts, proves and closes."},
        ],
    },
    {
        "title": "The hidden premise: enthymemes",
        "summary": "Dig out the unstated assumption that completes an everyday argument.",
        "md": """# The hidden premise: enthymemes

Most real arguments are shorter than the logic textbook version. People say "It will rain, so take an umbrella" and
leave out the assumption that makes the leap valid. Aristotle called such compressed arguments **enthymemes**
and held that they are the heart of rhetorical persuasion.

## Syllogism and enthymeme

A **syllogism** has two premises and a conclusion:

- All humans are mortal.
- Socrates is a human.
- Therefore Socrates is mortal.

An **enthymeme** states only some of this. "Socrates is human, so he is mortal" leaves out the major premise (all
humans are mortal). The audience supplies it silently, and that is why enthymemes persuade so well: the listeners
help to build the argument themselves.

Aristotle added that enthymemes usually rest on what is *probable* in daily life, not on what is universally true.
Rhetoric deals with things that could be otherwise, so its premises are often plausible generalisations.

## Finding the hidden premise

To excavate it, follow these steps.

1. Write the stated premise and the conclusion.
2. Ask what must also be true for the stated premise to support the conclusion.
3. Phrase the missing statement as a general claim that links the two ideas. It will usually say "whatever has property X also has property Y".
4. Test the candidate. Plug it in and check that the argument now follows. Then check the direction: "All humans are mortal" works, but "All mortals are human" does not.

## Example

"Rain is forecast for noon, so the picnic should be held indoors." The hidden premise is that rain spoils outdoor
picnics. With it, the argument is complete. Without it, the conclusion is unsupported.

## Why make the premise explicit

Once a hidden premise is on the table you can judge it. Take "This supplement is made only from natural ingredients,
so it is safe." The suppressed premise is "Whatever is natural is safe". That is false: hemlock, arsenic and many
mushrooms are natural and deadly. The argument looked convincing only while the premise stayed hidden. This is why
rhetoric's skeptics and logic's students both value the exercise. Speakers can use the technique to build stronger
arguments, and listeners can use it to catch weak ones.

## Practical use

When you read an editorial or advertisement, ask what the author takes for granted. List the assumptions and rank them
by how risky they are. When you write, state the key premise in your own argument if your audience is likely to
reject it. Leave out premises only when you are confident the audience shares them.

Spotting hidden premises is a skill that improves with practice, and it quickly changes how you hear everyday arguments.
""",
        "cheat": [cs("Syllogism", r"\text{major premise} + \text{minor premise} \Rightarrow \text{conclusion}"),
                  cs("Enthymeme", r"\text{a syllogism with one part left unstated}"), cs("Test", r"\text{add the premise; does the conclusion now follow?}")],
        "quiz": [
            q("What is an enthymeme?", ["A syllogism with a part left unstated", "A kind of metaphor", "A figure of sound", "A speech's conclusion"], 0,
              "Aristotle's rhetorical syllogism.", "An enthymeme is an argument in which a premise or the conclusion is left unstated."),
            q("Why do enthymemes persuade well?", ["They are always true", "The audience supplies the missing part", "They are short", "They avoid emotion"], 1,
              "The audience helps to build the argument.", "Listeners fill in the missing premise, which engages them."),
            q("In 'It is natural, so it is safe', what is the hidden premise?", ["Whatever is safe is natural", "Whatever is natural is safe", "Nothing natural is safe", "Safe things are rare"], 1,
              "The claim runs from natural to safe.", "The argument needs 'whatever is natural is safe', which is false."),
        ],
        "practice": [
            {"type": "enthymeme_excavator", "prompt": "Which unstated premise completes the argument?",
             "stated_premise": "Rain is forecast for noon.", "conclusion": "The picnic should be held indoors.",
             "options": ["Rain spoils outdoor picnics.", "Picnics are always held in the morning.", "Indoor picnics are cheaper."], "solution": 0,
             "explanation": "Only the first option links rain to moving the picnic."},
            {"type": "enthymeme_excavator", "prompt": "Which unstated premise completes the argument?",
             "stated_premise": "This supplement is made only from natural ingredients.", "conclusion": "This supplement is safe.",
             "options": ["Whatever is natural is safe.", "Whatever is safe is natural.", "Supplements should be made in a laboratory."], "solution": 0,
             "explanation": "That is the missing bridge, and it is a weak one: hemlock is natural and deadly."},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------
# Polity
# ---------------------------------------------------------------------------------------------------------------
POLITY = [
    {
        "title": "Veto players: who can say no?",
        "summary": "Trace a bill through the actors whose agreement it needs.",
        "md": """# Veto players: who can say no?

Every political system makes it easier to block change in some ways and harder in others. The political scientist
George Tsebelis (in work published around 2002) proposed a simple way to compare systems: count the **veto players**.

## What is a veto player?

A veto player is an individual or collective actor whose agreement is required to change the status quo. If a veto
player says no, the proposal fails. Some veto players are set by the constitution, such as a president, or each house of a
bicameral legislature. Others come from the party system, such as the parties in a coalition government, each of
which can block a bill the cabinet needs.

## The core rule

A bill passes only if **every** veto player agrees. One opposed veto player is enough to stop it. This makes the
analysis easy: list the actors, check each one's position, and look for the first that refuses.

## Why the number matters

More veto players mean a more stable policy status quo. With many actors, the set of changes they would all
accept shrinks, because the actors must find an outcome all of them prefer to the present policy. Policy then changes
less often and by smaller steps. Systems with few veto players, such as a single-party majority government in a
parliamentary system without a strong upper house, can change policy quickly.

Two further points sharpen the analysis.

- **Absorption**: an actor whose preferences are already between those of others adds no new constraint. Only actors who change the range of acceptable outcomes really count.
- **Distance**: the farther apart the veto players' positions, the harder it is to find an outcome they all support.

## Institutional and partisan veto players

*Institutional* veto players come from the constitutional design: a president, two chambers that must both pass a
bill, a constitutional court that can strike laws down, a federal structure that requires the approval of states.
*Partisan* veto players come from the party system: the parties in a governing coalition. In the same constitution,
a single-party majority has fewer partisan veto players than a coalition of three parties.

## Working a case

1. List the actors named in the case.
2. Note each actor's position, for or against.
3. If all agree, the bill passes.
4. If any disagrees, the bill fails and that actor is the blocker. If several refuse, name the first in the order the bill meets them.

## Use and limits

Veto-player analysis gives quick comparisons across countries, but it simplifies reality. Real actors bargain, trade
favours and threaten, and some vetoes can be overridden by a supermajority. Still, the model is a clear first step:
find who can say no.
""",
        "cheat": [cs("Passage rule", r"\text{pass} \iff \text{every veto player agrees}"), cs("Status quo", r"\text{more veto players} \Rightarrow \text{more stable policy}"),
                  cs("Types", r"\text{institutional (constitution) and partisan (parties)}")],
        "quiz": [
            q("A bill needs three veto players. Two agree and one refuses. What happens?", ["It passes by majority", "It fails", "It passes if the refusing actor is weakest", "It goes to a referendum automatically"], 1,
              "Every veto player must agree.", "A single refusing veto player is enough to block the bill."),
            q("Which scholar is associated with veto-player theory?", ["George Tsebelis", "Robert Putnam", "Samuel Huntington", "Max Weber"], 0,
              "He published the key work around 2002.", "George Tsebelis developed veto-player theory."),
            q("What effect do more veto players usually have?", ["Faster policy change", "A more stable status quo", "Fewer laws blocked", "Larger majorities"], 1,
              "Agreement becomes harder to find.", "More veto players make policy change harder, so the status quo is more stable."),
        ],
        "practice": [
            {"type": "veto_pipeline", "prompt": "An education funding bill needs the Prime Minister and the Parliament. Both support it. Will it pass? If not, who blocks it?",
             "bill": "Education funding act", "veto_players": ["Prime Minister", "Parliament"], "will_pass": True,
             "explanation": "Every veto player agrees, so the bill passes."},
            {"type": "veto_pipeline",
             "prompt": "An income tax bill must pass the lower house, the upper house and a review by the Constitutional court. Both houses pass it, but the court finds it unconstitutional. Will it pass, and who blocks it?",
             "bill": "Income tax reform", "veto_players": ["Lower house", "Upper house", "Constitutional court"], "will_pass": False,
             "blocking_actor": "Constitutional court", "explanation": "One veto player refusing is enough: the court blocks it."},
        ],
    },
    {
        "title": "Turning votes into seats: D'Hondt and quotas",
        "summary": "Allocate legislative seats by highest averages and compare Droop and Hare quotas.",
        "md": """# Turning votes into seats: D'Hondt and quotas

In a system of **proportional representation** (PR), the share of seats a party wins should roughly match its share
of votes. But votes are whole numbers and seats are whole numbers, so every PR system needs a rule for rounding.
Two families of rules do this: highest averages and largest remainders.

## Highest-averages methods

These methods award seats one at a time. For each party, compute a quotient, and the party with the highest quotient
gets the next seat. After a party wins a seat, its quotient is recomputed with a larger divisor.

**D'Hondt** (named for the Belgian lawyer Victor d'Hondt) divides a party's votes $V$ by the number of seats it has
already won plus one:

$$\\text{quotient} = \\frac{V}{s + 1}.$$

So the divisors are 1, 2, 3, 4, and so on. **Sainte-Laguë** uses the odd numbers 1, 3, 5, 7 as divisors:

$$\\text{quotient} = \\frac{V}{2s + 1}.$$

Sainte-Laguë is a little kinder to small parties. D'Hondt slightly favours larger ones. Both are in wide use:
D'Hondt in Spain, Portugal and Poland, for example, and Sainte-Laguë in Sweden and Norway, in modified forms.

## A worked example

Take 100 votes for A, 60 for B and 40 for C, with five seats.

| Divisor | A | B | C |
| --- | --- | --- | --- |
| 1 | 100 | 60 | 40 |
| 2 | 50 | 30 | 20 |
| 3 | 33.3 | 20 | 13.3 |

The five largest quotients are 100 (A), 60 (B), 50 (A), 40 (C) and 33.3 (A). So A gets 3 seats, B gets 1 and C gets 1.
List every quotient you might need, sort them, and take the top ones.

## Largest remainder and quotas

The other family fixes a **quota**, the number of votes that earns a seat, and gives each party as many seats as it
fills whole quotas. Leftover seats go to the largest remainders. Two quotas are common.

- **Hare quota**: $V/S$, total votes divided by seats.
- **Droop quota**: $\\lfloor V/(S+1) \\rfloor + 1$, which is the smallest number of votes such that no more candidates can reach it than there are seats.

For 100,000 votes and 4 seats the Hare quota is 25,000 and the Droop quota is 20,001. The Droop quota is the standard
for the single transferable vote (STV) and is used in Ireland.

## Thresholds

Many systems add an **electoral threshold** that excludes parties below a certain share of votes (for example 5
percent in Germany). Thresholds reduce fragmentation but waste the votes of small parties.

## Checking your work

The total number of seats awarded must equal the seats available. Verify that the last seat given has a higher
quotient than the best quotient left over. If two quotients tie, the rules of the particular system break the tie.
""",
        "cheat": [cs("D'Hondt quotient", r"V/(s+1)"), cs("Sainte-Laguë quotient", r"V/(2s+1)"), cs("Droop quota", r"\lfloor V/(S+1) \rfloor + 1")],
        "quiz": [
            q("What divisors does the D'Hondt method use?", ["1, 2, 3, 4, ...", "1, 3, 5, 7, ...", "2, 4, 6, 8, ...", "1, 4, 9, 16, ..."], 0,
              "The quotient is V/(s+1).", "D'Hondt divides by 1, 2, 3, 4 and so on."),
            q("What is the Droop quota for 100,000 votes and 4 seats?", ["20,000", "20,001", "25,000", "25,001"], 1,
              "floor(100000/5) + 1.", "floor(100000 / 5) + 1 = 20,001."),
            q("Which method tends to favour larger parties slightly more?", ["D'Hondt", "Sainte-Laguë", "Neither", "Both equally"], 0,
              "Sainte-Laguë uses odd divisors.", "D'Hondt gives a small advantage to larger parties; Sainte-Laguë is more even."),
        ],
        "practice": [
            {"type": "compute_dhondt", "prompt": "Allocate the seats with the D'Hondt method.",
             "votes": {"Alder": 340000, "Birch": 280000, "Cedar": 160000, "Dogwood": 60000}, "seats": 7,
             "explanation": "Top quotients: 340k, 280k, 170k, 160k, 140k, 113k, 93k. Alder 3, Birch 3, Cedar 1, Dogwood 0."},
            {"type": "compute_dhondt", "prompt": "Allocate the seats with the D'Hondt method.",
             "votes": {"Left": 46000, "Centre": 30000, "Right": 20000, "Green": 5000}, "seats": 6,
             "explanation": "Top quotients: 46k, 30k, 23k, 20k, 15.3k, 15k. Left 3, Centre 2, Right 1, Green 0."},
        ],
    },
    {
        "title": "Ranked ballots: the instant runoff",
        "summary": "Count a ranked-choice election round by round and see how transfers decide it.",
        "md": """# Ranked ballots: the instant runoff

In a plurality election each voter chooses one candidate and the one with the most votes wins, even with far less than
half. If the opposing votes are split between several candidates, a candidate most voters dislike can win. Ranked
voting tries to fix this by letting voters list their preferences.

## How instant-runoff voting works

In **instant-runoff voting** (IRV), also called ranked-choice voting or the alternative vote, each voter ranks the
candidates in order of preference. The count runs in rounds.

1. Count each ballot for its highest-ranked candidate who is still in the race.
2. If one candidate has more than half the continuing ballots, that candidate wins.
3. If not, eliminate the candidate with the fewest votes. Every ballot that had that candidate on top moves to its next preference.
4. Repeat until a candidate has a majority.

The majority threshold is more than $V/2$ of the ballots that still name a continuing candidate. A ballot whose
choices have all been eliminated is exhausted and drops out of the count.

## An example

Suppose 23 voters rank four candidates. First choices: Ana 8, Ben 6, Cy 5, Dee 4. No one has 12, so Dee is
eliminated. If Dee's four voters all rank Cy second, Cy rises to 9. Still no majority, and Ben, now last with 6, is
eliminated. If Ben's voters prefer Cy next, Cy reaches 15 and wins, although Ana started with the most first choices.
The instant runoff mirrors a series of runoff elections, in one trip to the polls.

## Where it is used

IRV is used for the Australian House of Representatives (preferential voting, adopted in 1918), in some US states and
cities (Maine, for example), and in many party leadership contests.
Do not confuse it with the **single transferable vote**, a related system for electing several winners in one
district, as in Ireland and Malta.

## Strengths and criticisms

Supporters say IRV reduces vote splitting, lets voters support a small candidate without fear of wasting the vote, and
ensures the winner has majority support among continuing ballots. Critics note that it can be harder to count, that the
winner may not be the candidate preferred in all head-to-head comparisons, and that in rare cases a candidate can do
worse by receiving more support. Political scientists describe this last problem as non-monotonicity.

## A tie-breaking note

Real systems set rules for ties, such as drawing lots or looking back at earlier rounds. In the exercises below,
the server breaks a tie for last place by eliminating the candidate that comes first alphabetically.

## Counting carefully

Work in a table: one column per round, one row per candidate. Write the first-choice totals, strike off the last
candidate and rewrite the totals after the transfers. Check that the totals in each round add up to the same number,
unless some ballots are exhausted.
""",
        "cheat": [cs("Majority", r"\text{winner needs} > V/2 \text{ of continuing ballots}"), cs("Elimination", r"\text{remove the candidate with the fewest votes; transfer their ballots}"),
                  cs("Not STV", r"\text{IRV elects one winner; STV elects several}")],
        "quiz": [
            q("In IRV, what happens to a ballot when its top candidate is eliminated?", ["It is discarded", "It moves to the voter's next preference", "It is added to the leader", "It is recounted from scratch"], 1,
              "That is the 'instant runoff'.", "The ballot transfers to the next-ranked continuing candidate."),
            q("How many first-choice votes does a candidate need to win an election with 23 ballots in round one?", ["At least 11", "At least 12", "At least 13", "At least 15"], 1,
              "More than half of 23.", "More than 11.5 means at least 12."),
            q("Which country uses preferential voting (IRV) for the lower house of its national parliament?", ["Australia", "Canada", "United Kingdom", "France"], 0,
              "Adopted in 1918.", "Australia's House of Representatives uses preferential voting."),
        ],
        "practice": [
            {"type": "instant_runoff_tally", "prompt": "Run the instant-runoff count: who wins, and in what order are candidates eliminated?",
             "candidates": ["Ana", "Ben", "Cy", "Dee"],
             "ballots": [["Ana", "Ben", "Dee", "Cy"]] * 8 + [["Ben", "Cy", "Dee", "Ana"]] * 6 + [["Cy", "Ben", "Dee", "Ana"]] * 5 + [["Dee", "Cy", "Ben", "Ana"]] * 4,
             "explanation": "Dee goes first (4 votes), then Ben (6); Cy gains both sets of transfers and beats Ana 15 to 8."},
            {"type": "instant_runoff_tally", "prompt": "Run the instant-runoff count: who wins, and in what order are candidates eliminated?",
             "candidates": ["Mira", "Noel", "Omar"],
             "ballots": [["Mira", "Noel", "Omar"]] * 9 + [["Noel", "Omar", "Mira"]] * 7 + [["Omar", "Noel", "Mira"]] * 6,
             "explanation": "Omar is eliminated (6) and his ballots go to Noel, who wins 13 to 9."},
        ],
    },
    {
        "title": "Voting power: weights, quotas and pivots",
        "summary": "Measure real influence in a weighted vote with the Shapley-Shubik index.",
        "md": """# Voting power: weights, quotas and pivots

In many bodies votes are not equal. Shareholders vote by the number of shares, the Council of the European Union
has used weighted votes, and in the US Electoral College states carry different numbers of electors. This raises a
question: does a voter with twice the weight have twice the power?

## Weighted voting

A weighted voting game is written $[q; w_1, w_2, \\ldots, w_n]$, where $q$ is the **quota** needed to pass a measure
and $w_i$ is the weight of voter $i$. A coalition wins if the total weight of its members reaches the quota.

## Power is not weight

Consider $[51; 40, 35, 25]$. No voter has a majority alone, but any two voters together have at least 60, so any two win.
Each voter is therefore equally necessary, even though the weights differ widely. The voter with 25 has the same
power as the voter with 40. Weight is just a number; **power** is the ability to change the outcome.

## The Shapley-Shubik index

Lloyd Shapley and Martin Shubik proposed a measure in 1954. Imagine voters joining a coalition one at a time, in all
possible orders, and keep a running total of weight. In each order, one voter is the **pivot**: the person whose
joining takes the total from below the quota to the quota or above. A voter's index is the share of orders in which
that voter is the pivot:

$$\\phi_i = \\frac{\\text{number of orderings where } i \\text{ is pivotal}}{n!}.$$

The indices of all voters add up to 1, so each index is a share of the total power.

## A worked example

Take $[6; 4, 3, 2, 1]$ with voters A, B, C and D. There are $4! = 24$ orderings. Counting pivots gives A 10, B 6, C 6
and D 2. So the indices are A 10/24 (about 0.417), B and C 0.25 each, and D 2/24 (about 0.083). The weights 4, 3, 2, 1
are in the ratio 40:30:20:10, but the power shares are not the same as the weight shares: D holds 10 percent of the
weight and just over 8 percent of the power.

## Special voters

- A **dummy** is a voter who is never pivotal, with an index of 0. A voter whose weight is too small to ever change a result is a dummy, no matter how many votes the voter holds.
- A **dictator** is a voter whose weight alone reaches the quota. The dictator's index is 1.

## Other indices

The **Banzhaf index** counts the number of coalitions where a voter is critical, rather than orderings. It can give
different values from Shapley-Shubik. Both are used in legal and political arguments about fair representation.

## Computing it

1. List all orderings of the voters. For small games this is feasible by hand; for $n$ voters there are $n!$.
2. For each ordering, add weights from the left and mark the voter at whom the total first reaches the quota.
3. Count the marks for each voter and divide by $n!$.

The answers should sum to 1. Check this before you submit.
""",
        "cheat": [cs("Shapley-Shubik index", r"\phi_i = \frac{\#\text{orderings where } i \text{ is pivotal}}{n!}"), cs("Orderings", r"n! \text{ (4 voters: 24)}"),
                  cs("Sum of indices", r"\sum_i \phi_i = 1")],
        "quiz": [
            q("How many orderings are there for four voters?", ["4", "12", "24", "64"], 2,
              "Four factorial.", "4! = 24."),
            q("What is a dummy voter?", ["A voter who always votes yes", "A voter who is never pivotal", "A voter with the most weight", "A voter who abstains"], 1,
              "Their index is zero.", "A dummy is never the pivot, so their power index is 0."),
            q("In [51; 40, 35, 25], what is each voter's Shapley-Shubik index?", ["40/100, 35/100, 25/100", "1/3 each", "1/2, 1/4, 1/4", "1, 0, 0"], 1,
              "Any two voters form a winning coalition.", "Each voter is pivotal in 2 of the 6 orderings, so each has an index of 1/3."),
        ],
        "practice": [
            {"type": "compute_shapley_shubik_pivotal", "prompt": "Find each voter's Shapley-Shubik power index (a fraction of 1).",
             "quota": 51, "weights": {"A": 40, "B": 35, "C": 25},
             "explanation": "Whoever joins second is the pivot, and each voter is second in 2 of 6 orderings: 1/3 each, despite the unequal weights."},
            {"type": "compute_shapley_shubik_pivotal", "prompt": "Find each voter's Shapley-Shubik power index (a fraction of 1).",
             "quota": 6, "weights": {"A": 4, "B": 3, "C": 2, "D": 1},
             "explanation": "Pivot counts over 24 orderings: A 10, B 6, C 6, D 2, so A 5/12, B 1/4, C 1/4, D 1/12."},
        ],
    },
]

LESSONS = {
    "literature": LITERATURE, "art_history": ART_HISTORY, "music": MUSIC,
    "classics": CLASSICS, "rhetoric": RHETORIC, "polity": POLITY,
}


def build_topics():
    """Every lesson as a topic dict: ids kit-<kit-with-dashes>-class-<1..4> (24 in all)."""
    topics = []
    for kit, lessons in LESSONS.items():
        workspace, category, course = KIT_META[kit]
        for n, les in enumerate(lessons, start=1):
            topics.append({
                "id": f"kit-{kit.replace('_', '-')}-class-{n}", "title": f"{course} {n}: {les['title']}", "category": category,
                "difficulty": DIFFICULTY[n], "summary": les["summary"] + f" Class {n} of 4.",
                "markdownContent": les["md"], "cheatSheet": les["cheat"], "quiz": [dict(x, id=f"q{i + 1}") for i, x in enumerate(les["quiz"])],
                "practice": les["practice"], "source": {"workspace": workspace},
            })
    return topics


def _post(topic):
    req = urllib.request.Request(API + "/api/topics", method="POST", data=json.dumps(topic).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{topic['id']}: HTTP {e.code} {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"The &.edu backend is not reachable at {API} ({e.reason}). Start it, or use --dry-run.")


def main():
    parser = argparse.ArgumentParser(description="Post four sample classes for each liberal-arts kit (24 lessons) to the backend")
    parser.add_argument("--dry-run", action="store_true", help="normalize offline against a throwaway data folder and write nothing")
    args = parser.parse_args()
    topics = build_topics()
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="andedu-seed-") as scratch:
            os.environ["SCIEDU_CONTENT_DIR"] = scratch  # the server opens its data here, never the live database
            import server  # noqa: E402
            bad = 0
            for t in topics:
                clean, warnings = server.normalize_topic(t)
                kept, sent = len(clean["practice"]), len(t["practice"])
                quiz_ok = len(clean["quiz"]) == len(t["quiz"])
                print(f"{t['id']}: {kept}/{sent} items, {len(clean['quiz'])}/{len(t['quiz'])} quiz"
                      f"{'  WARNINGS: ' + '; '.join(warnings) if warnings else ''}")
                bad += bool(warnings) or kept != sent or not quiz_ok
            sys.exit(1 if bad else 0)
    for t in topics:
        res = _post(t)
        print(f"{t['id']}: saved" + (f" with warnings {res['warnings']}" if res.get("warnings") else ""))
        if res.get("warnings"):
            sys.exit(1)


if __name__ == "__main__":
    main()
