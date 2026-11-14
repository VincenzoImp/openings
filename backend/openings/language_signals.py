"""The language a posting is written in and the languages it says a candidate needs.

Both are deterministic: fixed word lists and phrase rules in English, German,
French and Italian, without a model, a dictionary download or the network.

**Posting language.** Very frequent function words of each language are counted
in the first words of the text; a word that several languages share counts for
each of them in proportion. The language with the highest score wins when it
has enough evidence and clearly leads the second; otherwise the language is
unknown (``None``). The confidence is the winner's share of the two best scores.

**Stated requirements.** A requirement is a language name bound to a cue next to
it: a prefix such as "fluent", "fließend", "maîtrise du" or "ottima conoscenza
della", or a suffix such as "skills", "C1", "Kenntnisse", "courant", "exigé" or
"richiesto". Names joined by "and", commas or slashes form one list sharing its
cues; names joined by "or" are alternatives, one of which is enough. A cue such
as "a plus", "von Vorteil", "un atout" or "titolo preferenziale" makes the list
an advantage, which is not a requirement, and a negation ("no", "keine", "pas", "non")
nearby cancels it. A name that only describes something else ("German market",
"entreprise française", "deutsche Kunden") is not a language mention.
"""

import re
import unicodedata

# Bump when the rules change: stored signals of another format are computed again.
FORMAT = 1

# The posting's first words are enough to tell its language.
_LANGUAGE_WORDS = 1500
_MIN_EVIDENCE = 6.0
_MIN_LEAD = 1.4
# Requirements are read from the whole text, bounded for very long pages.
_REQUIREMENT_CHARS = 60_000

_FUNCTION_WORDS = {
    "en": (
        "the and of to in a is are you your we our with for will be this that on as have "
        "has an or from at by who what which about would can all their they it its into "
        "within across including experience skills ability strong working join us looking"
    ),
    "de": (
        "der die das und mit fur wir sie ist sind von zu den dem des ein eine einen einem "
        "einer auf im bei oder als auch nicht uns unser unsere unseren ihre ihr du dich dein "
        "deine wird werden haben hast bist uber aus nach sowie kenntnisse erfahrung aufgaben "
        "bieten zum zur es sich sehr deiner deinen ihnen"
    ),
    "fr": (
        "le la les des du de et en un une pour avec dans sur nous vous votre vos notre nos "
        "est sont etre au aux par qui que ou ce cette ces son sa ses plus pas ne se "
        "experience equipe competences poste vous profil missions"
    ),
    "it": (
        "il lo la gli le di del della delle dei degli e ed per con un una uno che sono nel "
        "nella alla al dal dalla su ci si come anche nostro nostra nostri tuo tua esperienza "
        "conoscenza lavoro sei siamo offriamo cerchiamo requisiti tuoi"
    ),
    "es": (
        "el la los las de del y en un una para con por que es son nuestro nuestra tu su sus "
        "se al como mas experiencia equipo ofrecemos buscamos trabajo conocimientos"
    ),
    "nl": (
        "de het een en van voor met je jij wij we ons onze zijn is op te aan bij of als ook "
        "niet dat die wat naar om ervaring werken jouw bent hebt heb kennis"
    ),
    "pt": (
        "o a os as de do da dos das e em no na um uma para com por que e sao nosso nossa "
        "voce seu sua experiencia equipe conhecimento trabalho oferecemos"
    ),
}


# Bullets end a clause; typographic apostrophes are apostrophes.
_FOLD = str.maketrans({"ß": "ss", "’": "'", "`": "'", **dict.fromkeys("•·▪◦●", "\n")})


def fold(text):
    """Lower case ASCII without accents: ß as ss, bullets as line breaks; other letters go."""
    text = (text or "").lower().translate(_FOLD)
    if text.isascii():
        return text
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


_WORD = re.compile(r"[a-z]+")


def _words(text):
    return set(text.split())


