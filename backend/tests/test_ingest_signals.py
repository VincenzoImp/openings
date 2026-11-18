"""Ingest signals, their precision, and the filters they give: never a dismissal.

The labelled fixture (language_fixture.json) is synthetic: postings in English,
German, French and Italian, and fewer in Spanish, Portuguese, Dutch, Polish,
Swedish, Danish, Norwegian and Finnish, with the language they are written in and
the languages they require.
"""

import json
from pathlib import Path

import pytest

from discovery_fixtures import patch_discovery
from openings.actors import OWNER, acting_as, token_actor
from openings.discovery import SourceCreate
from openings.language_signals import language_requirements, posting_language, text_signals
from openings.workspace import Workspace

FIXTURE = json.loads((Path(__file__).with_name("language_fixture.json")).read_text())["items"]
AGENT = token_actor("agent-token", "Synthetic agent", "agent")
# Every language whose postings are recognised.
READ = ("en", "de", "fr", "it", "es", "pt", "nl", "pl", "sv", "da", "no", "fi", "cs", "ro")

# What the detectors must reach on the labelled fixture. Measured when written:
# language 89/89 correct where a language was given (89 of 90 labelled postings),
# required 83/83 correct with 83/83 found. A held-out round of 26 postings written
# before the detectors saw them scored language 25/25 and required 19/20 (recall
# 19/25) on the first run. Sixteen postings in the eight languages added later (two
# each) scored language 16/16 and required 16/16 when written. A language stated
# only as an advantage is not required.
LANGUAGE_PRECISION = 0.95
LANGUAGE_COVERAGE = 0.9
REQUIRED_PRECISION = 0.9
REQUIRED_RECALL = 0.8


def test_language_detection_reaches_the_stated_precision():
    predicted = correct = labelled = 0
    for item in FIXTURE:
        language = text_signals(item["title"], item["posting"])["language"]
        labelled += item["language"] is not None
        if language is not None:
            predicted += 1
            correct += language == item["language"]
    assert labelled >= 80 and {item["language"] for item in FIXTURE} >= set(READ)
    assert correct / predicted >= LANGUAGE_PRECISION, (correct, predicted)
    assert predicted / labelled >= LANGUAGE_COVERAGE, (predicted, labelled)
    # Too little text says nothing.
    assert posting_language("Python developer wanted.") == (None, None)


def test_language_requirement_detection_reaches_the_stated_precision():
    correct = predicted = labelled = 0
    for item in FIXTURE:
        signals = text_signals(item["title"], item["posting"])
        gold = {tuple(g) for g in item["required"]}
        got = {tuple(g) for g in signals["required"]}
        correct += len(gold & got)
        predicted += len(got)
        labelled += len(gold)
    found = (correct, predicted, labelled)
    assert labelled >= 60
    assert correct / predicted >= REQUIRED_PRECISION, found
    assert correct / labelled >= REQUIRED_RECALL, found
    # Phrases that state a requirement, and phrases that only mention a language.
    for text, required in [
        ("Fluent German required, English is a plus.", [["de"]]),
        ("Deutsch C1 und Englisch B2.", [["de"], ["en"]]),
        ("La langue française est exigée.", [["fr"]]),
        ("Richiesta la conoscenza fluente del francese o del tedesco.", [["de", "fr"]]),
        ("Knowledge of the German market is important.", []),
        ("Keine Deutschkenntnisse erforderlich.", []),
        ("Le français n'est pas requis.", []),
        ("Wir betreuen deutsche Kunden.", []),
        # A requirement, an advantage, a negation and alternatives in each language
        # added later, and a name that only describes something else.
        ("Inglés fluido imprescindible.", [["en"]]),
        ("Se valorará el conocimiento de alemán.", []),
        ("No es necesario hablar francés.", []),
        ("Dominio del inglés o del francés.", [["en", "fr"]]),
        ("Trabajamos para el mercado alemán.", []),
        ("Inglês fluente é obrigatório.", [["en"]]),
        ("Espanhol será um diferencial.", []),
        ("Não é necessário falar alemão.", []),
        ("Inglês ou espanhol avançado.", [["en", "es"]]),
        ("Je spreekt vloeiend Nederlands.", [["nl"]]),
        ("Duits is een pluspunt.", []),
        ("Frans is niet vereist.", []),
        ("Engels of Duits is vereist.", [["de", "en"]]),
        ("Uitstekende beheersing van de Nederlandse taal.", [["nl"]]),
        ("Ervaring met connection pools is vereist.", []),
        ("Biegła znajomość języka angielskiego.", [["en"]]),
        ("Mile widziana znajomość języka niemieckiego.", []),
        ("Znajomość języka francuskiego nie jest wymagana.", []),
        ("Język angielski lub niemiecki na poziomie B2.", [["de", "en"]]),
        ("Obsługujemy rynek niemiecki.", []),
        ("Flytande svenska krävs.", [["sv"]]),
        ("Kunskaper i finska är meriterande.", []),
        ("Det är inget krav att kunna norska.", []),
        ("Svenska eller engelska krävs.", [["en", "sv"]]),
        ("Vi har svenska kunder.", []),
        ("Du taler flydende dansk.", [["da"]]),
        ("Kendskab til tysk er en fordel.", []),
        ("Svensk er ikke et krav.", []),
        ("Dansk eller engelsk er et krav.", [["da", "en"]]),
        ("Du snakker flytende norsk.", [["no"]]),
        ("Kunnskaper i svensk er et pluss.", []),
        ("Dansk kreves ikke.", []),
        ("Norsk eller engelsk kreves.", [["en", "no"]]),
        ("Sujuva englannin kielen taito.", [["en"]]),
        ("Ruotsin kielen taito katsotaan eduksi.", []),
        ("Saksan kielen taitoa ei vaadita.", []),
        ("Englanti tai ruotsi on edellytys.", [["en", "sv"]]),
        ("Tunnet Suomen markkinat hyvin.", []),
    ]:
        assert language_requirements(text) == {"required": required}, text


