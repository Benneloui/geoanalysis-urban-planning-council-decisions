# ============================================================================
# Analysis Workflow Step 1: Download Council Data
# ============================================================================
# Downloads council meeting and agenda data from OParl API endpoints.
# Supports multiple cities (Augsburg, Cologne, etc.) via configuration.
#
# Outputs:
#   - data-raw/council_meetings/{city}_meetings.rds
#   - data-raw/council_meetings/{city}_agenda.rds
#   - data-raw/council_meetings/{city}_papers.rds
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(tidyverse)
  library(lubridate)
  library(jsonlite)
})

# Source custom functions
source("R/utils.R")
source("R/oparl_api.R")
source("R/text_analysis.R")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# City to analyze (can be changed or made into command-line argument)
CITY <- "augsburg"  # Options: "augsburg", "cologne", etc.

# OParl endpoints for different cities
OPARL_ENDPOINTS <- list(
  augsburg = "https://www.augsburg.sitzung-online.de/public/oparl/system",
  cologne = "https://ratsinformation.stadt-koeln.de/oparl/system"
  # Add other cities as they become available
)

# Data collection parameters
START_DATE <- "2020-01-01T00:00:00Z"  # RFC3339 format
MAX_PAGES_MEETINGS <- 50    # Increase for full dataset
MAX_PAGES_AGENDA <- 20
MAX_ITEMS <- Inf            # No limit for production
HTTP_TIMEOUT <- 30          # 30 seconds timeout (faster feedback)
RETRY_ATTEMPTS <- 5
RETRY_PAUSE <- 2            # Wait 2 seconds between retries

# Output directory
OUTPUT_DIR <- "data-raw/council_meetings"

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Create output directory
if (!dir.exists(OUTPUT_DIR)) {
  dir.create(OUTPUT_DIR, recursive = TRUE)
  cat("✅ Created output directory:", OUTPUT_DIR, "\n\n")
}

# Validate city selection
if (!CITY %in% names(OPARL_ENDPOINTS)) {
  stop("❌ City '", CITY, "' not found in OPARL_ENDPOINTS configuration")
}

print_separator()
cat("📥 DATA DOWNLOAD: ", toupper(CITY), "\n")
print_separator()
cat("\n")

# --------------------------------------------------------------------------
# Step 1: Connect to OParl API
# --------------------------------------------------------------------------

print_section("Connecting to OParl API...", "🔌")

oparl_url <- OPARL_ENDPOINTS[[CITY]]
system_info <- oparl_connect(oparl_url, timeout_sec = HTTP_TIMEOUT)

cat("✅ Connected to:", system_info$name, "\n")
cat("   OParl Version:", system_info$oparlVersion %||% "Unknown", "\n")
cat("   Endpoint:", oparl_url, "\n\n")

# --------------------------------------------------------------------------
# Step 2: Fetch Political Bodies
# --------------------------------------------------------------------------

print_section("Fetching political bodies...", "🏛️")

bodies <- fetch_bodies(system_info)
body <- bodies[[1]]  # Usually city council is first body

cat("✅ Found body:", body$name, "\n")
cat("   ID:", body$id, "\n\n")

# --------------------------------------------------------------------------
# Step 3: Download Meetings
# --------------------------------------------------------------------------

print_section("Downloading council meetings...", "📅")

meetings_file <- file.path(OUTPUT_DIR, paste0(CITY, "_meetings.rds"))
meetings_raw_file <- file.path(OUTPUT_DIR, paste0(CITY, "_meetings_raw.rds"))

