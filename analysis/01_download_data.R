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
  library(furrr)
  library(progressr)
  library(httr2)
  library(logger)
  library(yaml)
})

# Source custom functions
source("R/utils.R")
source("R/oparl_api.R")
source("R/text_analysis.R")

# --------------------------------------------------------------------------
# Load Configuration
# --------------------------------------------------------------------------
config <- yaml::read_yaml("config.yaml")

# Assign config values to variables
CITY <- config$city
OPARL_ENDPOINTS <- config$oparl$endpoints
START_DATE <- config$oparl$start_date
MAX_PAGES_MEETINGS <- config$oparl$max_pages_meetings
MAX_PAGES_AGENDA <- config$oparl$max_pages_agenda
HTTP_TIMEOUT <- config$oparl$http_timeout_sec
RETRY_ATTEMPTS <- config$oparl$retry_attempts
RETRY_PAUSE <- config$oparl$retry_pause_sec
OUTPUT_DIR <- config$dir_raw
BATCH_SIZE <- config$processing$paper_download_batch_size

# --------------------------------------------------------------------------
# Logger Configuration
# --------------------------------------------------------------------------
log_dir <- config$dir_logs
if (!dir.exists(log_dir)) dir.create(log_dir)
log_appender(appender_tee(file.path(log_dir, paste0("01_download_data_", CITY, ".log"))))
log_threshold(INFO)

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Create output directory
if (!dir.exists(OUTPUT_DIR)) {
  dir.create(OUTPUT_DIR, recursive = TRUE)
  log_info("Created output directory: {OUTPUT_DIR}")
}

# Validate city selection
if (!CITY %in% names(OPARL_ENDPOINTS)) {
  log_fatal("City '{CITY}' not found in OPARL_ENDPOINTS configuration in config.yaml")
  stop("City not found in config.yaml")
}

print_separator()
log_info("DATA DOWNLOAD: {toupper(CITY)}")
print_separator()

# --------------------------------------------------------------------------
# Step 1: Connect to OParl API
# --------------------------------------------------------------------------

print_section("Connecting to OParl API...", "🔌")

oparl_url <- OPARL_ENDPOINTS[[CITY]]
system_info <- oparl_connect(oparl_url, timeout_sec = HTTP_TIMEOUT)

log_info("Connected to: {system_info$name}")
log_info("OParl Version: {system_info$oparlVersion %||% 'Unknown'}")
log_info("Endpoint: {oparl_url}")

# --------------------------------------------------------------------------
# Step 2: Fetch Political Bodies
# --------------------------------------------------------------------------

print_section("Fetching political bodies...", "🏛️")

bodies <- fetch_bodies(system_info)
body <- bodies[[1]]  # Usually city council is first body

log_info("Found body: {body$name}")
log_info("ID: {body$id}")

# --------------------------------------------------------------------------
# Step 3: Download Meetings
# --------------------------------------------------------------------------

print_section("Downloading council meetings...", "📅")

meetings_file <- file.path(OUTPUT_DIR, paste0(CITY, "_meetings.rds"))
meetings_raw_file <- file.path(OUTPUT_DIR, paste0(CITY, "_meetings_raw.rds"))

# Check if already downloaded
if (file.exists(meetings_file) && file.exists(meetings_raw_file)) {
  log_info("Meetings file already exists, loading from disk...")
  meetings_df <- readRDS(meetings_file)
  meetings_list <- readRDS(meetings_raw_file)
  log_info("Loaded {nrow(meetings_df)} meetings from cache")
} else {
  log_info("Time filter: Since {START_DATE}")
  log_info("Max pages: {MAX_PAGES_MEETINGS}")

  # Fetch meetings with time filter
  meetings_list <- oparl_fetch_all(
    body$meeting,
    query = list(modified_since = START_DATE),
    max_pages = MAX_PAGES_MEETINGS,
    max_items = Inf,
    timeout_sec = HTTP_TIMEOUT,
    retries = RETRY_ATTEMPTS,
    pause_sec = RETRY_PAUSE
  )

  # Fallback without filter if needed
  if (length(meetings_list) == 0) {
    log_warn("No meetings with filter. Trying without time filter...")
    meetings_list <- oparl_fetch_all(
      body$meeting,
      max_pages = MAX_PAGES_MEETINGS,
      max_items = Inf,
      timeout_sec = HTTP_TIMEOUT,
      retries = RETRY_ATTEMPTS,
      pause_sec = RETRY_PAUSE
    )
  }

  log_info("Downloaded {length(meetings_list)} meetings")

  # Parse to data frame
  meetings_df <- parse_meetings(meetings_list)

  # Parse dates
  if ("start_date" %in% names(meetings_df)) {
    meetings_df <- meetings_df %>%
      mutate(start_date = ymd_hms(start_date, quiet = TRUE))

    if (any(!is.na(meetings_df$start_date))) {
      date_range <- range(meetings_df$start_date, na.rm = TRUE)
      log_info("Date range: {format(date_range[1], '%Y-%m-%d')} to {format(date_range[2], '%Y-%m-%d')}")
    }
  }

  # Save BOTH parsed data and raw list
  saveRDS(meetings_df, meetings_file)
  saveRDS(meetings_list, meetings_raw_file)
  log_info("Saved to: {meetings_file}")
  log_info("Saved raw data to: {meetings_raw_file}")
}