def test_each_added_language_is_told_apart_from_its_neighbours():
    # Every labelled posting in a language added later is read exactly.
    added = [item for item in FIXTURE if item["language"] in READ[4:]]
    assert {item["language"] for item in added} == set(READ[4:])
    for item in added:
        signals = text_signals(item["title"], item["posting"])
        assert signals["language"] == item["language"], item["id"]
        assert sorted(signals["required"]) == sorted(item["required"]), item["id"]
    # The same short posting in languages that share most of their words.
    for language, text in [
        (
            "es",
            (
                "Buscamos una persona para nuestro equipo de datos. Tendrás experiencia con "
                "Python y trabajarás con los analistas en la calidad de los datos. Ofrecemos "
                "un contrato indefinido y un buen ambiente de trabajo."
            ),
        ),
        (
            "pt",
            (
                "Procuramos uma pessoa para a nossa equipe de dados. Você terá experiência com "
                "Python e vai trabalhar com os analistas na qualidade dos dados. Oferecemos um "
                "contrato efetivo e um bom ambiente de trabalho."
            ),
        ),
        (
            "sv",
            (
                "Vi söker en utvecklare till vårt team. Du har erfarenhet av Python och arbetar "
                "nära våra analytiker med kvaliteten på data. Vi erbjuder en fast anställning "
                "och en trevlig arbetsmiljö där du kan växa."
            ),
        ),
        (
            "da",
            (
                "Vi søger en udvikler til vores team. Du har erfaring med Python og arbejder tæt "
                "sammen med vores analytikere om kvaliteten af data. Vi tilbyder en fast "
                "stilling og et godt arbejdsmiljø, hvor du kan udvikle dig."
            ),
        ),
        (
            "no",
            (
                "Vi søker en utvikler til vårt team. Du har erfaring med Python og jobber tett "
                "med analytikerne våre om kvaliteten av data. Vi tilbyr en fast stilling og et "
                "godt arbeidsmiljø der du kan utvikle deg."
            ),
        ),
    ]:
        assert posting_language(text)[0] == language, text


