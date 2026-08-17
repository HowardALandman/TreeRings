#!/usr/bin/env Rscript
# Independent reference parse of .rwl files using dplR::read.rwl.
#
# dplR is the community-standard Tucson-format reader with decades of hardening.
# We use it as an oracle for our own parser: agreement on every series' first
# and last measured year is the acceptance criterion.  Disagreements are bugs to
# investigate, in either implementation.
#
# Usage: Rscript scripts/dplr_reference.R <rwl-dir> <out.csv>
# Output columns: file, series, first, last, n_measured

suppressPackageStartupMessages(library(dplR))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("usage: dplr_reference.R <rwl-dir> <out.csv>")
in_dir <- args[1]
out_csv <- args[2]

files <- list.files(in_dir, pattern = "\\.rwl$", full.names = TRUE)
message(sprintf("dplR %s: reading %d files", packageVersion("dplR"), length(files)))

rows <- list()
failed <- character(0)

for (f in files) {
  # read.rwl is chatty and throws on malformed files; keep going regardless so
  # that a single bad file cannot hide the rest of the comparison.
  rw <- tryCatch(
    suppressWarnings(suppressMessages(read.rwl(f, header = FALSE))),
    error = function(e) NULL
  )
  if (is.null(rw) || ncol(rw) == 0) {
    failed <- c(failed, basename(f))
    next
  }
  years <- as.numeric(rownames(rw))
  for (nm in colnames(rw)) {
    v <- rw[[nm]]
    ok <- which(!is.na(v))
    if (length(ok) == 0) next
    rows[[length(rows) + 1]] <- data.frame(
      file = basename(f),
      series = nm,
      first = years[min(ok)],
      last = years[max(ok)],
      n_measured = length(ok),
      stringsAsFactors = FALSE
    )
  }
}

if (length(failed) > 0) {
  message(sprintf("dplR could not read %d file(s): %s",
                  length(failed), paste(failed, collapse = ", ")))
}

out <- if (length(rows)) do.call(rbind, rows) else
  data.frame(file = character(0), series = character(0),
             first = numeric(0), last = numeric(0), n_measured = numeric(0))

write.csv(out, out_csv, row.names = FALSE)
message(sprintf("wrote %d series to %s", nrow(out), out_csv))
