# ============================================================================
# Analysis Workflow Step 2: Extract Text from PDFs
# ============================================================================
# This script loads the raw 'papers' data, downloads the associated PDF for
# each paper, extracts the full text using pdftools (with an OCR fallback),
# and saves the enriched dataset.
#
# Inputs:
#   - data-raw/council_meetings/{city}_papers.rds
#
# Outputs:
#   - data-raw/council_meetings/{city}_papers_with_text.rds
#
# Author: Benedikt Pilgram
# Date: November 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(tidyverse)
  library(pdftools)
  library(purrr)
  library(tesseract) # For OCR fallback
  library(furrr)     # For parallel processing
  library(progressr) # For progress bars
  library(logger)
  library(yaml)
})

# Source custom functions (only utils needed for now)
source("R/utils.R")

# --------------------------------------------------------------------------
# Load Configuration
# --------------------------------------------------------------------------
config <- yaml::read_yaml("config.yaml")

# Assign config values to variables
CITY <- config$city
INPUT_DIR <- config$dir_raw
OUTPUT_DIR <- config$dir_raw # Keep intermediate data in data-raw
BATCH_SIZE <- config$processing$pdf_extraction_batch_size

# --------------------------------------------------------------------------
# Logger Configuration
# --------------------------------------------------------------------------
log_dir <- config$dir_logs
if (!dir.exists(log_dir)) dir.create(log_dir)
log_appender(appender_tee(file.path(log_dir, paste0("02_extract_pdf_text_", CITY, ".log"))))
log_threshold(INFO)

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Input file
papers_file <- file.path(INPUT_DIR, paste0(CITY, "_papers.rds"))

# Output file
output_file_rds <- file.path(OUTPUT_DIR, paste0(CITY, "_papers_with_text.rds"))

# Check for input file
if (!file.exists(papers_file)) {
  log_fatal("Raw papers file not found: {papers_file}. Please run '01_download_data.R' first.")
  stop("Raw papers file not found. Please run '01_download_data.R' first.")
}

print_separator()
log_info("PDF Text Extraction: {toupper(CITY)}")
print_separator()

# --------------------------------------------------------------------------
# Step 1: Load Raw Papers Data
# --------------------------------------------------------------------------

print_section("Loading raw papers data...", "📂")

papers_list <- readRDS(papers_file)
log_info("Loaded {length(papers_list)} raw paper objects.")

# Deduplicate based on paper ID to avoid processing the same paper multiple times
initial_count <- length(papers_list)
# The raw data is a list of lists, so we need to unnest or extract IDs first.
# A robust way is to get the IDs, find the unique ones, and filter the list.
paper_ids <- purrr::map_chr(papers_list, "id")
unique_paper_indices <- which(!duplicated(paper_ids))
papers_list <- papers_list[unique_paper_indices]

if (length(papers_list) < initial_count) {
  log_info("Removed {initial_count - length(papers_list)} duplicate paper objects.")
}
log_info("Processing {length(papers_list)} unique papers.")

# --------------------------------------------------------------------------
# Step 2: Extract Full Text from PDFs in Batches
# --------------------------------------------------------------------------
print_section("Extracting full text from linked PDFs (parallel, in batches)...", "📄")

# First, create the dataframe with the pdf_url for all papers
papers_with_urls <- papers_list %>%
  map_dfr(~tibble(
    id = .x$id,
    mainFile = list(.x$mainFile),
    file = list(.x$file)
  )) %>%
  mutate(
    pdf_url = map_chr(mainFile, ~ .x$accessUrl, .default = NA_character_),
    pdf_url = ifelse(is.na(pdf_url), map_chr(file, ~ .x[[1]]$accessUrl, .default = NA_character_), pdf_url)
  ) %>%
  filter(!is.na(pdf_url))

# --- Configuration for batch processing ---
paper_batches <- papers_with_urls %>%
  mutate(batch_id = ceiling(row_number() / BATCH_SIZE)) %>%
  group_split(batch_id)

processed_batches <- list()

# Setup parallel processing backend
plan(multisession, workers = parallel::detectCores() - 1)

# --- Loop over batches ---
for (i in seq_along(paper_batches)) {
  current_batch <- paper_batches[[i]]
  log_info("--- Processing PDF Batch {i}/{length(paper_batches)} ({nrow(current_batch)} PDFs) ---")

  batch_results <- tryCatch({
    # Use future_map with a progress bar for the current batch
    with_progress({
      p <- progressor(steps = nrow(current_batch))
      # Safely apply the function and store results
      full_text_results <- future_map_chr(current_batch$pdf_url, ~{
        p()
        read_pdf_from_url(.x)
      })
      current_batch$full_text <- full_text_results
    })
    current_batch # Return the processed batch if successful
  }, error = function(e) {
    log_warn("Batch {i} failed with error: {e$message}. Skipping this batch.")
    current_batch$full_text <- NA_character_ # Assign NA to full_text for failed batch
    current_batch # Return batch with NA full_text
  })
  
  processed_batches[[i]] <- batch_results
  log_info("Batch {i} complete. Extracted text from {sum(!is.na(batch_results$full_text))} PDFs.")
}

# Close the parallel backend
plan(sequential)

# Combine all processed batches into a single dataframe
papers_with_text <- bind_rows(processed_batches)

log_info("Processed a total of {nrow(papers_with_text)} papers with PDF URLs.")
log_info("Successfully extracted text from {sum(!is.na(papers_with_text$full_text))} PDFs.")


# --------------------------------------------------------------------------
# Step 3: Save Enriched Data
# --------------------------------------------------------------------------
print_section("Saving enriched paper data...", "💾")

saveRDS(papers_with_text, output_file_rds)

log_info("Saved {nrow(papers_with_text)} papers with extracted text to: {output_file_rds}")


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
print_separator()
log_info("PDF TEXT EXTRACTION COMPLETE")
print_separator()

log_info("Summary:")
log_info("- Total papers with PDF URLs: {nrow(papers_with_text)}")
log_info("- Papers with readable text: {sum(!is.na(papers_with_text$full_text))}")

log_info("Output file: {output_file_rds}")

print_separator()
log_info("Next step: Run '03_extract_locations.R' to identify location references.")


