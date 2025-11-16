# ============================================================================
# Analysis Workflow Step 2: Prepare Data for Geocoding
# ============================================================================
# This script loads the raw data downloaded from the OParl API, extracts
# various types of location information (addresses, parcels, districts),
# and saves the result as a clean, non-spatial dataset ready for geocoding.
#
# Inputs:
#   - data-raw/council_meetings/{city}_agenda.rds
#   - data-raw/council_meetings/{city}_papers.rds
#
# Outputs:
#   - data/{city}_items_for_geocoding.csv
#
# Author: Benedikt Pilgram
# Date: November 2025
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
# NOTE: geocoding.R is not strictly needed here, but sourced for extract_district
source("R/geocoding.R")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

CITY <- "augsburg"
INPUT_DIR <- "data-raw/council_meetings"
OUTPUT_DIR <- "data"

# Input files
agenda_file <- file.path(INPUT_DIR, paste0(CITY, "_agenda.rds"))
papers_file <- file.path(INPUT_DIR, paste0(CITY, "_papers.rds"))

# Output file
output_file_csv <- file.path(OUTPUT_DIR, paste0(CITY, "_items_for_geocoding.csv"))

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Create output directory
if (!dir.exists(OUTPUT_DIR)) {
  dir.create(OUTPUT_DIR, recursive = TRUE)
  cat("✅ Created output directory:", OUTPUT_DIR, "\n\n")
}

# Check for input files
if (!file.exists(agenda_file) || !file.exists(papers_file)) {
  stop("❌ Raw data files not found. Please run '01_download_data.R' first.")
}

print_separator()
cat(" Data Preparation for Geocoding:", toupper(CITY), "\n")
print_separator()
cat("\n")

# --------------------------------------------------------------------------
# Step 1: Load Raw Data
# --------------------------------------------------------------------------

print_section("Loading raw data...", "📂")

agenda_df <- readRDS(agenda_file)
papers_df <- readRDS(papers_file)

cat("✅ Loaded", nrow(agenda_df), "agenda items.\n")
cat("✅ Loaded", nrow(papers_df), "papers.\n\n")

# Combine agenda items and papers into a single dataframe
# Standardize column names for binding
papers_df_renamed <- papers_df %>%
  rename(agenda_item_id = paper_id)

combined_df <- bind_rows(
  agenda_df %>% mutate(source = "agenda"),
  papers_df_renamed %>% mutate(source = "paper")
) %>%
  distinct(agenda_item_id, .keep_all = TRUE) # Remove duplicates

cat("✅ Combined into a single dataset with", nrow(combined_df), "unique items.\n\n")


# --------------------------------------------------------------------------
# Step 2: Comprehensive Location Extraction
# --------------------------------------------------------------------------
print_section("Extracting location information...", "🔍")

# Get regex patterns from the text analysis library
location_patterns <- get_location_patterns()

location_df <- combined_df %>%
  mutate(
    # Extract all patterns in a single pass (more efficient than detect + extract)
    address_match = str_extract(name, regex(location_patterns$address, ignore_case = TRUE)),
    parcel_match = str_extract(name, regex(location_patterns$parcel, ignore_case = TRUE)),
    bplan_match = str_extract(name, regex(location_patterns$bplan, ignore_case = TRUE)),
    district_match = extract_district(name),

    # Derive type from what was actually found (hierarchical priority)
    location_type = case_when(
      !is.na(address_match) ~ "Address",
      !is.na(parcel_match) ~ "Parcel",
      !is.na(bplan_match) ~ "B-Plan",
      !is.na(district_match) ~ "District",
      TRUE ~ NA_character_
    ),

    # Select the appropriate extracted text based on type
    location_text = case_when(
      location_type == "Address" ~ address_match,
      location_type == "Parcel" ~ parcel_match,
      location_type == "B-Plan" ~ bplan_match,
      location_type == "District" ~ district_match,
      TRUE ~ NA_character_
    )
  ) %>%
  select(-address_match, -parcel_match, -bplan_match, -district_match) %>%
  filter(!is.na(location_type)) # Keep only items with some location info

cat("✅ Identified location references in", nrow(location_df), "items.\n")
print(table(location_df$location_type))
cat("\n")


# --------------------------------------------------------------------------
# Step 3: Save for Geocoding
# --------------------------------------------------------------------------
print_section("Saving data for next step...", "💾")

# Select relevant columns and save
location_df %>%
  select(agenda_item_id, name, location_type, location_text, source, everything()) %>%
  write_csv(output_file_csv)

cat("✅ Saved", nrow(location_df), "items for geocoding to:", output_file_csv, "\n\n")


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
print_separator()
cat("✅ DATA PREPARATION COMPLETE\n")
print_separator()
cat("\n")

cat("📊 Summary:\n")
cat("   Total items with location info:", nrow(location_df), "\n")
cat("   Location types found:\n")
print(table(location_df$location_type))
cat("\n")

cat("📁 File saved to:", output_file_csv, "\n\n")

print_separator()
cat("\n🎯 Next step: Run '03_geocode_data.R' to assign coordinates.\n\n")

