# R Functions

Custom R functions for the Geomodelierung project. All functions are documented with roxygen-style comments and examples.

## Files and Functions

### `utils.R` - General Utilities
Helper functions used across the project.

**Functions:**
- `%||%` - NULL-coalescing operator
- `extract_district()` - Extract district name from text
- `safe_parse_date()` - Safe date parsing with fallbacks
- `print_section()` - Print formatted section headers
- `print_separator()` - Print separator lines

**Usage:**
```r
source("R/utils.R")

# NULL-coalescing
result <- NULL %||% "default"  # Returns "default"

# Extract district
extract_district("Bebauungsplan in Poppelsdorf")  # Returns "Poppelsdorf"
```

---

### `oparl_api.R` - OParl API Integration
Functions for interacting with OParl-compliant municipal council APIs.

**Functions:**
- `oparl_connect()` - Connect to OParl system endpoint
- `oparl_fetch_all()` - Fetch and paginate through OParl list endpoints
- `fetch_bodies()` - Fetch political bodies
- `parse_meetings()` - Convert meeting objects to data frame
- `parse_agenda_items()` - Convert agenda items to data frame
- `parse_papers()` - Convert papers to data frame

**Usage:**
```r
source("R/oparl_api.R")

# Connect to Bonn
system <- oparl_connect("https://www.bonn.sitzung-online.de/public/oparl/system")
bodies <- fetch_bodies(system)
body <- bodies[[1]]

# Fetch meetings
meetings_list <- oparl_fetch_all(
  body$meeting,
  max_pages = 10,
  timeout_sec = 30
)

# Parse to data frame
meetings_df <- parse_meetings(meetings_list)
```

---

### `text_analysis.R` - Text Mining
Functions for text analysis and pattern matching in council documents.

**Functions:**
- `create_bplan_pattern()` - Create regex pattern for Bebauungsplan detection
- `filter_bplan_items()` - Filter data frame for B-Plan references
- `extract_plan_number()` - Extract plan number from text
- `classify_plan_type()` - Classify plan by type (Residential, Commercial, etc.)
- `classify_decision_type()` - Classify decision outcome (Approved, Rejected, etc.)
- `extract_location()` - Extract street names from text

**Usage:**
```r
source("R/text_analysis.R")

# Filter for Bebauungsplan items
pattern <- create_bplan_pattern()
bplan_items <- filter_bplan_items(agenda_df, text_column = "name")

# Classify plan types
df <- df %>%
  mutate(
    plan_type = classify_plan_type(name),
    decision = classify_decision_type(result)
  )
```

---

### `geocoding.R` - Geocoding Functions
Functions for geocoding addresses and spatial data processing.

**Functions:**
- `get_district_coordinates()` - Get Bonn district center coordinates
- `geocode_by_district()` - Join data with district coordinates
- `df_to_sf()` - Convert data frame to sf spatial object
- `geocode_nominatim()` - Geocode single address via Nominatim API
- `geocode_batch()` - Batch geocode with rate limiting
- `geocoding_success_rate()` - Calculate geocoding success percentage

**Usage:**
```r
source("R/geocoding.R")

# Simple district-based geocoding
geocoded <- geocode_by_district(bplan_items)

# Convert to spatial object
bplan_sf <- df_to_sf(geocoded, lon_col = "lon", lat_col = "lat")

# Full geocoding via Nominatim (requires internet)
results <- geocode_batch(c("Rathausgasse 1", "Poppelsdorfer Allee 49"))
```

---

### `visualization.R` - Visualization Functions
Functions for creating consistent, publication-quality visualizations.

**Functions:**
- `plot_temporal_trend()` - Create temporal distribution histogram
- `plot_district_frequency()` - Create district frequency bar chart
- `plot_spatial_map()` - Create spatial distribution map
- `save_plot()` - Save plot with consistent settings
- `create_summary_stats()` - Generate summary statistics table
- `print_summary_stats()` - Print formatted summary statistics

**Usage:**
```r
source("R/visualization.R")

# Create temporal trend plot
temporal_plot <- plot_temporal_trend(
  df,
  bins = 12,
  title = "Temporal Distribution of B-Plan Decisions"
)

# Create district frequency plot
district_plot <- plot_district_frequency(df)

# Create spatial map
map_plot <- plot_spatial_map(bplan_sf)

# Save plots
save_plot(temporal_plot, "temporal_trend.png", dpi = 300)
save_plot(district_plot, "district_frequency.png")
save_plot(map_plot, "spatial_map.png")

# Summary statistics
stats <- create_summary_stats(df)
print_summary_stats(stats)
```

---

## Usage Pattern

**Standard workflow:**

```r
# 1. Load all functions
source("R/utils.R")
source("R/oparl_api.R")
source("R/text_analysis.R")
source("R/geocoding.R")
source("R/visualization.R")

# 2. Download data
system <- oparl_connect("https://example.com/oparl/system")
meetings <- oparl_fetch_all(body$meeting)
agenda <- parse_agenda_items(agenda_list)

# 3. Filter for Bebauungsplan
bplan_items <- filter_bplan_items(agenda)

# 4. Geocode
geocoded <- geocode_by_district(bplan_items)
bplan_sf <- df_to_sf(geocoded)

# 5. Visualize
plot <- plot_spatial_map(bplan_sf)
save_plot(plot, "map.png")

# 6. Statistics
stats <- create_summary_stats(geocoded)
print_summary_stats(stats)
```

---

## Design Principles

1. **Separation of Concerns**: Each file has a single, clear purpose
2. **Reusability**: Functions are generic and composable
3. **Documentation**: All functions have roxygen comments
4. **Error Handling**: Graceful fallbacks and informative warnings
5. **Consistency**: Standardized naming and parameter conventions

---

## Testing

Functions can be tested individually:

```r
# Test utils
stopifnot((NULL %||% "default") == "default")
stopifnot(extract_district("Text Poppelsdorf Text") == "Poppelsdorf")

# Test text analysis
pattern <- create_bplan_pattern()
stopifnot(str_detect("Bebauungsplan", pattern))

# Test geocoding
coords <- get_district_coordinates()
stopifnot(nrow(coords) == 15)  # 15 Bonn districts
```

---

## Future Extensions

Planned additions:
- `load_data.R` - Data loading utilities for processed data
- `spatial_analysis.R` - Advanced spatial statistics (Moran's I, LISA, clustering)
- `nlp_advanced.R` - Advanced NLP functions for document analysis
- `interactive_viz.R` - Interactive visualizations with leaflet, shiny
