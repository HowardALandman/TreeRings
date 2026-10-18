"""Which colour a collection is drawn in.

The taxon used to come from the four-letter code in the NCEI study *title*.
AUST115's title says QUPE, sessile oak; its 588 series are *Pinus nigra* by
every other account - the template's Species_Name and Tree_Species_Code
(PILR), the Tucson header ("Austrian pine"), the series ids (``At2Pn*``,
beside the ISONET oak site AUST114's ``At1Qp*``), and the Strumia black-pine
series it contains.  They were drawn as oak.

The template's Latin name now decides.  Where it and the code disagreed it was
right every time, so these are the cases pinned.
"""

from __future__ import annotations

import pytest

from ehd.corpus import classify, read_noaa_header


@pytest.mark.parametrize(
    "site,code,latin,genus,group",
    [
        ("aust115", "QUPE", "Pinus laricio Poir. = Pinus nigra", "Pinus", "pine"),
        # PIAB is not an ITRDB code; its first two letters read as Pinus.
        ("ita063", "PIAB", "Picea abies (L.) H. Karst.", "Picea", "spruce"),
        # PT is Platanus in the code table; the tree is mastic.
        ("ital029", "PTLE", "Pistacia lentiscus  L.", "Pistacia", "other"),
        # Agreement is unchanged.
        ("neth001", "QUSP", "Quercus sp.", "Quercus", "oak"),
        # Codes the table never knew still get their genus from the name.
        ("ital044", "HEHE", "Hedera helix\xa0L.", "Hedera", "other"),
    ],
)
def test_latin_name_decides(site, code, latin, genus, group):
    assert classify(code, latin) == (genus, group), site


def test_code_is_the_fallback_without_a_latin_name():
    assert classify("QURO") == ("Quercus", "oak")
    assert classify("PCAB", "") == ("Picea", "spruce")
    assert classify("") == ("", "other")


def test_template_species_code_is_read(tmp_path):
    # AUST115's maintained template, the lines that matter.
    path = tmp_path / "aust115-rwl-noaa.txt"
    path.write_text(
        "#   Study_Name: Gutiérrez - Poellau - QUPE - ITRDB AUST115\n"
        "#   Species_Name: Pinus laricio Poir. = Pinus nigra\n"
        "#   Common_Name: None\n"
        "#   Tree_Species_Code: PILR\n"
    )
    meta = read_noaa_header(str(path))
    assert meta["species_code"] == "PILR"
    assert classify(meta["species_code"], meta["species_name"])[1] == "pine"