# --------------------------------------------------------------------------
# Step 4: Download Agenda Items
# --------------------------------------------------------------------------

print_section("Downloading agenda items...", "📋")

agenda_file <- file.path(OUTPUT_DIR, paste0(CITY, "_agenda.rds"))

# Check if already downloaded
if (file.exists(agenda_file)) {
  log_info("Agenda file already exists, loading from disk...")
  agenda_df <- readRDS(agenda_file)
  log_info("Loaded {nrow(agenda_df)} agenda items from cache")
} else {
  all_agenda <- list()
  n_meetings_with_agenda <- 0

  # Progress tracking
  log_info("Processing meetings for agenda items...")
  pb_step <- max(1, length(meetings_list) %/% 10)  # Show progress every 10%

  for (i in seq_along(meetings_list)) {
    meeting <- meetings_list[[i]]

    # Progress indicator
    if (i %% pb_step == 0) {
      log_info("Progress: {i}/{length(meetings_list)} ({round(100 * i / length(meetings_list))}%)")
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
            max_items = Inf,
            timeout_sec = HTTP_TIMEOUT,
            retries = RETRY_ATTEMPTS,
            pause_sec = RETRY_PAUSE
          )
        }, error = function(e) {
          log_warn("Failed to fetch agenda for meeting {meeting$id}: {e$message}")
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

  log_info("Found agenda items from {n_meetings_with_agenda} meetings")
  log_info("Total agenda items: {length(all_agenda)}")

  # Parse agenda items
  if (length(all_agenda) > 0) {
    agenda_df <- parse_agenda_items(all_agenda)
    saveRDS(agenda_df, agenda_file)
    log_info("Saved to: {agenda_file}")
  } else {
    log_warn("No agenda items found")
    agenda_df <- tibble()
  }
}

# --------------------------------------------------------------------------
# Step 5: Download Papers (Full Details)
# --------------------------------------------------------------------------
print_section("Downloading papers/documents (full details)...", "📄")

# Initialize papers_df early to avoid missing object errors
papers_df <- tibble()

papers_file <- file.path(OUTPUT_DIR, paste0(CITY, "_papers.rds"))

# Check if already downloaded
if (file.exists(papers_file)) {
  log_info("Papers file already exists, loading from disk...")
  # Load the full JSON objects
  papers_list_full <- readRDS(papers_file)
  log_info("Loaded {length(papers_list_full)} full paper objects from cache")

  # Create papers_df for compatibility using the centralized function from R/oparl_api.R
  papers_df <- parse_papers(papers_list_full)
  log_info("Created papers_df with {nrow(papers_df)} rows")

  # Extract paper_urls for summary statistics
  paper_urls <- purrr::map_chr(papers_list_full, "id")
} else {
  # Step 5.1: Fetch the summary list of all papers to get their URLs
  log_info("Fetching summary list of all papers...")
  papers_summary_list <- tryCatch({
    oparl_fetch_all(
      body$paper,
      query = list(modified_since = START_DATE),
      max_pages = Inf, # Get all pages for the summary
      max_items = Inf,
      timeout_sec = HTTP_TIMEOUT,
      retries = RETRY_ATTEMPTS,
      pause_sec = RETRY_PAUSE
    )
  }, error = function(e) {
    log_warn("Failed to fetch summary list of papers: {e$message}")
    list()
  })

  if (length(papers_summary_list) == 0) {
    log_fatal("No papers found in the summary list. Cannot proceed.")
    stop("No papers found in the summary list. Cannot proceed.")
  }

  # Extract the detail URLs. The URL is simply the 'id' field of each paper.
  paper_urls <- purrr::map_chr(papers_summary_list, "id")
  log_info("Found {length(paper_urls)} papers in the summary list.")

  # NEW: Deduplicate paper URLs to avoid redundant API calls
  initial_paper_urls_count <- length(paper_urls)
  paper_urls <- unique(paper_urls)
  if (length(paper_urls) < initial_paper_urls_count) {
    log_info("Removed {initial_paper_urls_count - length(paper_urls)} duplicate paper URLs.")
  }
  log_info("Processing {length(paper_urls)} unique paper URLs.")

    # Step 5.2: Fetch the full details for each paper in parallel and in batches
    log_info("Fetching full details for each paper in parallel... (this may take a while)")

    # --- Configuration for batch processing ---
    paper_url_batches <- split(paper_urls, ceiling(seq_along(paper_urls) / BATCH_SIZE))
    temp_file_paths <- c()
    all_failed_urls <- c()

    # Setup parallel processing
    plan(multisession, workers = parallel::detectCores() - 1)

    # Define a safe function to get details for a single URL, using httr2
    # This function now also checks for the presence of a PDF.
    fetch_paper_details <- function(url) {
      # Add a small delay to be polite to the API
      Sys.sleep(runif(1, 0.5, 2.0))

      # Build the request object with retry and timeout policies using httr2
      req <- request(url) %>%
        req_retry(max_tries = RETRY_ATTEMPTS, backoff = ~RETRY_PAUSE) %>%
        req_timeout(HTTP_TIMEOUT)

      tryCatch({
        resp <- req_perform(req)
        json_data <- resp_body_json(resp, simplifyVector = FALSE)

        # NEW: Check for PDF link right after download
        has_pdf <- !is.null(json_data$mainFile$accessUrl) || !is.null(json_data$file[[1]]$accessUrl)

        if (has_pdf) {
          # Success and has PDF: return full data
          list(success = TRUE, data = json_data)
        } else {
          # Success but no PDF: return NULL to be filtered out
          NULL
        }

      }, error = function(e) {
        # This block is executed only if all retries fail.
        log_warn("All {RETRY_ATTEMPTS} attempts failed for URL: {url}. Final error: {e$message}")
        list(success = FALSE, url = url)
      })
    }

    # --- Loop over batches ---
    for (i in seq_along(paper_url_batches)) {
      batch_urls <- paper_url_batches[[i]]
      log_info("--- Processing Batch {i}/{length(paper_url_batches)} ({length(batch_urls)} papers) ---")

      # Use future_map with a progress bar for the current batch
      with_progress({
        p <- progressor(steps = length(batch_urls))
        results_list <- future_map(batch_urls, ~{
          p() # Increment progress bar
          fetch_paper_details(.x)
        })
      })

      # NEW: Filter out NULLs from papers that were successfully downloaded but had no PDF
      results_list <- results_list[!sapply(results_list, is.null)]

      # Process results for the batch (now only contains success/failure objects)
      is_success <- purrr::map_lgl(results_list, "success")
      batch_success_list <- purrr::map(results_list[is_success], "data")
      batch_failed_urls <- purrr::map_chr(results_list[!is_success], "url")

      # Save intermediate results if any were successful
      if (length(batch_success_list) > 0) {
        temp_file <- tempfile(pattern = paste0("papers_batch_", i, "_"), tmpdir = OUTPUT_DIR, fileext = ".rds")
        saveRDS(batch_success_list, temp_file)
        temp_file_paths <- c(temp_file_paths, temp_file)
        log_info("Batch {i} complete. Saved {length(batch_success_list)} papers (with PDFs) to temporary file.")
      }

      # Collect failed URLs
      if (length(batch_failed_urls) > 0) {
        all_failed_urls <- c(all_failed_urls, batch_failed_urls)
      }
    }

    # --- Post-loop processing ---
    log_info("--- Combining all batches ---")

    # Read and combine all temporary files
    papers_list_full <- purrr::map(temp_file_paths, readRDS) %>% purrr::flatten()

    # Clean up temporary files
    unlink(temp_file_paths)
    log_info("Combined {length(papers_list_full)} papers from {length(temp_file_paths)} batch files. Temporary files removed.")

    # Handle and save all collected failed URLs
    if (length(all_failed_urls) > 0) {
      failed_urls_file <- file.path(OUTPUT_DIR, paste0(CITY, "_failed_paper_urls.txt"))
      writeLines(all_failed_urls, failed_urls_file)
      log_warn("Failed to fetch {length(all_failed_urls)} papers. URLs saved to {basename(failed_urls_file)}")
    }

    # The explicit filtering step is no longer needed here, as it was done in the fetch function.
    # For clarity, we'll just announce the final count.
    log_info("Total papers with PDFs to be saved: {length(papers_list_full)}")

        # For compatibility with the rest of the script, create a simple papers_df
        # This now uses the centralized function from R/oparl_api.R
        papers_df <- parse_papers(papers_list_full)
}

# --------------------------------------------------------------------------
# Step 6: Filter for Bebauungsplan Items (OPTIONAL - can be skipped)
# --------------------------------------------------------------------------

print_section("Filtering for Bebauungsplan references...", "🔍")

# Initialize bplan_all early to avoid missing object errors
bplan_all <- tibble()

bplan_pattern <- create_bplan_pattern()

# Search in agenda items (only if data exists and has 'name' column)
if (exists("agenda_df") && nrow(agenda_df) > 0 && "name" %in% names(agenda_df)) {
  bplan_agenda <- filter_bplan_items(agenda_df, text_column = "name", pattern = bplan_pattern)
  log_info("Agenda items: {nrow(bplan_agenda)} B-Plan references")
} else {
  log_warn("Agenda items not available or missing 'name' column")
  bplan_agenda <- tibble()
}

# Search in papers (only if data exists and has 'name' column)
if (exists("papers_df") && nrow(papers_df) > 0 && "name" %in% names(papers_df)) {
  bplan_papers <- filter_bplan_items(papers_df, text_column = "name", pattern = bplan_pattern)
  log_info("Papers: {nrow(bplan_papers)} B-Plan references")
} else {
  log_warn("Papers not available or missing 'name' column")
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

log_info("Total B-Plan references found: {nrow(bplan_all)}")

if (nrow(bplan_all) > 0) {
  # Save filtered B-Plan data
  bplan_file <- file.path(OUTPUT_DIR, paste0(CITY, "_bplan_raw.rds"))
  saveRDS(bplan_all, bplan_file)
  log_info("Saved to: {bplan_file}")

  # Show sample
  log_info("Sample B-Plan items:")
  log_info(paste(capture.output(print(head(select(bplan_all, name, source), 10))), collapse = "\n"))
}

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

print_separator()
log_info("DATA DOWNLOAD COMPLETE")
print_separator()

log_info("Summary:")
log_info("- Meetings: {nrow(meetings_df)}")
log_info("- Agenda items: {nrow(agenda_df)}")
log_info("- Papers: {nrow(papers_df)}")
log_info("- B-Plan references: {nrow(bplan_all)}")

log_info("Files saved to: {OUTPUT_DIR}")
log_info("- {paste0(CITY, '_meetings.rds')}")
if (nrow(agenda_df) > 0) log_info("- {paste0(CITY, '_agenda.rds')}")
if (nrow(papers_df) > 0) log_info("- {paste0(CITY, '_papers.rds')}")
if (nrow(bplan_all) > 0) log_info("- {paste0(CITY, '_bplan_raw.rds')}")

print_separator()
log_info("Next step: Run 02_extract_pdf_text.R")

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
log_info("--- Interpretation ---")
log_info("- Meetings: {nrow(meetings_df)} total sessions{if (has_dates) paste0(', date range: ', format(date_range[1], '%Y-%m-%d'), ' to ', format(date_range[2], '%Y-%m-%d')) else ' (no valid start date available)'}")
log_info("- Agenda Items: {nrow(agenda_df)}{if (!is.na(meetings_with_agenda_n)) paste0(' (from ', meetings_with_agenda_n, ' meetings)') else ''}")
log_info("- Papers: {nrow(papers_df)} documents (OParl 'paper')")
log_info("- B-Plan references: {nrow(bplan_all)} = {bplan_agenda_n} (Agenda) + {bplan_papers_n} (Papers)")
log_info("- API request time filter: modified_since = {START_DATE} (filters by modification date, not necessarily meeting date)")

# Save machine-readable summary (JSON)
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
writeLines(jsonlite::toJSON(summary_list, auto_unbox = TRUE, pretty = TRUE), summary_json_path)

log_info("Summary JSON file saved: {summary_json_path}")

