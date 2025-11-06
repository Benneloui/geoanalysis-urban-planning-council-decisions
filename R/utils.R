# ============================================================================
# Utility Functions
# ============================================================================
# General-purpose helper functions used across the analysis
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

#' NULL-Coalescing Operator
#'
#' Returns the left-hand side if not NULL, otherwise returns the right-hand side.
#' Equivalent to the || operator in other languages.
#'
#' @param x First value to check
#' @param y Fallback value if x is NULL
#' @return x if not NULL, otherwise y
#'
#' @examples
#' NULL %||% "default"  # Returns "default"
#' "value" %||% "default"  # Returns "value"
`%||%` <- function(x, y) {
  if (is.null(x)) y else x
}

#' Extract District Name from Text
#'
#' Searches text for known Cologne district names and returns the first match.
#'
#' @param text Character vector to search
#' @param known_districts Character vector of district names to search for
#' @return First matched district name or NA if no match
#'
#' @examples
#' extract_district("Bebauungsplan in Ehrenfeld")  # Returns "Ehrenfeld"
extract_district <- function(text, known_districts = NULL) {
  if (is.null(known_districts)) {
    # Default Cologne districts
    known_districts <- c(
      "Innenstadt", "Altstadt-Nord", "Altstadt-Süd", "Deutz", "Kalk",
      "Mülheim", "Ehrenfeld", "Nippes", "Lindenthal", "Rodenkirchen",
      "Sülz", "Porz", "Chorweiler", "Poll", "Bayenthal"
    )
  }

  # Create regex pattern with word boundaries
  pattern <- paste0("\\b(", paste(known_districts, collapse = "|"), ")\\b")

  # Find matches
  hit <- known_districts[stringr::str_detect(
    text,
    stringr::regex(pattern, ignore_case = TRUE)
  )]

  if (length(hit) > 0) hit[[1]] else NA_character_
}

#' Safe Date Parsing
#'
#' Attempts to parse dates with multiple fallbacks and error handling.
#'
#' @param date_string Character vector of date strings
#' @param fallback_date Date to use if parsing fails (default: current date)
#' @return Date vector
safe_parse_date <- function(date_string, fallback_date = Sys.Date()) {
  suppressWarnings({
    parsed <- lubridate::ymd_hms(date_string, quiet = TRUE)
    parsed <- as.Date(ifelse(is.na(parsed), fallback_date, parsed))
  })
  parsed
}

#' Print Section Header
#'
#' Prints a formatted section header for console output.
#'
#' @param text Header text
#' @param emoji Optional emoji prefix (default: "")
#' @param width Total width of separator line (default: 70)
print_section <- function(text, emoji = "", width = 70) {
  if (nchar(emoji) > 0) {
    cat(emoji, " ", text, "\n", sep = "")
  } else {
    cat(text, "\n")
  }
}

#' Print Separator Line
#'
#' Prints a separator line for console output.
#'
#' @param char Character to repeat (default: "=")
#' @param width Width of line (default: 70)
print_separator <- function(char = "=", width = 70) {
  cat(strrep(char, width), "\n")
}
