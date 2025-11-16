# ============================================================================
# Analysis Workflow Step 3: Geocode Prepared Data
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
})

# Source custom functions
source("R/utils.R")
source("R/geocoding.R")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

CITY <- "augsburg"
INPUT_DIR <- "data"
OUTPUT_DIR <- "data"

# Input file
input_file_csv <- file.path(INPUT_DIR, paste0(CITY, "_items_for_geocoding.csv"))

# Output files
output_file_gpkg <- file.path(OUTPUT_DIR, paste0(CITY, "_geocoded_items.gpkg"))
output_file_csv <- file.path(OUTPUT_DIR, paste0(CITY, "_geocoded_items_final.csv"))

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# Check for input file
if (!file.exists(input_file_csv)) {
  stop("❌ Prepared data file not found. Please run '02_prepare_data.R' first.")
}

print_separator()
cat(" Geocoding Prepared Data:", toupper(CITY), "\n")
print_separator()
cat("\n")

# --------------------------------------------------------------------------
# Step 1: Load Prepared Data
# --------------------------------------------------------------------------

print_section("Loading prepared data...", "📂")

location_df <- read_csv(input_file_csv, col_types = cols())
cat("✅ Loaded", nrow(location_df), "items to be geocoded.\n\n")

# --------------------------------------------------------------------------
# Step 2: Hierarchical Geocoding
# --------------------------------------------------------------------------
print_section("Geocoding locations (hierarchical)...", "🌍")

# Separate items by geocoding strategy
addresses_to_geocode <- location_df %>%
  filter(location_type == "Address")

other_items_to_geocode <- location_df %>%
  filter(location_type != "Address")

cat("   Found", nrow(addresses_to_geocode), "items with addresses to geocode via Nominatim.\n")
cat("   Found", nrow(other_items_to_geocode), "items to geocode by district name.\n\n")

# --- Strategy 1: Address-level geocoding (slow, but precise) ---
geocoded_addresses_df <- NULL
if (nrow(addresses_to_geocode) > 0) {
  cat("   Starting batch geocoding for addresses... (this may take a while)\n")
  # geocode_batch is designed to be robust, with rate limiting.
  # It takes a vector of queries and returns a tibble with 'query', 'lat', 'lon'.
  geocoded_results <- geocode_batch(addresses_to_geocode$location_text)

  # Join results back to the original data
  geocoded_addresses_df <- addresses_to_geocode %>%
    left_join(geocoded_results, by = c("location_text" = "query"))
  
cat("   ...address geocoding complete.\n")
}

# --- Strategy 2: District-level geocoding (fast fallback) ---
geocoded_districts_df <- NULL
if (nrow(other_items_to_geocode) > 0) {
  cat("   Starting geocoding for districts and other types...\n")
  geocoded_districts_df <- geocode_by_district(other_items_to_geocode, district_col = "location_text")
  cat("   ...district geocoding complete.\n")
}

# --- Combine results ---
final_geocoded_df <- bind_rows(geocoded_addresses_df, geocoded_districts_df) %>%
  arrange(agenda_item_id) # Restore original order

# Calculate overall success rate
success_rate <- geocoding_success_rate(final_geocoded_df)

cat("\n✅ Hierarchical geocoding complete.\n")
cat("   Overall Success Rate:", scales::percent(success_rate), "\n\n")

# --------------------------------------------------------------------------
# Step 3: Create Spatial Object (sf)
# --------------------------------------------------------------------------
print_section("Creating spatial 'sf' object...", "🗺️")

# Filter out items that could not be geocoded
geocoded_sf <- final_geocoded_df %>%
  filter(!is.na(lon) & !is.na(lat)) %>%
  df_to_sf(lon_col = "lon", lat_col = "lat")

cat("✅ Converted", nrow(geocoded_sf), "items to a spatial 'sf' object.\n\n")

# --------------------------------------------------------------------------
# Step 4: Save Processed Data
# --------------------------------------------------------------------------
print_section("Saving final geocoded data...", "💾")

# Save as GeoPackage
st_write(geocoded_sf, output_file_gpkg, delete_dsn = TRUE)
cat("✅ Saved spatial data to:", output_file_gpkg, "\n")

# Save as CSV for easy inspection
st_drop_geometry(geocoded_sf) %>%
  write_csv(output_file_csv)
cat("✅ Saved non-spatial data to:", output_file_csv, "\n\n")

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
print_separator()
cat("✅ GEOCODING COMPLETE\n")
print_separator()
cat("\n")

cat("📊 Summary:\n")
cat("   Total items processed:", nrow(location_df), "\n")
cat("   Successfully geocoded items:", nrow(geocoded_sf), "\n")
cat("   Geocoding success rate:", scales::percent(success_rate), "\n\n")

cat("📁 Files saved to:", OUTPUT_DIR, "\n")
cat("   -", basename(output_file_gpkg), "\n")
cat("   -", basename(output_file_csv), "\n\n")

print_separator()
cat("\n🎯 Next step: Exploratory analysis and visualization.\n\n")