# Check if already downloaded
if (file.exists(meetings_file) && file.exists(meetings_raw_file)) {
  cat("✅ Meetings file already exists, loading from disk...\n")
  meetings_df <- readRDS(meetings_file)
  meetings_list <- readRDS(meetings_raw_file)
  cat("   Loaded", nrow(meetings_df), "meetings from cache\n\n")
} else {
  cat("   Time filter: Since", START_DATE, "\n")
  cat("   Max pages:", MAX_PAGES_MEETINGS, "\n\n")

  # Fetch meetings with time filter
  meetings_list <- oparl_fetch_all(
    body$meeting,
    query = list(modified_since = START_DATE),
    max_pages = MAX_PAGES_MEETINGS,
    max_items = MAX_ITEMS,
    timeout_sec = HTTP_TIMEOUT,
    retries = RETRY_ATTEMPTS,
    pause_sec = RETRY_PAUSE
  )

  # Fallback without filter if needed
  if (length(meetings_list) == 0) {
    cat("⚠️  No meetings with filter. Trying without time filter...\n")
    meetings_list <- oparl_fetch_all(
      body$meeting,
      max_pages = MAX_PAGES_MEETINGS,
      max_items = MAX_ITEMS,
      timeout_sec = HTTP_TIMEOUT,
      retries = RETRY_ATTEMPTS,
      pause_sec = RETRY_PAUSE
    )
  }

  cat("✅ Downloaded", length(meetings_list), "meetings\n")

  # Parse to data frame
  meetings_df <- parse_meetings(meetings_list)

  # Parse dates
  if ("start_date" %in% names(meetings_df)) {
    meetings_df <- meetings_df %>%
      mutate(start_date = ymd_hms(start_date, quiet = TRUE))

    if (any(!is.na(meetings_df$start_date))) {
      date_range <- range(meetings_df$start_date, na.rm = TRUE)
      cat("   Date range:", format(date_range[1], "%Y-%m-%d"), "to",
          format(date_range[2], "%Y-%m-%d"), "\n")
    }
  }

  # Save BOTH parsed data and raw list
  saveRDS(meetings_df, meetings_file)
  saveRDS(meetings_list, meetings_raw_file)
  cat("💾 Saved to:", meetings_file, "\n")
  cat("💾 Saved raw data to:", meetings_raw_file, "\n\n")
}

# --------------------------------------------------------------------------
# Step 4: Download Agenda Items
# --------------------------------------------------------------------------

print_section("Downloading agenda items...", "📋")

agenda_file <- file.path(OUTPUT_DIR, paste0(CITY, "_agenda.rds"))

# Check if already downloaded
if (file.exists(agenda_file)) {
  cat("✅ Agenda file already exists, loading from disk...\n")
  agenda_df <- readRDS(agenda_file)
  cat("   Loaded", nrow(agenda_df), "agenda items from cache\n\n")
} else {
  all_agenda <- list()
  n_meetings_with_agenda <- 0

  # Progress tracking
  cat("   Processing meetings for agenda items...\n")
  pb_step <- max(1, length(meetings_list) %/% 10)  # Show progress every 10%

  for (i in seq_along(meetings_list)) {
    meeting <- meetings_list[[i]]

    # Progress indicator
    if (i %% pb_step == 0) {
      cat("   Progress:", i, "/", length(meetings_list),
          "(", round(100 * i / length(meetings_list)), "%)\n")
    }

    # Check if meeting has agenda items
    if (!is.null(meeting$agendaItem)) {
      # Handle two cases:
      # 1. agendaItem is a URL string → fetch from API
      # 2. agendaItem is a list of objects → already included

      if (is.character(meeting$agendaItem) && length(meeting$agendaItem) == 1) {
        # Case 1: URL - fetch from API
        agenda_list <- tryCatch({
          oparl_fetch_all(
            meeting$agendaItem,
            max_pages = MAX_PAGES_AGENDA,
            max_items = MAX_ITEMS,
            timeout_sec = HTTP_TIMEOUT,
            retries = RETRY_ATTEMPTS,
            pause_sec = RETRY_PAUSE
          )
        }, error = function(e) {
          warning("Failed to fetch agenda for meeting ", meeting$id, ": ", e$message)
          list()
        })
      } else if (is.list(meeting$agendaItem)) {
        # Case 2: Already included as list - use directly
        agenda_list <- meeting$agendaItem
      } else {
        # Unknown format - skip
        next
      }

      if (length(agenda_list) > 0) {
        n_meetings_with_agenda <- n_meetings_with_agenda + 1
        all_agenda <- c(all_agenda, agenda_list)
      }
    }
  }

  cat("\n✅ Found agenda items from", n_meetings_with_agenda, "meetings\n")
  cat("   Total agenda items:", length(all_agenda), "\n")

  # Parse agenda items
  if (length(all_agenda) > 0) {
    agenda_df <- parse_agenda_items(all_agenda)
    saveRDS(agenda_df, agenda_file)
    cat("💾 Saved to:", agenda_file, "\n\n")
  } else {
    cat("⚠️  No agenda items found\n\n")
    agenda_df <- tibble()
  }
}

# --------------------------------------------------------------------------
# Step 5: Download Papers (Optional, for Bebauungsplan search)
# --------------------------------------------------------------------------

print_section("Downloading papers/documents...", "📄")

papers_file <- file.path(OUTPUT_DIR, paste0(CITY, "_papers.rds"))

