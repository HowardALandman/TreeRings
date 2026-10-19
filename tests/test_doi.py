"""Which publications a file links to.

The study record is the authority for DOIs and the per-file template is
checked against it.  Cases are taken from the live archive (2026-10-19).
"""

from __future__ import annotations

from ehd.corpus import choose_dois
from ehd.harvest import publication_dois

HARTL = "10.1016/j.dendro.2022.125958"
KUHL = "10.1002/ecs2.4453"


def pub(doi: str) -> dict:
    return {"title": "...", "identifier": {"type": "doi", "id": doi,
                                           "url": "http://dx.doi.org/" + doi}}


def test_record_dois_are_read_from_the_identifier():
    # The shape NCEI sends; the old harvest read a top-level "doi" key that
    # never exists, so it found no DOI in any of 12,629 records.
    assert publication_dois([pub(KUHL), pub(HARTL)]) == [KUHL, HARTL]
    assert publication_dois([{"doi": HARTL, "title": "x"}]) == []


def test_publications_without_a_doi_are_skipped():
    pubs = [{"title": "x", "identifier": None},
            {"title": "y", "identifier": {"type": "url", "id": "http://example.org"}},
            {"title": "z"}, pub(HARTL), pub(HARTL)]
    assert publication_dois(pubs) == [HARTL]


def test_identifier_given_as_a_list_is_read():
    assert publication_dois([{"identifier": [{"type": "DOI", "id": HARTL}]}]) == [HARTL]


def test_template_doi_the_record_does_not_list_is_replaced_and_reported():
    # che419: template says the Prislan sample-preparation protocol; the
    # record lists Kuhl 2023 and Hartl 2022.
    assert choose_dois("10.1016/j.dendro.2022.125959", [KUHL, HARTL]) == (
        [KUHL, HARTL], "10.1016/j.dendro.2022.125959")


def test_template_doi_the_record_confirms_goes_first():
    # che417: template and record agree on Hartl 2022.
    assert choose_dois(HARTL, [KUHL, HARTL]) == ([HARTL, KUHL], "")


def test_agreement_is_case_insensitive_and_ignores_the_resolver():
    # ... and the record's spelling is the one linked.
    assert choose_dois("https://doi.org/" + HARTL.upper(), [HARTL]) == ([HARTL], "")


def test_without_record_dois_the_template_stands_unchecked():
    assert choose_dois(HARTL, []) == ([HARTL], "")
    assert choose_dois("", []) == ([], "")


def test_without_a_template_doi_the_record_is_used():
    assert choose_dois("", [KUHL, HARTL]) == ([KUHL, HARTL], "")


def test_record_order_does_not_matter():
    # The API's publication order varies between calls; the payload must not.
    assert choose_dois("", [HARTL, KUHL]) == choose_dois("", [KUHL, HARTL])
    assert choose_dois("x/1", [HARTL, KUHL]) == choose_dois("x/1", [KUHL, HARTL])