GERMAN = (
    "Wir suchen eine Person für unser Team in Bern. Deine Aufgaben: Du entwickelst neue "
    "Funktionen in Python und arbeitest mit unseren Kunden. Dein Profil: fließend Deutsch "
    "und sehr gute Englischkenntnisse. Wir bieten flexible Arbeitszeiten."
)
ENGLISH = (
    "You will build data pipelines in Python and work with a small team of analysts. "
    "We are looking for three years of experience and fluent English. We offer a yearly "
    "learning budget and flexible hours in our Zurich office. Your days start with a short "
    "planning meeting, then you design, test and run the jobs that load measurement data "
    "into our warehouse, review the changes of your colleagues and help the analysts who "
    "depend on clean, documented tables every week."
)


@pytest.fixture
def services(tmp_path):
    return Workspace(tmp_path / "signals.sqlite")


def job(workspace, title, posting, number, **extra):
    return workspace.ingest_job(
        {
            "title": title,
            "company": extra.pop("company", f"Example {number}"),
            "location": "Zurich, Switzerland",
            "url": f"https://example.test/jobs/{number}",
            "posting": posting,
            **extra,
        }
    )


def test_signals_are_computed_at_ingest_and_follow_the_text(services):
    workspace = services
    first = job(workspace, "Softwareentwickler", GERMAN, 1)
    signals = first["signals"]
    assert signals["computed"] and signals["duplicate_checked"]
    assert signals["language"] == "de" and signals["language_confidence"] > 0.5
    assert signals["required"] == [["de"], ["en"]] and signals["duplicate"] is None
    assert not signals["no_longer_listed"] and "rules" not in signals
    # A refresh that changes the text changes the text signals.
    refreshed = workspace.ingest_job({"url": "https://example.test/jobs/1", "posting": ENGLISH})
    assert refreshed["signals"]["language"] == "en" and refreshed["signals"]["required"] == [["en"]]
    edited = workspace.update_job(
        first["id"], {"expected_version": refreshed["version"], "posting": GERMAN}
    )
    assert edited["signals"]["language"] == "de"
    # The list and the compact summary carry the same signals.
    listed = workspace.list_jobs(posting_language="German")["items"]
    assert [item["id"] for item in listed] == [first["id"]]
    assert workspace.list_jobs(requires="en")["total"] == 1
    assert workspace.list_jobs(posting_language_not="de")["total"] == 0
    assert workspace.list_jobs(signal="language_required")["total"] == 1


def test_a_likely_duplicate_is_flagged_against_the_earlier_job_and_never_merged(services):
    workspace = services
    first = job(workspace, "Data Engineer", ENGLISH, 1, company="Northstar Labs")
    copy = job(workspace, "Data Engineer", ENGLISH, 2, company="Northstar Labs AG")
    other = job(workspace, "Gardener", "Plant trees in the park every morning.", 3)
    assert first["signals"]["duplicate"] is None
    duplicate = copy["signals"]["duplicate"]
    assert duplicate["job_id"] == first["id"] and duplicate["confidence"] >= 0.85
    assert duplicate["tier"] == "high" and other["signals"]["duplicate"] is None
    assert workspace.db.one("SELECT count(*) n FROM jobs")["n"] == 3
    assert [item["id"] for item in workspace.list_jobs(signal="likely_duplicate")["items"]] == [
        copy["id"]
    ]
    # "Different": the flag goes and stays gone when signals are computed again.
    cleared = workspace.mark_distinct(copy["id"], first["id"])
    assert cleared["signals"]["duplicate"] is None
    workspace.db.execute("UPDATE job_signals SET format=0,duplicate_checked=0")
    assert workspace.signals.backfill() == {"text": 3, "duplicates": 3}
    assert workspace.get_job(copy["id"])["signals"]["duplicate"] is None
    assert (
        workspace.db.one("SELECT count(*) n FROM events WHERE kind='duplicate_cleared'")["n"] == 1
    )
    # Merging the earlier job into another keeps flags pointing at the kept record.
    third = job(workspace, "Data Engineer", ENGLISH, 4, company="Northstar Labs")
    assert third["signals"]["duplicate"]["job_id"] == first["id"]
    merged_into = workspace.merge_jobs(
        first["id"], other["id"], workspace.get_job(first["id"])["version"], other["version"]
    )
    assert workspace.get_job(third["id"])["signals"]["duplicate"]["job_id"] == merged_into["id"]


