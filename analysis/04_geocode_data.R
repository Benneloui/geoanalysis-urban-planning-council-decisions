# ============================================================================
# Analysis Workflow Step 4: Geocode Prepared Data
# ============================================================================
# This script loads the prepared data, geocodes it using a hierarchical
# strategy (addresses first, then districts), and saves the result as a
# clean, spatial dataset.
#
# Inputs:
#   - data/{city}_items_for_geocoding.csv
#
# Outputs:
#   - data/{city}_geocoded_items.gpkg
#   - data/{city}_geocoded_items.csv (for inspection)
#
# Author: Benedikt Pilgram
# Date: November 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(tidyverse)
  library(sf)
  library(logger)
  library(yaml)
})

# Source custom functions
source("R/utils.R")
source("R/geocoding.R")

# --------------------------------------------------------------------------
# Load Configuration
# --------------------------------------------------------------------------
config <- yaml::read_yaml("config.yaml")

# Assign config values to variables
CITY <- config$city
INPUT_DIR <- config$dir_processed
OUTPUT_DIR <- config$dir_processed

# --------------------------------------------------------------------------
# Logger Configuration
# --------------------------------------------------------------------------
log_dir <- config$dir_logs
if (!dir.exists(log_dir)) dir.create(log_dir)
log_appender(appender_tee(file.path(log_dir, paste0("04_geocode_data_", CITY, ".log"))))
log_threshold(INFO)

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Input file
input_file_csv <- file.path(INPUT_DIR, paste0(CITY, "_items_for_geocoding.csv"))

# Output files
output_file_gpkg <- file.path(OUTPUT_DIR, paste0(CITY, "_geocoded_items.gpkg"))
output_file_csv <- file.path(OUTPUT_DIR, paste0(CITY, "_geocoded_items_final.csv"))

# Check for input file
if (!file.exists(input_file_csv)) {
  log_fatal("Prepared data file not found: {input_file_csv}. Please run '03_extract_locations.R' first.")
  stop("Prepared data file not found. Please run '03_extract_locations.R' first.")
}

print_separator()
log_info("Geocoding Prepared Data: {toupper(CITY)}")
print_separator()

# --------------------------------------------------------------------------
# Step 1: Load Prepared Data
# --------------------------------------------------------------------------

print_section("Loading prepared data...", "📂")

location_df <- read_csv(input_file_csv, col_types = cols())
log_info("Loaded {nrow(location_df)} items to be geocoded.")

# --------------------------------------------------------------------------
# Step 2: Hierarchical Geocoding
# --------------------------------------------------------------------------
print_section("Geocoding locations (hierarchical)...", "🌍")

# Separate items by geocoding strategy
addresses_to_geocode <- location_df %>%
  filter(location_type == "Address")

other_items_to_geocode <- location_df %>%
  filter(location_type != "Address")

log_info("Found {nrow(addresses_to_geocode)} items with addresses to geocode via Nominatim.")
log_info("Found {nrow(other_items_to_geocode)} items to geocode by district name.")

# --- Strategy 1: Address-level geocoding (slow, but precise) ---
geocoded_addresses_df <- NULL
if (nrow(addresses_to_geocode) > 0) {
  log_info("Starting batch geocoding for addresses... (this may take a while)")
  # geocode_batch is designed to be robust, with rate limiting.
  # It takes a vector of queries and returns a tibble with 'query', 'lat', 'lon'.
  geocoded_results <- geocode_batch(addresses_to_geocode$location_text)

  # Join results back to the original data
  geocoded_addresses_df <- addresses_to_geocode %>%
    left_join(geocoded_results, by = c("location_text" = "query"))
  
  log_info("...address geocoding complete.")
}

# --- Strategy 2: District-level geocoding (fast fallback) ---
geocoded_districts_df <- NULL
if (nrow(other_items_to_geocode) > 0) {
  log_info("Starting geocoding for districts and other types...")
  geocoded_districts_df <- geocode_by_district(other_items_to_geocode, district_col = "location_text")
  log_info("...district geocoding complete.")
}

# --- Combine results ---
final_geocoded_df <- bind_rows(geocoded_addresses_df, geocoded_districts_df) %>%
  arrange(agenda_item_id) # Restore original order

# Calculate overall success rate
success_rate <- geocoding_success_rate(final_geocoded_df)

log_info("Hierarchical geocoding complete.")
log_info("Overall Success Rate: {scales::percent(success_rate)}")

# --------------------------------------------------------------------------
# Step 3: Create Spatial Object (sf)
# --------------------------------------------------------------------------
print_section("Creating spatial 'sf' object...", "🗺️")

# Filter out items that could not be geocoded
geocoded_sf <- final_geocoded_df %>%
  filter(!is.na(lon) & !is.na(lat)) %>%
  df_to_sf(lon_col = "lon", lat_col = "lat")

log_info("Converted {nrow(geocoded_sf)} items to a spatial 'sf' object.")

# --------------------------------------------------------------------------
# Step 4: Save Processed Data
# --------------------------------------------------------------------------
print_section("Saving final geocoded data...", "💾")

# Save as GeoPackage
st_write(geocoded_sf, output_file_gpkg, delete_dsn = TRUE, quiet = TRUE)
log_info("Saved spatial data to: {output_file_gpkg}")

# Save as CSV for easy inspection
st_drop_geometry(geocoded_sf) %>%
  write_csv(output_file_csv)
log_info("Saved non-spatial data to: {output_file_csv}")

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
print_separator()
log_info("GEOCODING COMPLETE")
print_separator()

log_info("Summary:")
log_info("- Total items processed: {nrow(location_df)}")
log_info("- Successfully geocoded items: {nrow(geocoded_sf)}")
log_info("- Geocoding success rate: {scales::percent(success_rate)}")

log_info("Files saved to: {OUTPUT_DIR}")
log_info("- {basename(output_file_gpkg)}")
log_info("- {basename(output_file_csv)}")

print_separator()
log_info("Next step: Exploratory analysis and visualization.")