# Check if already downloaded
if (file.exists(papers_file)) {
  cat("✅ Papers file already exists, loading from disk...\n")
  papers_df <- readRDS(papers_file)
  cat("   Loaded", nrow(papers_df), "papers from cache\n\n")
} else {
  papers_list <- tryCatch({
    oparl_fetch_all(
      body$paper,
      query = list(modified_since = START_DATE),
      max_pages = MAX_PAGES_AGENDA,  # Fewer pages for papers
      max_items = MAX_ITEMS,
      timeout_sec = HTTP_TIMEOUT,
      retries = RETRY_ATTEMPTS,
      pause_sec = RETRY_PAUSE
    )
  }, error = function(e) {
    warning("Failed to fetch papers: ", e$message)
    list()
  })

  cat("✅ Downloaded", length(papers_list), "papers\n")

  if (length(papers_list) > 0) {
    papers_df <- parse_papers(papers_list)
    saveRDS(papers_df, papers_file)
    cat("💾 Saved to:", papers_file, "\n\n")
  } else {
    cat("⚠️  No papers found\n\n")
    papers_df <- tibble()
  }
}

# --------------------------------------------------------------------------
# Step 6: Filter for Bebauungsplan Items (OPTIONAL - can be skipped)
# --------------------------------------------------------------------------

print_section("Filtering for Bebauungsplan references...", "🔍")

bplan_pattern <- create_bplan_pattern()

# Search in agenda items (only if data exists and has 'name' column)
if (exists("agenda_df") && nrow(agenda_df) > 0 && "name" %in% names(agenda_df)) {
  bplan_agenda <- filter_bplan_items(agenda_df, text_column = "name", pattern = bplan_pattern)
  cat("   Agenda items:", nrow(bplan_agenda), "B-Plan references\n")
} else {
  cat("   ⚠️  Agenda items not available or missing 'name' column\n")
  bplan_agenda <- tibble()
}

# Search in papers (only if data exists and has 'name' column)
if (exists("papers_df") && nrow(papers_df) > 0 && "name" %in% names(papers_df)) {
  bplan_papers <- filter_bplan_items(papers_df, text_column = "name", pattern = bplan_pattern)
  cat("   Papers:", nrow(bplan_papers), "B-Plan references\n")
} else {
  cat("   ⚠️  Papers not available or missing 'name' column\n")
  bplan_papers <- tibble()
}

# Combine (only if we have data)
if (nrow(bplan_agenda) > 0 || nrow(bplan_papers) > 0) {
  bplan_all <- bind_rows(
    if (nrow(bplan_agenda) > 0) bplan_agenda %>% mutate(source = "agenda") else NULL,
    if (nrow(bplan_papers) > 0) bplan_papers %>% mutate(source = "paper") else NULL
  )
} else {
  bplan_all <- tibble()
}

cat("\n✅ Total B-Plan references found:", nrow(bplan_all), "\n")

if (nrow(bplan_all) > 0) {
  # Save filtered B-Plan data
  bplan_file <- file.path(OUTPUT_DIR, paste0(CITY, "_bplan_raw.rds"))
  saveRDS(bplan_all, bplan_file)
  cat("💾 Saved to:", bplan_file, "\n\n")

  # Show sample
  cat("📋 Sample B-Plan items:\n")
  print(head(select(bplan_all, name, source), 10))
  cat("\n")
}

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

print_separator()
cat("✅ DATA DOWNLOAD COMPLETE\n")
print_separator()
cat("\n")

cat("📊 Summary:\n")
cat("   Meetings:", nrow(meetings_df), "\n")
cat("   Agenda items:", nrow(agenda_df), "\n")
cat("   Papers:", nrow(papers_df), "\n")
cat("   B-Plan references:", nrow(bplan_all), "\n\n")

cat("📁 Files saved to:", OUTPUT_DIR, "\n")
cat("   -", paste0(CITY, "_meetings.rds"), "\n")
if (nrow(agenda_df) > 0) cat("   -", paste0(CITY, "_agenda.rds"), "\n")
if (nrow(papers_df) > 0) cat("   -", paste0(CITY, "_papers.rds"), "\n")
if (nrow(bplan_all) > 0) cat("   -", paste0(CITY, "_bplan_raw.rds"), "\n")

print_separator()
cat("\n🎯 Next step: Run 02_prepare_geodata.R\n\n")

# --------------------------------------------------------------------------
# Interpretation & Machine-readable Summary
# --------------------------------------------------------------------------

