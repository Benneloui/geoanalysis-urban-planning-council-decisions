# ============================================================================
# LOCAL TEST SCRIPT for Steps 02 & 03
# ============================================================================
# This script is a lightweight, local version of the main data preparation
# pipeline. It runs the combined logic of '02_extract_pdf_text.R' and
# '03_extract_locations.R' on a small, configurable sample of papers.
#
# PURPOSE:
#   - Quickly test changes to PDF parsing or location regex.
#   - Verify the pipeline without processing all documents.
#
# NOTE: This script does NOT need to be run for the main analysis.
# ============================================================================


# Load required libraries
suppressPackageStartupMessages({
  library(tidyverse)
  library(lubridate)
  library(pdftools)
  library(purrr)
  library(tesseract)
  library(furrr)
  library(progressr)
  library(logger)
  library(yaml)
})

# Source custom functions
source("R/utils.R")
source("R/text_analysis.R")

# --------------------------------------------------------------------------
# Load Configuration
# --------------------------------------------------------------------------
config <- yaml::read_yaml("config.yaml")

# Assign config values to variables
CITY <- config$city
INPUT_DIR <- config$dir_raw
OUTPUT_DIR <- config$dir_processed
SAMPLE_SIZE <- config$testing$sample_size

# --------------------------------------------------------------------------
# Logger Configuration
# --------------------------------------------------------------------------
log_dir <- config$dir_logs
if (!dir.exists(log_dir)) dir.create(log_dir)
log_appender(appender_tee(file.path(log_dir, paste0("02_local_test_prepare_data_", CITY, ".log"))))
log_threshold(INFO)

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Input files
agenda_file <- file.path(INPUT_DIR, paste0(CITY, "_agenda.rds"))
papers_file <- file.path(INPUT_DIR, paste0(CITY, "_papers.rds"))

# Test output file
output_file_csv <- file.path(OUTPUT_DIR, "local_test_output.csv")

# Check for input files
if (!file.exists(agenda_file) || !file.exists(papers_file)) {
  log_fatal("Raw data files not found. Please run '01_download_data.R' first.")
  stop("Raw data files not found. Please run '01_download_data.R' first.")
}

print_separator()
log_info("🚀 RUNNING LOCAL TEST PIPELINE 🚀")
log_info("   Processing a sample of {SAMPLE_SIZE} papers.")
print_separator()

# --------------------------------------------------------------------------
# Step 1: Load Raw Data & Take Sample
# --------------------------------------------------------------------------

print_section("Loading raw data and taking sample...", "📂")

agenda_df <- readRDS(agenda_file)
papers_df <- readRDS(papers_file)
# --- This is the key sampling step ---
papers_df <- papers_df[1:min(SAMPLE_SIZE, length(papers_df))]

log_info("Loaded {nrow(agenda_df)} agenda items.")
log_info("Using a sample of {length(papers_df)} papers for testing.")

# --------------------------------------------------------------------------
# Step 2: Extract Full Text from PDFs (Sample)
# --------------------------------------------------------------------------
print_section("Extracting PDF text for sample...", "📄")

# Parallel PDF extraction using furrr
plan(multisession, workers = parallel::detectCores() - 1)

papers_with_text <- papers_df %>%
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

if (nrow(papers_with_text) > 0) {
  with_progress({
    p <- progressor(steps = nrow(papers_with_text))
    papers_with_text$full_text <- future_map_chr(papers_with_text$pdf_url, ~{
      p()
      read_pdf_from_url(.x)
    })
  })
} else {
  papers_with_text$full_text <- character(0)
}

plan(sequential)

log_info("Processed {nrow(papers_with_text)} papers with PDF URLs.")
log_info("Successfully extracted text from {sum(!is.na(papers_with_text$full_text))} PDFs.")


# --------------------------------------------------------------------------
# Step 3: Extract Locations (Sample)
# --------------------------------------------------------------------------
print_section("Combining data and extracting locations from sample...", "🔗")

papers_df_renamed <- papers_with_text %>%
  rename(agenda_item_id = id)

combined_df <- bind_rows(
  agenda_df %>% mutate(source = "agenda"),
  papers_df_renamed %>% mutate(source = "paper")
) %>%
  distinct(agenda_item_id, .keep_all = TRUE) %>%
  mutate(search_text = paste(name, full_text, sep = " \n "))

location_patterns <- get_location_patterns()

location_df <- combined_df %>%
  mutate(
    address_match = str_extract(search_text, regex(location_patterns$address, ignore_case = TRUE)),
    parcel_match = str_extract(search_text, regex(location_patterns$parcel, ignore_case = TRUE)),
    bplan_match = str_extract(search_text, regex(location_patterns$bplan, ignore_case = TRUE)),
    district_match = extract_district(search_text),
    location_type = case_when(
      !is.na(address_match) ~ "Address",
      !is.na(parcel_match) ~ "Parcel",
      !is.na(bplan_match) ~ "B-Plan",
      !is.na(district_match) ~ "District",
      TRUE ~ NA_character_
    ),
    location_text = case_when(
      location_type == "Address" ~ address_match,
      location_type == "Parcel" ~ parcel_match,
      location_type == "B-Plan" ~ bplan_match,
      location_type == "District" ~ district_match,
      TRUE ~ NA_character_
    )
  ) %>%
  select(-address_match, -parcel_match, -bplan_match, -district_match) %>%
  filter(!is.na(location_type))

log_info("Identified location references in {nrow(location_df)} items from the sample data.")

# --------------------------------------------------------------------------
# Step 4: Save Test Output
# --------------------------------------------------------------------------
print_section("Saving test output...", "💾")

location_df %>%
  select(agenda_item_id, name, location_type, location_text, source) %>%
  write_csv(output_file_csv)

log_info("Saved {nrow(location_df)} test items to: {output_file_csv}")

print_separator()
log_info("🎉 LOCAL TEST COMPLETE 🎉")
print_separator()

