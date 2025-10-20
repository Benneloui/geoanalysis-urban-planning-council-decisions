# ============================================================================
# Geocoding Functions
# ============================================================================
# Functions for geocoding addresses and locations.
# Includes simplified district-based geocoding and full address geocoding.
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(dplyr)
  library(tibble)
  library(sf)
})

#' Get Bonn District Coordinates
#'
#' Returns approximate center coordinates for Bonn districts.
#' Used for demonstration/fallback when precise geocoding is not available.
#'
#' @return Tibble with columns: district, lon, lat
#'
#' @examples
#' coords <- get_district_coordinates()
#' coords %>% filter(district == "Innenstadt")
#'
#' @export
get_district_coordinates <- function() {
  tribble(
    ~district,       ~lon,     ~lat,
    "Innenstadt",    7.0982,   50.7374,
    "Nordstadt",     7.0982,   50.7474,
    "Südstadt",      7.0982,   50.7274,
    "Beuel",         7.1282,   50.7374,
    "Bad Godesberg", 7.1582,   50.6874,
    "Dottendorf",    7.1082,   50.7174,
    "Poppelsdorf",   7.0782,   50.7224,
    "Endenich",      7.0582,   50.7324,
    "Duisdorf",      7.0482,   50.7524,
    "Hardtberg",     7.0282,   50.7674,
    "Kessenich",     7.0882,   50.7074,
    "Vilich",        7.1382,   50.7274,
    "Lengsdorf",     7.0382,   50.7424,
    "Röttgen",       7.0182,   50.6874,
    "Ückesdorf",     7.1482,   50.6974
  )
}

#' Geocode by District
#'
#' Joins data frame with district coordinates based on district column.
#'
#' @param df Data frame with a 'district' column
#' @param district_coords Optional custom district coordinate table
#'
#' @return Data frame with added lon and lat columns
#'
#' @examples
#' df <- tibble(district = c("Innenstadt", "Beuel"))
#' geocoded <- geocode_by_district(df)
#'
#' @export
geocode_by_district <- function(df, district_coords = NULL) {
  if (is.null(district_coords)) {
    district_coords <- get_district_coordinates()
  }

  df %>%
    dplyr::left_join(district_coords, by = "district")
}

#' Convert to SF (Simple Features) Object
#'
#' Converts a data frame with lon/lat columns to an sf spatial object.
#'
#' @param df Data frame with lon and lat columns
#' @param lon_col Name of longitude column (default: "lon")
#' @param lat_col Name of latitude column (default: "lat")
#' @param crs Coordinate reference system (default: 4326 for WGS84)
#' @param remove_na Remove rows with NA coordinates (default: TRUE)
#'
#' @return sf object
#'
#' @examples
#' df <- tibble(lon = 7.0982, lat = 50.7374, name = "Bonn")
#' sf_obj <- df_to_sf(df)
#'
#' @export
df_to_sf <- function(df,
                     lon_col = "lon",
                     lat_col = "lat",
                     crs = 4326,
                     remove_na = TRUE) {

  # Check columns exist
  if (!lon_col %in% names(df)) stop("Column '", lon_col, "' not found")
  if (!lat_col %in% names(df)) stop("Column '", lat_col, "' not found")

  # Optionally filter out NA coordinates
  if (remove_na) {
    df <- df %>%
      dplyr::filter(!is.na(.data[[lon_col]]) & !is.na(.data[[lat_col]]))
  }

  # Convert to sf
  sf::st_as_sf(
    df,
    coords = c(lon_col, lat_col),
    crs = crs
  )
}

#' Geocode Address via Nominatim
#'
#' Geocodes an address using the OpenStreetMap Nominatim API.
#' NOTE: Requires internet connection and respects usage limits.
#'
#' @param address Character string of address to geocode
#' @param city Optional city name to append to query (default: "Bonn, Germany")
#' @param timeout_sec HTTP timeout in seconds (default: 10)
#'
#' @return Named vector with lon, lat, display_name or NA if failed
#'
#' @examples
#' \dontrun{
#' coords <- geocode_nominatim("Rathausgasse 1")
#' }
#'
#' @export
geocode_nominatim <- function(address,
                              city = "Bonn, Germany",
                              timeout_sec = 10) {

  # Construct query
  query_address <- paste(address, city, sep = ", ")

  # Build Nominatim URL
  base_url <- "https://nominatim.openstreetmap.org/search"
  url <- httr::modify_url(
    base_url,
    query = list(
      q = query_address,
      format = "json",
      limit = 1
    )
  )

  # Make request
  resp <- tryCatch({
    httr::GET(
      url,
      httr::timeout(timeout_sec),
      httr::user_agent("R geomodelierung research project")  # Nominatim requires user agent
    )
  }, error = function(e) {
    warning("Geocoding request failed: ", e$message)
    return(NULL)
  })

  if (is.null(resp) || httr::status_code(resp) != 200) {
    return(c(lon = NA_real_, lat = NA_real_, display_name = NA_character_))
  }

  # Parse response
  result <- httr::content(resp, as = "parsed")

  if (length(result) == 0) {
    return(c(lon = NA_real_, lat = NA_real_, display_name = NA_character_))
  }

  c(
    lon = as.numeric(result[[1]]$lon),
    lat = as.numeric(result[[1]]$lat),
    display_name = result[[1]]$display_name
  )
}

#' Batch Geocode with Rate Limiting
#'
#' Geocodes multiple addresses with automatic rate limiting to respect API limits.
#'
#' @param addresses Character vector of addresses
#' @param city City name (default: "Bonn, Germany")
#' @param delay_sec Delay between requests in seconds (default: 1, Nominatim policy)
#' @param show_progress Show progress bar (default: TRUE)
#'
#' @return Tibble with columns: address, lon, lat, display_name, success
#'
#' @examples
#' \dontrun{
#' addresses <- c("Rathausgasse 1", "Poppelsdorfer Allee 49")
#' results <- geocode_batch(addresses)
#' }
#'
#' @export
geocode_batch <- function(addresses,
                          city = "Bonn, Germany",
                          delay_sec = 1,
                          show_progress = TRUE) {

  n <- length(addresses)
  results <- vector("list", n)

  if (show_progress) {
    cat("Geocoding", n, "addresses...\n")
  }

  for (i in seq_along(addresses)) {
    if (show_progress && i %% 10 == 0) {
      cat("  Progress:", i, "/", n, "\n")
    }

    coords <- geocode_nominatim(addresses[i], city = city)

    results[[i]] <- tibble(
      address = addresses[i],
      lon = coords["lon"],
      lat = coords["lat"],
      display_name = coords["display_name"],
      success = !is.na(coords["lon"])
    )

    # Rate limiting
    if (i < n) Sys.sleep(delay_sec)
  }

  dplyr::bind_rows(results)
}

#' Calculate Geocoding Success Rate
#'
#' Calculates the percentage of successfully geocoded items.
#'
#' @param df Data frame with lon and lat columns
#' @param lon_col Longitude column name (default: "lon")
#' @param lat_col Latitude column name (default: "lat")
#'
#' @return Numeric value between 0 and 100
#'
#' @export
geocoding_success_rate <- function(df, lon_col = "lon", lat_col = "lat") {
  total <- nrow(df)
  if (total == 0) return(0)

  success <- sum(!is.na(df[[lon_col]]) & !is.na(df[[lat_col]]))
  round(100 * success / total, 1)
}