def _weights():
    owners = {}
    for code, words in _FUNCTION_WORDS.items():
        for word in set(words.split()):
            owners.setdefault(word, []).append(code)
    return {word: {code: 1 / len(codes) for code in codes} for word, codes in owners.items()}


_WEIGHTS = _weights()


def posting_language(text):
    """The language a text is written in, as an ISO 639-1 code, and a confidence.

    Returns ``(None, None)`` when the text is too short or no language leads clearly.
    """
    scores = {}
    words = _WORD.findall(fold(text[:20_000] if text else ""))[:_LANGUAGE_WORDS]
    for word in words:
        for code, weight in _WEIGHTS.get(word, {}).items():
            scores[code] = scores.get(code, 0.0) + weight
    if not scores:
        return None, None
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best, score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if score < _MIN_EVIDENCE or score < _MIN_LEAD * second:
        return None, None
    return best, round(score / (score + second), 2)


# Language names (folded) in the four languages read, each with its ISO 639-1 code,
# in the order: English, German, French, Italian.
_NAME_TABLE = {
    "en": ("english", "englisch", "anglais anglaise", "inglese"),
    "de": ("german", "deutsch schweizerdeutsch", "allemand allemande", "tedesco tedesca"),
    "fr": ("french", "franzosisch", "francais francaise", "francese"),
    "it": ("italian", "italienisch", "italien italienne", "italiano italiana"),
    "es": ("spanish", "spanisch", "espagnol espagnole", "spagnolo spagnola castellano"),
    "nl": (
        "dutch flemish",
        "niederlandisch hollandisch flamisch",
        "neerlandais neerlandaise",
        "olandese",
    ),
    "pt": ("portuguese", "portugiesisch", "portugais portugaise", "portoghese"),
    "pl": ("polish", "polnisch", "polonais", "polacco"),
    "sv": ("swedish", "schwedisch", "suedois", "svedese"),
    "da": ("danish", "danisch", "danois", "danese"),
    "no": ("norwegian", "norwegisch", "norvegien norvegienne", "norvegese"),
    "fi": ("finnish", "finnisch", "finnois", "finlandese"),
    "cs": ("czech", "tschechisch", "tcheque", "ceco"),
    "ru": ("russian", "russisch", "russe", "russo"),
    "ja": ("japanese", "japanisch", "japonais", "giapponese"),
    "zh": ("chinese mandarin", "chinesisch", "chinois", "cinese"),
    "ar": ("arabic", "arabisch", "arabe", "arabo"),
    "tr": ("turkish", "turkisch", "turc", "turco"),
    "ko": ("korean", "koreanisch", "coreen", "coreano"),
}
NAMES = {
    name: code
    for code, columns in _NAME_TABLE.items()
    for names in columns
    for name in names.split()
}
# English names are adjectives before a noun; French and Italian ones follow the noun.
_ENGLISH_NAMES = {name for columns in _NAME_TABLE.values() for name in columns[0].split()}
_ROMANCE_NAMES = {
    name for columns in _NAME_TABLE.values() for names in columns[2:] for name in names.split()
}
# German noun stems: "Deutschkenntnisse", "Englischkenntnissen", "deutschsprachig".
_GERMAN_STEMS = {name: code for code, columns in _NAME_TABLE.items() for name in columns[1].split()}
_COMPOUND = re.compile(
    r"^(" + "|".join(sorted(_GERMAN_STEMS, key=len, reverse=True)) + r")"
    r"(sprachkenntnissen|sprachkenntnisse|kenntnissen|kenntnisse|sprachig|sprachige|"
    r"sprachigen|sprachiger|muttersprachler|muttersprachlerin)$"
)
# "deutsche Sprache", "in englischer Sprache".
_GERMAN_ADJECTIVE = re.compile(
    r"^(" + "|".join(sorted(_GERMAN_STEMS, key=len, reverse=True)) + r")(e|en|er|es)$"
)

