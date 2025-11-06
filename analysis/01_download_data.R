# ============================================================================
# Analysis Workflow Step 1: Download Council Data
# ============================================================================
# Downloads council meeting and agenda data from OParl API endpoints.
# Supports multiple cities (Cologne, Augsburg, etc.) via configuration.
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
})

# Source custom functions
source("R/utils.R")
source("R/oparl_api.R")
source("R/text_analysis.R")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# City to analyze (can be changed or made into command-line argument)
CITY <- "cologne"  # Options: "cologne", "augsburg", etc.

# OParl endpoints for different cities
OPARL_ENDPOINTS <- list(
  cologne = "https://ratsinformation.stadt-koeln.de/oparl/system",
  # Add other cities as they become available:
  # augsburg = "https://example.com/oparl/system"
)

# Data collection parameters
START_DATE <- "2020-01-01T00:00:00Z"  # RFC3339 format
MAX_PAGES_MEETINGS <- 50    # Increase for full dataset
MAX_PAGES_AGENDA <- 20
MAX_ITEMS <- Inf            # No limit for production
HTTP_TIMEOUT <- 30
RETRY_ATTEMPTS <- 5

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

cat("   Time filter: Since", START_DATE, "\n")
cat("   Max pages:", MAX_PAGES_MEETINGS, "\n\n")

# Fetch meetings with time filter
meetings_list <- oparl_fetch_all(
  body$meeting,
  query = list(modified_since = START_DATE),
  max_pages = MAX_PAGES_MEETINGS,
  max_items = MAX_ITEMS,
  timeout_sec = HTTP_TIMEOUT,
  retries = RETRY_ATTEMPTS
)

# Fallback without filter if needed
if (length(meetings_list) == 0) {
  cat("⚠️  No meetings with filter. Trying without time filter...\n")
  meetings_list <- oparl_fetch_all(
    body$meeting,
    max_pages = MAX_PAGES_MEETINGS,
    max_items = MAX_ITEMS,
    timeout_sec = HTTP_TIMEOUT,
    retries = RETRY_ATTEMPTS
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

# Save meetings data
meetings_file <- file.path(OUTPUT_DIR, paste0(CITY, "_meetings.rds"))
saveRDS(meetings_df, meetings_file)
cat("💾 Saved to:", meetings_file, "\n\n")

# --------------------------------------------------------------------------
# Step 4: Download Agenda Items
# --------------------------------------------------------------------------

print_section("Downloading agenda items...", "📋")

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
    agenda_list <- tryCatch({
      oparl_fetch_all(
        meeting$agendaItem,
        max_pages = MAX_PAGES_AGENDA,
        max_items = MAX_ITEMS,
        timeout_sec = HTTP_TIMEOUT,
        retries = RETRY_ATTEMPTS
      )
    }, error = function(e) {
      warning("Failed to fetch agenda for meeting ", meeting$id, ": ", e$message)
      list()
    })

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

  # Save agenda data
  agenda_file <- file.path(OUTPUT_DIR, paste0(CITY, "_agenda.rds"))
  saveRDS(agenda_df, agenda_file)
  cat("💾 Saved to:", agenda_file, "\n\n")
} else {
  cat("⚠️  No agenda items found\n\n")
  agenda_df <- tibble()
}

# --------------------------------------------------------------------------
# Step 5: Download Papers (Optional, for Bebauungsplan search)
# --------------------------------------------------------------------------

print_section("Downloading papers/documents...", "📄")

papers_list <- tryCatch({
  oparl_fetch_all(
    body$paper,
    query = list(modified_since = START_DATE),
    max_pages = MAX_PAGES_AGENDA,  # Fewer pages for papers
    max_items = MAX_ITEMS,
    timeout_sec = HTTP_TIMEOUT,
    retries = RETRY_ATTEMPTS
  )
}, error = function(e) {
  warning("Failed to fetch papers: ", e$message)
  list()
})

cat("✅ Downloaded", length(papers_list), "papers\n")

if (length(papers_list) > 0) {
  papers_df <- parse_papers(papers_list)

  # Save papers data
  papers_file <- file.path(OUTPUT_DIR, paste0(CITY, "_papers.rds"))
  saveRDS(papers_df, papers_file)
  cat("💾 Saved to:", papers_file, "\n\n")
} else {
  cat("⚠️  No papers found\n\n")
  papers_df <- tibble()
}

# --------------------------------------------------------------------------
# Step 6: Filter for Bebauungsplan Items
# --------------------------------------------------------------------------

print_section("Filtering for Bebauungsplan references...", "🔍")

bplan_pattern <- create_bplan_pattern()

# Search in agenda items
bplan_agenda <- filter_bplan_items(agenda_df, text_column = "name", pattern = bplan_pattern)
cat("   Agenda items:", nrow(bplan_agenda), "B-Plan references\n")

# Search in papers
bplan_papers <- filter_bplan_items(papers_df, text_column = "name", pattern = bplan_pattern)
cat("   Papers:", nrow(bplan_papers), "B-Plan references\n")

# Combine
bplan_all <- bind_rows(
  bplan_agenda %>% mutate(source = "agenda"),
  bplan_papers %>% mutate(source = "paper")
)

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
