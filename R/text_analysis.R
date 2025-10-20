# ============================================================================
# Text Analysis Functions
# ============================================================================
# Functions for text mining and pattern matching in council documents.
# Specialized for identifying development plan (Bebauungsplan) references.
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(stringr)
  library(dplyr)
})

#' Create Bebauungsplan Detection Pattern
#'
#' Returns a regex pattern for matching development plan (Bebauungsplan) references
#' in German text. Includes common abbreviations and variations.
#'
#' @param ignore_case Logical, whether to ignore case (default: TRUE)
#'
#' @return Regex pattern object
#'
#' @examples
#' pattern <- create_bplan_pattern()
#' str_detect("Bebauungsplan Nr. 1234", pattern)  # Returns TRUE
#'
#' @export
create_bplan_pattern <- function(ignore_case = TRUE) {
  pattern_string <- paste(
    "bebauungsplan",
    "bebauungspl[aä]n[e]?",
    "b-?plan",
    "bpl[aä]n[e]?",
    "bebauungsplanverfahren",
    "bauleitplan",
    sep = "|"
  )

  stringr::regex(pattern_string, ignore_case = ignore_case)
}

#' Filter Bebauungsplan Items
#'
#' Filters a data frame to keep only rows containing Bebauungsplan references.
#'
#' @param df Data frame with a 'name' or 'title' column
#' @param text_column Name of column to search (default: "name")
#' @param pattern Optional custom regex pattern (default: uses create_bplan_pattern())
#'
#' @return Filtered data frame
#'
#' @examples
#' agenda <- tibble(name = c("Bebauungsplan X", "Other topic"))
#' bplan_agenda <- filter_bplan_items(agenda)
#'
#' @export
filter_bplan_items <- function(df,
                               text_column = "name",
                               pattern = create_bplan_pattern()) {

  if (!text_column %in% names(df)) {
    stop("Column '", text_column, "' not found in data frame")
  }

  df %>%
    dplyr::filter(stringr::str_detect(.data[[text_column]], pattern))
}

#' Extract Plan Number from Text
#'
#' Attempts to extract a plan number (e.g., "Nr. 1234", "No. 5678") from text.
#'
#' @param text Character vector to search
#'
#' @return Character vector of plan numbers or NA if not found
#'
#' @examples
#' extract_plan_number("Bebauungsplan Nr. 1234")  # Returns "1234"
#' extract_plan_number("B-Plan No. 5678-A")  # Returns "5678-A"
#'
#' @export
extract_plan_number <- function(text) {
  # Pattern: "Nr." or "No." followed by optional space and alphanumeric characters
  pattern <- "(?:Nr\\.?|No\\.?)\\s*([A-Za-z0-9-]+)"
  stringr::str_extract(text, stringr::regex(pattern, ignore_case = TRUE))
}

#' Classify Plan Type
#'
#' Classifies development plans by type based on keywords in the text.
#' Categories: Residential, Commercial, Industrial, Green Space, Mixed, Other
#'
#' @param text Character vector of plan descriptions
#'
#' @return Factor vector of plan types
#'
#' @examples
#' classify_plan_type("Bebauungsplan Wohngebiet")  # Returns "Residential"
#'
#' @export
classify_plan_type <- function(text) {
  text_lower <- tolower(text)

  type <- case_when(
    # Residential
    stringr::str_detect(text_lower, "wohn|wohnung|residential") ~ "Residential",

    # Commercial
    stringr::str_detect(text_lower, "einzelhandel|handel|einkauf|commercial|retail") ~ "Commercial",

    # Industrial
    stringr::str_detect(text_lower, "gewerbe|industrie|industrial") ~ "Industrial",

    # Green space / Parks
    stringr::str_detect(text_lower, "grün|park|naturschutz|green|nature") ~ "Green Space",

    # Mixed use
    stringr::str_detect(text_lower, "misch|mixed") ~ "Mixed",

    # Infrastructure
    stringr::str_detect(text_lower, "infrastruktur|verkehr|transport|infrastructure") ~ "Infrastructure",

    # Default
    TRUE ~ "Other"
  )

  factor(type, levels = c(
    "Residential", "Commercial", "Industrial",
    "Green Space", "Mixed", "Infrastructure", "Other"
  ))
}

#' Classify Decision Type
#'
#' Extracts decision type from German council decision text.
#'
#' @param text Character vector of decision descriptions
#'
#' @return Factor vector of decision types
#'
#' @examples
#' classify_decision_type("Beschlossen")  # Returns "Approved"
#'
#' @export
classify_decision_type <- function(text) {
  text_lower <- tolower(text)

  decision <- case_when(
    stringr::str_detect(text_lower, "beschlossen|approved|genehmigt") ~ "Approved",
    stringr::str_detect(text_lower, "abgelehnt|rejected|verworfen") ~ "Rejected",
    stringr::str_detect(text_lower, "vertagt|postponed|verschoben") ~ "Postponed",
    stringr::str_detect(text_lower, "zurückgestellt|zurückgezogen|withdrawn") ~ "Withdrawn",
    TRUE ~ "Other"
  )

  factor(decision, levels = c("Approved", "Rejected", "Postponed", "Withdrawn", "Other"))
}

#' Extract Location References
#'
#' Attempts to extract street names or location identifiers from text.
#'
#' @param text Character vector to search
#'
#' @return Character vector of location references or NA
#'
#' @export
extract_location <- function(text) {
  # Pattern: Common German street suffixes
  street_pattern <- "([A-ZÄÖÜ][a-zäöüß]+(?:straße|str\\.|weg|platz|allee|ring|damm|ufer))"
  stringr::str_extract(text, stringr::regex(street_pattern, ignore_case = TRUE))
}