# A name followed (English) or preceded (French, Italian) by one of these words is
# still a language; any other word means the name describes something else.
_ENGLISH_FOLLOWERS = _words(
    """language languages skills skill proficiency fluency knowledge speaker speakers is are
    and or required mandatory essential necessary needed a an as would will should must at
    on to in level c1 c2 b1 b2 a1 a2 native written spoken plus nice preferred desirable
    beneficial fluent communication both preferably also an asset advantage welcome
    certificate is would be either"""
)
_ROMANCE_PRECEDERS = _words(
    """langue langues lingua lingue l la le les de du des en et ou e o il in della dell del
    di dello degli maitrise connaissance connaissances conoscenza conoscenze parle parler
    parlez parlare parli parliamo et ou y padronanza courant bilingue madrelingua ecrit
    parlato scritto anche aussi ainsi que nonche oltre all alla"""
)

_CONNECTORS = {
    "and": "and",
    "und": "and",
    "et": "and",
    "e": "and",
    "ed": "and",
    "y": "and",
    "&": "and",
    ",": "and",
    "/": "and",
    "sowie": "and",
    "nonche": "and",
    "or": "or",
    "oder": "or",
    "ou": "or",
    "o": "or",
    "oppure": "or",
}
# Inside a list: "German (C1), English (B2)", "German and/or French".
_TRANSPARENT = _words("( ) - a1 a2 b1 b2 c1 c2 level niveau livello also auch")
_LEVELS = {"a1", "a2", "b1", "b2", "c1", "c2"}
# Articles and prepositions after a connector: "dell'italiano e del francese",
# "du français et de l'anglais".
_LINKS = _words("del dell della dello dei degli de du des l la le the of")


def _phrases(text):
    return [tuple(phrase.split()) for phrase in text.split("|")]


