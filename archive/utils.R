# ============================================================================
# Utility Functions
# ============================================================================
# General-purpose helper functions used across the analysis
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(logger)
})

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
#' Searches text for known Augsburg district names and returns the first match.
#'
#' @param text Character vector to search
#' @param known_districts Character vector of district names to search for
#' @return First matched district name or NA if no match
#'
#' @examples
#' extract_district("Bebauungsplan in Göggingen")  # Returns "Göggingen"
extract_district <- function(text, known_districts = NULL) {
  if (is.null(known_districts)) {
    # Default Augsburg districts
    known_districts <- c(
      "Innenstadt", "Antonsviertel", "Bärenkeller", "Göggingen", "Haunstetten",
      "Hochfeld", "Kriegshaber", "Lechhausen", "Oberhausen", "Pfersee",
      "Spickel", "Stadtbergen", "Univiertel", "Hammerschmiede", "Bergheim"
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
#' Prints a formatted section header using the logger.
#'
#' @param text Header text
#' @param emoji Optional emoji prefix (default: "")
print_section <- function(text, emoji = "") {
  log_info(paste(emoji, text))
}

#' Print Separator Line
#'
#' Prints a separator line using the logger.
#'
#' @param char Character to repeat (default: "=")
#' @param width Width of line (default: 70)
print_separator <- function(char = "=", width = 70) {
  log_info(strrep(char, width))
}

#' Safely Read PDF Text from a URL with OCR fallback
#'
#' Downloads a PDF from a URL to a temporary file, extracts the text using
#' pdftools (with a tesseract OCR fallback), and cleans up the temporary file.
#'
#' @param url The URL of the PDF file.
#' @return A single character string containing the collapsed text of the PDF,
#'   or NA_character_ if the URL is invalid or the PDF cannot be read.
#' @export
read_pdf_from_url <- function(url) {
  if (is.na(url) || !str_starts(url, "http")) {
    return(NA_character_)
  }
  temp_pdf_path <- tempfile(fileext = ".pdf")
  on.exit(unlink(temp_pdf_path), add = TRUE)
  
  download_success <- tryCatch({
    # Add a timeout to the download
    download.file(url, temp_pdf_path, mode = "wb", quiet = TRUE, timeout = 60)
    TRUE
  }, error = function(e) {
    log_warn("Failed to download URL: {url} - {e$message}")
    FALSE
  })
  
  if (!download_success) {
    return(NA_character_)
  }
  
  # Try pdftools first
  pdf_text <- tryCatch({
    pdftools::pdf_text(temp_pdf_path)
  }, error = function(e) NULL)
  
  # OCR fallback if no text layer is found
  if (is.null(pdf_text) || all(nchar(trimws(pdf_text)) == 0)) {
    pdf_text <- tryCatch({
      tesseract::ocr(temp_pdf_path)
    }, error = function(e) {
      log_warn("OCR failed for URL: {url} - {e$message}")
      NA_character_
    })
    return(paste(pdf_text, collapse = " \n "))
  }
  
  return(paste(pdf_text, collapse = " \n "))
}