def test_triage_reasons_and_who_dismissed(services):
    workspace = services
    first, second, third = (job(workspace, "Engineer", ENGLISH + str(n), n) for n in (1, 2, 3))
    with acting_as(AGENT):
        result = workspace.bulk_jobs(
            {
                "action": "dismissed",
                "reason": "Junior role; the policy targets senior roles.",
                "items": [{"id": first["id"], "expected_version": first["version"]}],
            }
        )
    assert result["succeeded"] == 1
    dismissal = workspace.get_job(first["id"])["dismissal"]
    assert dismissal["category"] == "agent" and dismissal["reason"].startswith("Junior")
    with acting_as(OWNER):
        owner = workspace.set_triage(second["id"], "dismissed", second["version"], "Too far.")
    assert owner["dismissal"]["category"] == "owner" and owner["dismissal"]["reason"] == "Too far."
    counts = workspace.list_jobs(include_counts=True)["counts"]
    assert counts["dismissed"] == 2 and counts["new"] == 1
    assert counts["dismissed_by"] == {"agent": 1, "owner": 1, "system": 0, "unknown": 0}
    # A dismissal recorded before 0.21 has no author: unknown, not job sources.
    with workspace.db.transaction() as connection:
        connection.execute("UPDATE jobs SET dismissed_by=NULL WHERE id=?", (second["id"],))
    assert workspace.get_job(second["id"])["dismissal"]["category"] == "unknown"
    unknown = workspace.list_jobs(dismissed_by="unknown", include_counts=True)
    assert [job["id"] for job in unknown["items"]] == [second["id"]]
    assert unknown["counts"]["dismissed_by"]["unknown"] == 1
    with pytest.raises(Exception, match="reason"):
        workspace.set_triage(third["id"], "shortlisted", third["version"], "Nice")


def test_a_board_that_stops_listing_a_posting_marks_it_and_dismisses_nothing(
    collection, monkeypatch
):
    workspace, service = collection
    source = service.create_source(
        SourceCreate(name="Example board", kind="greenhouse", config={"board": "example"})
    )
    listed = {"value": ["1", "2", "3"]}

    def collect(snapshot):
        for number in listed["value"]:
            snapshot["on_item"](
                {
                    "title": f"Engineer {number}",
                    "company": "Example",
                    "url": f"https://boards.greenhouse.io/example/jobs/{number}",
                    "source_key": f"greenhouse:example:{number}",
                    "posting": ENGLISH,
                    "metadata": {"ats": "greenhouse", "board": "example", "external_id": number},
                }
            )
        snapshot["streamed"] = True
        snapshot["on_checkpoint"]({"complete": True, "pending_details": 0})
        return []

    patch_discovery(monkeypatch, "fetch_postings", collect)

    def run():
        service.queue_collection(source["id"])
        task = service.claim_task("worker", "collect")
        service.run_task(task, "worker")
        return service.get_task(task["id"])

    assert run()["state"] == "succeeded"
    jobs = {item["title"]: item for item in workspace.list_jobs()["items"]}
    assert not any(item["signals"]["no_longer_listed"] for item in jobs.values())
    workspace.set_triage(jobs["Engineer 3"]["id"], "shortlisted", jobs["Engineer 3"]["version"])
    listed["value"] = ["1"]
    second = run()
    assert second["state"] == "succeeded" and second["result"]["unlisted"] == 2
    after = {item["title"]: item for item in workspace.list_jobs()["items"]}
    assert after["Engineer 2"]["signals"]["no_longer_listed"]
    # A label only: the job stays New.
    assert after["Engineer 2"]["triage"] == "new"
    assert (
        after["Engineer 3"]["triage"] == "shortlisted"
        and after["Engineer 3"]["signals"]["no_longer_listed"]
    )
    assert not after["Engineer 1"]["signals"]["no_longer_listed"]
    # Listed again: the observation is listed again.
    listed["value"] = ["1", "3"]
    run()
    assert not workspace.get_job(after["Engineer 3"]["id"])["signals"]["no_longer_listed"]
    assert workspace.list_jobs(signal="no_longer_listed")["total"] == 1


def test_czech_and_romanian_postings():
    for item in FIXTURE:
        if item["language"] in {"cs", "ro"}:
            assert posting_language(item["posting"])[0] == item["language"], item["id"]