# A requirement cue before the list ("fluent German"), after it ("German skills")
# or on either side ("required").
_BEFORE = _phrases(
    "fluent|fluently|fluency in|proficient in|proficiency in|native|business fluent|"
    "full professional proficiency in|professional proficiency in|working proficiency in|"
    "working knowledge of|knowledge of|good knowledge of|command of|good command of|"
    "excellent|very good|good|strong|solid|advanced|perfect|professional|business|"
    "written and spoken|spoken and written|speak|speaks|you speak|write|"
    "languages|language|bilingual|"
    "fliessend|fliessende|fliessendes|fliessenden|verhandlungssicher|verhandlungssichere|"
    "verhandlungssicheres|verhandlungssicheren|sehr gute|sehr guten|sehr gutes|gute|guten|"
    "ausgezeichnete|ausgezeichneten|exzellente|exzellenten|perfekte|perfektes|sichere|"
    "sicheres|sprachen|sprache|beherrschung der|du sprichst|sie sprechen|sprichst|"
    "maitrise|maitrise du|maitrise de|maitrise de la|maitrise de l|parfaite maitrise|"
    "bonne maitrise|excellente maitrise|connaissance du|connaissance de|connaissance de la|"
    "connaissance de l|bonne connaissance|parler|parlez|parler couramment|langues|"
    "excellente|bonne|parfaite|parfait|solide|bilingue|"
    "conoscenza|conoscenza della|conoscenza della lingua|conoscenza dell|conoscenza del|"
    "ottima|ottima conoscenza|buona|buona conoscenza|eccellente|padronanza|"
    "padronanza della|padronanza dell|perfetta|lingue|parlare|parli|madrelingua|correntemente|"
    "fluentemente|couramment|parler couramment|parlez couramment"
)
_AFTER = _phrases(
    "skills|skill|proficiency|fluency|knowledge|speaker|speakers|is required|are required|"
    "is mandatory|is essential|is a must|a must|is necessary|is needed|required|fluently|"
    "at a professional level|professional level|at native level|native level|"
    "at business level|business level|at a high level|auf verhandlungsniveau|"
    "verhandlungsniveau|auf hohem niveau|"
    "mandatory|essential|necessary|needed|native|native speaker|fluent|written and spoken|"
    "spoken and written|c1|c2|b1|b2|level c1|level c2|level b2|level b1|mother tongue|"
    "kenntnisse|sprachkenntnisse|erforderlich|vorausgesetzt|zwingend|zwingend erforderlich|"
    "voraussetzung|notwendig|in wort und schrift|wort und schrift|fliessend|"
    "verhandlungssicher|auf muttersprachniveau|muttersprache|muttersprachlich|"
    "auf muttersprachlichem niveau|sehr gut|"
    "courant|courante|courants|courantes|couramment|exige|exigee|exiges|exigees|requis|"
    "requise|requises|indispensable|indispensables|obligatoire|obligatoires|"
    "imperatif|imperative|langue maternelle|parle et ecrit|ecrit et parle|lu ecrit parle|"
    "est indispensable|est exige|est exigee|est requis|est requise|niveau c1|niveau b2|"
    "fluente|richiesto|richiesta|richiesti|richieste|e richiesto|e richiesta|"
    "indispensabile|obbligatorio|obbligatoria|madrelingua|parlato e scritto|"
    "scritto e parlato|necessario|necessaria|livello c1|livello b2|"
    "working language|is our working language|is the working language|company language"
)
_EITHER = _phrases(
    "required|requires|require|requirement|must|must have|must speak|mandatory|essential|"
    "need|needs|we need|erforderlich|voraussetzung|zwingend|exige|exigee|requis|requise|"
    "indispensable|obligatoire|richiesto|richiesta|richiesti|indispensabile|obbligatorio"
)
_ADVANTAGE = _phrases(
    "a plus|is a plus|an asset|asset|advantage|advantageous|an advantage|nice to have|"
    "nice|bonus|preferred|preferably|desirable|desired|beneficial|welcome|ideally|"
    "appreciated|helpful|would be great|optional|is an advantage|"
    "von vorteil|vorteil|vorteilhaft|wunschenswert|ein plus|willkommen|idealerweise|gerne|"
    "erwunscht|hilfreich|wunsch|waren ideal|ware ideal|ist ideal|"
    "un atout|atout|un plus|apprecie|appreciee|apprecies|appreciees|souhaite|souhaitee|"
    "souhaitable|avantage|un avantage|idealement|bienvenu|bienvenue|serait un plus|"
    "titolo preferenziale|preferenziale|gradito|gradita|graditi|preferibile|"
    "preferibilmente|apprezzato|apprezzata|vantaggio|un vantaggio|costituisce un plus"
)
_NEGATION = _phrases(
    "no|not|without|not required|keine|kein|keinerlei|nicht|ohne|pas|sans|aucune|aucun|"
    "non|nessuna|nessun|senza|not necessary|not needed"
)
_TITLE_AFTER = _phrases("speaking|- speaking")
_CLAUSE = re.compile(r"[.!?;\n\r•·▪◦●|]+")
_TOKEN = re.compile(r"[a-z0-9]+|[,/&()-]")
# A name followed (English) or preceded (French, Italian) by one of these words is
# still a language; any other word means the name describes something else.
_FOLLOWERS = _ENGLISH_FOLLOWERS | {
    phrase[0] for phrase in _AFTER + _EITHER + _ADVANTAGE + _NEGATION + _TITLE_AFTER
}
_PRECEDERS = _ROMANCE_PRECEDERS | {phrase[-1] for phrase in _BEFORE + _EITHER}
_AFTER_IN_TITLE = _AFTER + _TITLE_AFTER


def _index(phrases):
    by_first = {}
    for phrase in phrases:
        by_first.setdefault(phrase[0], []).append(phrase)
    return by_first


_INDEXES = {}