# Re-parse meeting dates robustly (even when loaded from cache)
meeting_dates <- suppressWarnings(ymd_hms(meetings_df$start_date, quiet = TRUE))
has_dates <- any(!is.na(meeting_dates))
date_range <- if (has_dates) range(meeting_dates, na.rm = TRUE) else c(NA, NA)

# B-Plan counts by source (ensure variables exist)
bplan_agenda_n <- if (exists("bplan_agenda")) nrow(bplan_agenda) else 0
bplan_papers_n <- if (exists("bplan_papers")) nrow(bplan_papers) else 0

# Meetings with agenda items (requires meeting_id in parsed agenda)
meetings_with_agenda_n <- if (nrow(agenda_df) > 0 && "meeting_id" %in% names(agenda_df)) {
  dplyr::n_distinct(stats::na.omit(agenda_df$meeting_id))
} else {
  NA_integer_
}

# Compose human-readable interpretation
cat("📝 Interpretation:\n")
cat(" - Meetings:", nrow(meetings_df), "Sitzungen insgesamt")
if (has_dates) {
  cat(
    ", Terminspanne:", format(date_range[1], "%Y-%m-%d"), "bis",
    format(date_range[2], "%Y-%m-%d"), "\n"
  )
} else {
  cat(" (kein gültiges Startdatum verfügbar)\n")
}
cat(
  " - Agenda Items:", nrow(agenda_df),
  if (!is.na(meetings_with_agenda_n)) paste0(" (aus ", meetings_with_agenda_n, " Meetings)") else "",
  "\n"
)
cat(" - Papers:", nrow(papers_df), "Dokumente (OParl 'paper')\n")
cat(
  " - B-Plan-Verweise:", nrow(bplan_all),
  "=", bplan_agenda_n, "(Agenda) +", bplan_papers_n, "(Papers)\n"
)
cat(
  " - Zeitfilter der API-Requests:",
  "modified_since =", START_DATE,
  "(filtert nach Änderungsdatum, nicht zwingend nach Sitzungstermin)\n\n"
)

# Save machine-readable summary (JSON) and a short text report
summary_list <- list(
  city = CITY,
  endpoint = oparl_url,
  modified_since = START_DATE,
  meeting_count = nrow(meetings_df),
  meeting_date_range = list(
    start = if (!is.na(date_range[1])) format(date_range[1], "%Y-%m-%dT%H:%M:%SZ") else NA,
    end = if (!is.na(date_range[2])) format(date_range[2], "%Y-%m-%dT%H:%M:%SZ") else NA
  ),
  agenda_item_count = nrow(agenda_df),
  meetings_with_agenda = meetings_with_agenda_n,
  paper_count = nrow(papers_df),
  bplan = list(
    total = nrow(bplan_all),
    agenda = bplan_agenda_n,
    papers = bplan_papers_n
  ),
  notes = c(
    "Counts reflect data modified since START_DATE (modified_since).",
    "Agenda items may be embedded in meeting objects (no extra API calls).",
    "B-Plan references are text matches, not unique plan numbers."
  )
)

summary_json_path <- file.path(OUTPUT_DIR, paste0(CITY, "_summary.json"))
summary_txt_path <- file.path(OUTPUT_DIR, paste0(CITY, "_summary.txt"))

writeLines(jsonlite::toJSON(summary_list, auto_unbox = TRUE, pretty = TRUE), summary_json_path)

summary_txt <- c(
  paste0("City: ", CITY),
  paste0("Endpoint: ", oparl_url),
  paste0("API modified_since: ", START_DATE, " (filter by modification date)"),
  paste0("Meetings: ", nrow(meetings_df),
         if (has_dates) paste0(" | Date range: ", format(date_range[1], "%Y-%m-%d"),
                               " to ", format(date_range[2], "%Y-%m-%d")) else ""),
  paste0("Agenda items: ", nrow(agenda_df),
         if (!is.na(meetings_with_agenda_n)) paste0(" (from ", meetings_with_agenda_n, " meetings)") else ""),
  paste0("Papers: ", nrow(papers_df)),
  paste0("B-Plan references: ", nrow(bplan_all),
         " (Agenda: ", bplan_agenda_n, ", Papers: ", bplan_papers_n, ")"),
  "Notes:",
  " - 'modified_since' considers modification timestamp, not necessarily meeting date.",
  " - Agenda items can be embedded within meeting responses.",
  " - B-Plan references are text matches, not unique plan IDs."
)

writeLines(summary_txt, summary_txt_path)

cat("🗂️  Summary files saved:\n")
cat("   -", summary_json_path, "\n")
cat("   -", summary_txt_path, "\n\n")
