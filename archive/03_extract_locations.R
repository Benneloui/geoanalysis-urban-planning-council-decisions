# ============================================================================
# Analysis Workflow Step 3: Extract Location References from Text
# ============================================================================
# This script combines agenda items with papers (containing full PDF text),
# applies regex patterns to identify location references (addresses, parcels,
# B-Plans, districts), and outputs a clean dataset ready for geocoding.
#
# Inputs:
#   - data-raw/council_meetings/{city}_agenda.rds
#   - data-raw/council_meetings/{city}_papers_with_text.rds
#
# Outputs:
#   - data/{city}_items_for_geocoding.csv
#   - data/{city}_unmatched_items.csv (if any items don't match patterns)
#
# Author: Benedikt Pilgram
# Date: November 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(tidyverse)
  library(lubridate)
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

# --------------------------------------------------------------------------
# Logger Configuration
# --------------------------------------------------------------------------
log_dir <- config$dir_logs
if (!dir.exists(log_dir)) dir.create(log_dir)
log_appender(appender_tee(file.path(log_dir, paste0("03_extract_locations_", CITY, ".log"))))
log_threshold(INFO)

# --------------------------------------------------------------------------
# District Lookup Table (for robust matching)
# --------------------------------------------------------------------------
district_lookup <- tibble(
  district = c(
    "Innenstadt", "Antonsviertel", "B\u00e4renkeller", "G\u00f6ggingen", "Haunstetten",
    "Hochfeld", "Kriegshaber", "Lechhausen", "Oberhausen", "Pfersee",
    "Spickel", "Stadtbergen", "Univiertel", "Hammerschmiede", "Bergheim"
  ),
  alias = c(
    "City Center", "Antons", "Baerenkeller", "Goeggingen", "Haunstetten",
    "Hochfeld", "Kriegshaber", "Lechhausen", "Oberhausen", "Pfersee",
    "Spickel", "Stadtbergen", "Univiertel", "Hammerschmiede", "Bergheim"
  )
)

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Input files
agenda_file <- file.path(INPUT_DIR, paste0(CITY, "_agenda.rds"))
papers_with_text_file <- file.path(INPUT_DIR, paste0(CITY, "_papers_with_text.rds"))

# Output files
output_file_csv <- file.path(OUTPUT_DIR, paste0(CITY, "_items_for_geocoding.csv"))
unmatched_file_csv <- file.path(OUTPUT_DIR, paste0(CITY, "_unmatched_items.csv"))

# Create output directory
if (!dir.exists(OUTPUT_DIR)) {
  dir.create(OUTPUT_DIR, recursive = TRUE)
  log_info("Created output directory: {OUTPUT_DIR}")
}

# Check for input files
if (!file.exists(agenda_file)) {
  log_fatal("Agenda file not found: {agenda_file}. Please run '01_download_data.R' first.")
  stop("Agenda file not found: ", agenda_file)
}

if (!file.exists(papers_with_text_file)) {
  log_fatal("Papers with text file not found: {papers_with_text_file}. Please run '02_extract_pdf_text.R' first.")
  stop("Papers with text file not found: ", papers_with_text_file)
}

print_separator()
log_info("Location Extraction from Council Documents: {toupper(CITY)}")
print_separator()

# --------------------------------------------------------------------------
# Step 1: Load Preprocessed Data
# --------------------------------------------------------------------------

print_section("Loading preprocessed data...", "📂")

agenda_df <- readRDS(agenda_file)
papers_with_text_df <- readRDS(papers_with_text_file)

log_info("Loaded {nrow(agenda_df)} agenda items.")
log_info("Loaded {nrow(papers_with_text_df)} papers with extracted text.")
log_info("- {sum(!is.na(papers_with_text_df$full_text))} papers have readable text.")

# --------------------------------------------------------------------------
# Step 2: Combine Data and Prepare Search Text
# --------------------------------------------------------------------------

print_section("Combining data sources...", "🔗")

# Standardize column names for binding
papers_df_renamed <- papers_with_text_df %>%
  rename(agenda_item_id = id)

combined_df <- bind_rows(
  agenda_df %>% mutate(source = "agenda"),
  papers_df_renamed %>% mutate(source = "paper")
) %>%
  distinct(agenda_item_id, .keep_all = TRUE) %>%
  mutate(
    # Create a unified search field
    search_text = paste(name, full_text, sep = " \n ")
  )

log_info("Combined into a single dataset with {nrow(combined_df)} unique items.")

# --------------------------------------------------------------------------
# Step 3: Comprehensive Location Extraction
# --------------------------------------------------------------------------

print_section("Extracting location information from text...", "🔍")

# Get regex patterns from the text analysis library
location_patterns <- get_location_patterns()

# --- Optimized District Matching ---
# 1. Prepare a lookup table in long format for easy mapping
district_long_lookup <- district_lookup %>%
  pivot_longer(cols = c(district, alias), names_to = "type", values_to = "term") %>%
  select(canonical_name = district, term) %>%
  filter(!is.na(term) & term != "") %>%
  mutate(term_lower = tolower(term))

# 2. Create a single, powerful regex from all terms
district_pattern <- paste0("\\b(", paste(district_long_lookup$term, collapse = "|"), ")\\b")

# 3. Create a named vector to serve as a fast hash map
term_to_canonical_map <- setNames(district_long_lookup$canonical_name, district_long_lookup$term_lower)

location_df <- combined_df %>%
  mutate(
    address_match = str_extract(search_text, regex(location_patterns$address, ignore_case = TRUE)),
    parcel_match = str_extract(search_text, regex(location_patterns$parcel, ignore_case = TRUE)),
    bplan_match = str_extract(search_text, regex(location_patterns$bplan, ignore_case = TRUE)),
    # 4. Extract the first match from each text in a single, vectorized operation
    first_match_lower = str_extract(tolower(search_text), tolower(district_pattern)),
    # 5. Map the found terms back to their canonical names
    district_match = unname(term_to_canonical_map[first_match_lower]),

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
  select(-address_match, -parcel_match, -bplan_match, -district_match)

# Log unmatched items for manual review
unmatched_items <- location_df %>% filter(is.na(location_type))
if (nrow(unmatched_items) > 0) {
  write_csv(unmatched_items, unmatched_file_csv)
  log_warn("Logged {nrow(unmatched_items)} unmatched items to: {basename(unmatched_file_csv)}")
  log_info("Review these items for potential new location patterns.")
}

location_df <- location_df %>% filter(!is.na(location_type))

log_info("Identified location references in {nrow(location_df)} items.")

# --------------------------------------------------------------------------
# Step 4: Save for Geocoding
# --------------------------------------------------------------------------

print_section("Saving results...", "💾")

# Select relevant columns and save
location_df %>%
  select(agenda_item_id, name, location_type, location_text, source, everything()) %>%
  write_csv(output_file_csv)

log_info("Saved {nrow(location_df)} items to: {output_file_csv}")

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

print_separator()
log_info("LOCATION EXTRACTION COMPLETE")
print_separator()

log_info("Summary:")
log_info("- Total items with location info: {nrow(location_df)}")
log_info("- Unmatched items: {nrow(unmatched_items)}")

log_info("Location types found:")
location_counts <- table(location_df$location_type)
for (type in names(location_counts)) {
  log_info("- {type}: {location_counts[type]}")
}

log_info("Output file: {output_file_csv}")

print_separator()
log_info("Next step: Run '04_geocode_data.R' to assign coordinates.")