def _find(tokens, phrases):
    """Every (start, end) span of tokens equal to one of the phrases."""
    key = id(phrases)
    if key not in _INDEXES:
        _INDEXES[key] = (phrases, _index(phrases))
    by_first = _INDEXES[key][1]
    found = []
    for index, token in enumerate(tokens):
        for phrase in by_first.get(token, ()):
            if tuple(tokens[index : index + len(phrase)]) == phrase:
                found.append((index, index + len(phrase)))
    return found


def _mention(tokens, index):
    """The language code a token names, and whether it carries its own cue."""
    token = tokens[index]
    after = tokens[index + 1] if index + 1 < len(tokens) else None
    before = tokens[index - 1] if index else None
    compound = _COMPOUND.match(token)
    if compound:
        # "Deutschkenntnisse" is a requirement cue; "deutschsprachig" only a mention.
        return _GERMAN_STEMS[compound.group(1)], "kenntnisse" in compound.group(
            2
        ) or compound.group(2).startswith("mutter")
    adjective = _GERMAN_ADJECTIVE.match(token)
    if adjective and after and after.startswith("sprach"):
        return _GERMAN_STEMS[adjective.group(1)], False
    code = NAMES.get(token)
    if code is None:
        return None, False
    if (
        token in _ENGLISH_NAMES
        and after is not None
        and not (after in _FOLLOWERS or after in NAMES or after in _CONNECTORS or after in "()-,/")
    ):
        return None, False
    if (
        token in _ROMANCE_NAMES
        and before is not None
        and not (
            before in _PRECEDERS or before in NAMES or before in _CONNECTORS or before in "()-,/"
        )
    ):
        return None, False
    return code, False


def _lists(tokens):
    """Language names joined by connectors: [(start, end, groups, own_cue)]."""
    mentions = {}
    for index in range(len(tokens)):
        code, cue = _mention(tokens, index)
        if code:
            mentions[index] = (code, cue)
    lists = []
    index = 0
    while index < len(tokens):
        if index not in mentions:
            index += 1
            continue
        start, end = index, index + 1
        codes, joins, cue = [mentions[index][0]], [], mentions[index][1]
        # A name with its own cue ("Deutschkenntnisse", "German (C1)") ends its list.
        own = mentions[index][1]
        cursor = end
        while cursor < len(tokens) and not own:
            joiner = None
            probe = cursor
            while probe < len(tokens) and (
                tokens[probe] in _CONNECTORS
                or tokens[probe] in _TRANSPARENT
                or (joiner and tokens[probe] in _LINKS)
            ):
                if tokens[probe] in _CONNECTORS:
                    # "and/or" is an alternative.
                    joiner = "or" if "or" in (joiner, _CONNECTORS[tokens[probe]]) else "and"
                if tokens[probe] in _LEVELS:
                    own = cue = True
                probe += 1
            if not own and probe < len(tokens) and probe in mentions and joiner:
                codes.append(mentions[probe][0])
                joins.append(joiner)
                own = mentions[probe][1]
                cue = cue or own
                end = cursor = probe + 1
            else:
                break
        # Levels directly after the last name belong to the list: "German C1".
        probe = end
        while probe < len(tokens) and tokens[probe] in _TRANSPARENT:
            cue = cue or tokens[probe] in _LEVELS
            probe += 1
        lists.append((start, end, _groups(codes, joins), cue))
        index = end
    return lists


def _groups(codes, joins):
    """Codes joined by "and" are separate requirements; "or" makes alternatives."""
    groups, current = [], [codes[0]]
    for code, join in zip(codes[1:], joins):
        if join == "or":
            current.append(code)
        else:
            groups.append(current)
            current = [code]
    groups.append(current)
    return [sorted(set(group)) for group in groups]


