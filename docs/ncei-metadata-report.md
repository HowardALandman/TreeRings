To: paleo@noaa.gov
Subject: Three declared-span errors in European ITRDB study records (BRIT101, NETH005, BRIT)

Hello,

I'm working on an independent visualisation of individual logs in the European
ITRDB measurement collections, which meant parsing all 2,061 deduplicated .rwl
files under measurements/europe/ and checking each file's data against the span
declared for it. The parser is cross-validated against dplR: 100.0000% span
agreement on the 65,154 series dplR reads, 0 disagreements.

Three collections came out with a declared span that cannot be reconciled with
the archived measurements. All three were re-checked against the live records
on 18 August 2026.

1. BRIT101 — Tyers, Mill Lodge Farm, Great Ryburgh
   https://www.ncei.noaa.gov/access/paleo-search/study/44081
   Study record: earliestYear 271, mostRecentYear 276.
   brit101.rwl: header line 2 ends "271 726", and the 11 series measure
   271-726 CE (latest ring GR2826 at 726).
   This looks like a transposition of 726. The NOAA template file
   brit101-rwl-noaa.txt carries no Earliest_Year/Most_Recent_Year fields, so
   the value appears to exist only in the study record. The .rwl file itself is
   correct and needs no change.
   Suggested: Most_Recent_Year 276 -> 726.

2. NETH005 — Jansma & van Rijn, Empel Village
   https://www.ncei.noaa.gov/access/paleo-search/study/3626
   Study record: earliestYear -66, mostRecentYear 106. neth005-rwl-noaa.txt
   declares the same, with Time_Unit: AD.
   neth005.rwl: the 9 series measure 1834-2006 CE — e.g. EMP041 runs 1881-1978,
   EMP051 begins 1845, EMP161 ends 1932.
   The offset is exactly 1900 years. I'd note that -66 to 106 CE is entirely
   plausible for the Roman-period site, so the alternative reading is that the
   record describes material other than what neth005.rwl actually holds. Either
   way the two do not correspond.

3. BRIT — Pilcher, Rostrevor
   https://www.ncei.noaa.gov/access/paleo-search/study/4225
   Study record and brit-rwl-noaa.txt: 1750-1975, Time_Unit: AD. The .rwl
   header line 2 ends "1750 1975" as well.
   brit.rwl: the 14 series measure 812-1458 CE.
   This file also appears to combine more than one collection: the series IDs
   carry three different site codes with distinct ranges — 346 (Rostrevor)
   902-1203, 347 at 1131-1458, and 348 at 812-1080. The header describes 346
   only, and its declared span matches none of the three.

One question, which is the reason I was comparing spans in the first place.
Are Earliest_Year and Most_Recent_Year defined as the extent of the archived
measurement data, or as the span of the site chronology? Many collections
declare a span narrower than their own .rwl file — FRAN10, for instance,
declares 1943-1975 and measures 1747-1988 — and I now treat that as normal
rather than as an error. Confirmation either way would be useful, and if it is
meant to be the data extent I can send the full list of collections where the
two disagree.

Thanks for maintaining the archive — the corpus has been a pleasure to work
with, traps and all.

Best regards,
Howard Landman