def _nearest(lists, start, end, before, after):
    """The list a cue spanning [start, end) binds to: the one beside it, or None."""
    best = None
    for position, (first, last, *_rest) in enumerate(lists):
        if after and last <= start and start - last <= after:
            distance = start - last
        elif before and end <= first and first - end <= before:
            distance = first - end
        else:
            continue
        # No other list in between.
        if any(
            (last <= other_first and other_last <= start)
            or (end <= other_first and other_last <= first)
            for index, (other_first, other_last, *_others) in enumerate(lists)
            if index != position
        ):
            continue
        if best is None or distance < best[0]:
            best = (distance, position)
    return None if best is None else best[1]


def _clause_requirements(clause, title=False):
    # "Teamsprache ist Englisch", "Arbeitssprache: Deutsch".
    tokens = [
        "sprache"
        if token.endswith("sprache") and len(token) > 7 and not token.startswith("mutter")
        else token
        for token in _TOKEN.findall(clause)
    ]
    lists = _lists(tokens)
    if not lists:
        return []
    state = [{"cue": own, "advantage": False, "negated": False} for *_, own in lists]
    for start, end in _find(tokens, _BEFORE):
        bound = _nearest(lists, start, end, before=4, after=0)
        if bound is not None:
            state[bound]["cue"] = True
    # In a title, "German-speaking Support Engineer" states what the role needs.
    for start, end in _find(tokens, _AFTER_IN_TITLE if title else _AFTER):
        bound = _nearest(lists, start, end, before=0, after=4)
        if bound is not None:
            state[bound]["cue"] = True
    for start, end in _find(tokens, _EITHER):
        # A cue just after a list belongs to it; otherwise to the list it precedes.
        bound = _nearest(lists, start, end, before=0, after=3)
        if bound is None:
            bound = _nearest(lists, start, end, before=5, after=0)
        if bound is not None:
            state[bound]["cue"] = True
    for start, end in _find(tokens, _ADVANTAGE):
        bound = _nearest(lists, start, end, before=8, after=10)
        if bound is not None:
            state[bound]["advantage"] = True
    for start, end in _find(tokens, _NEGATION):
        bound = _nearest(lists, start, end, before=3, after=4)
        if bound is not None:
            state[bound]["negated"] = True
    required = []
    for (*_, groups, _own), item in zip(lists, state):
        if item["cue"] and not (item["negated"] or item["advantage"]):
            required.extend(groups)
    return required


# Every word that can name a language, to skip the clauses that name none quickly.
_NAME_WORDS = set(NAMES) | {
    stem + suffix
    for stem in _GERMAN_STEMS
    for suffix in _words(
        "sprachkenntnissen sprachkenntnisse kenntnissen kenntnisse sprachig sprachige "
        "sprachigen sprachiger muttersprachler muttersprachlerin e en er es"
    )
}


def language_requirements(text, title=""):
    """Languages the text requires.

    ``required`` is a list of groups, each a sorted list of codes of which one is
    enough ("German or French" is one group of two). A language stated only as an
    advantage is not required.
    """
    required = []
    for source, is_title in ((title, True), (text, False)):
        folded = fold((source or "")[:_REQUIREMENT_CHARS])
        if _NAME_WORDS.isdisjoint(_WORD.findall(folded)):
            continue
        for clause in _CLAUSE.split(folded):
            if _NAME_WORDS.isdisjoint(_WORD.findall(clause)):
                continue
            required.extend(_clause_requirements(clause, is_title))
    unique = []
    for group in required:
        if group not in unique:
            unique.append(group)
    # A single requirement already covers any alternative that contains it.
    singles = {group[0] for group in unique if len(group) == 1}
    unique = [group for group in unique if len(group) == 1 or not singles.intersection(group)]
    return {"required": sorted(unique)}


def text_signals(title, posting):
    """Both text signals of a job, as stored in job_signals."""
    language, confidence = posting_language(
        posting if len(posting or "") >= 200 else f"{title}\n{posting}"
    )
    stated = language_requirements(posting, title)
    return {
        "language": language,
        "language_confidence": confidence,
        "required": stated["required"],
    }
