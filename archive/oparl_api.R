# ============================================================================
# OParl API Functions
# ============================================================================
# Functions for interacting with OParl-compliant municipal council APIs.
# OParl is a standardized API specification for German e-government data.
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(httr)
  library(jsonlite)
  library(purrr)
  library(dplyr)
  library(tibble)
  library(logger)
})

# Source utilities
source("R/utils.R")

# Default API settings
OPARL_HTTP_TIMEOUT <- 15
OPARL_RETRY_MAX <- 3
OPARL_PAUSE_SEC <- 1

#' Fetch and Paginate Through OParl List Endpoint
#'
#' Fetches all items from an OParl list endpoint, handling pagination automatically.
#' Includes retry logic and error handling for robust API access.
#'
#' @param url Character string of the initial OParl list endpoint URL
#' @param query Named list of query parameters (default: empty list)
#' @param max_pages Maximum number of pages to fetch (default: 50)
#' @param max_items Maximum total items to return (default: Inf for all)
#' @param timeout_sec HTTP timeout in seconds (default: 30)
#' @param retries Number of retry attempts on failure (default: 3)
#' @param pause_sec Pause duration between retries in seconds (default: 1)
#'
#' @return List of OParl objects
#'
#' @examples
#' # Fetch all meetings from Augsburg
#' meetings <- oparl_fetch_all(
#'   "https://augsburg.sitzung-online.de/public/oparl/body/1/meeting",
#'   max_pages = 10
#' )
#'
#' # Fetch with time filter
#' recent_meetings <- oparl_fetch_all(
#'   "https://augsburg.sitzung-online.de/public/oparl/body/1/meeting",
#'   query = list(modified_since = "2023-01-01T00:00:00Z"),
#'   max_items = 50
#' )
#'
#' @export
oparl_fetch_all <- function(url,
                            query = list(),
                            max_pages = 50,
                            max_items = Inf,
                            timeout_sec = 30,
                            retries = 3,
                            pause_sec = 1) {

  all_items <- list()
  page_count <- 0
  next_url <- if (length(query)) httr::modify_url(url, query = query) else url
  show_progress <- TRUE  # Only show detailed progress for main endpoints

  repeat {
    page_count <- page_count + 1
    if (page_count > max_pages || is.null(next_url)) break

    # Simple retry logic with while loop
    resp <- NULL
    attempt_num <- 1
    first_attempt <- TRUE

    while (attempt_num <= retries) {
      resp <- tryCatch({
        httr::GET(
          next_url,
          httr::timeout(timeout_sec),
          httr::user_agent("R OParl Client (httr)")
        )
      }, error = function(e) {
        # Only show error on first attempt to reduce spam
        if (first_attempt) {
          log_warn("Page {page_count} failed (attempt {attempt_num}/{retries})")
          first_attempt <<- FALSE
        }
        if (attempt_num < retries) {
          Sys.sleep(pause_sec)
        }
        NULL  # Return NULL on error
      })

      # If successful, break out of retry loop
      if (!is.null(resp)) {
        if (!first_attempt) {
          log_info("Page {page_count} succeeded after {attempt_num} attempts")
        }
        break
      }

      # Increment attempt counter
      attempt_num <- attempt_num + 1
    }

    # If all retries failed, stop
    if (is.null(resp)) {
      log_warn("Failed to fetch {next_url} after {retries} attempts")
      break
    }

    # Check response status
    if (is.null(resp) || httr::status_code(resp) != 200) {
      log_warn("Failed to fetch {next_url}; status: {if (!is.null(resp)) httr::status_code(resp) else 'NULL'}")
      break
    }

    # Check if response is actually JSON (not HTML error page)
    content_type <- httr::headers(resp)$`content-type` %||% ""
    if (!grepl("application/json", content_type, ignore.case = TRUE)) {
      log_warn("Server returned non-JSON response ({content_type}). Skipping this page.")
      break
    }

    # Parse JSON response
    parsed <- tryCatch({
      httr::content(resp, as = "parsed", type = "application/json")
    }, error = function(e) {
      log_warn("JSON parse error: {e$message}. Response might be HTML.")
      # Try to get raw text to see what we got
      raw_text <- httr::content(resp, as = "text", encoding = "UTF-8")
      if (nchar(raw_text) < 500) {
        log_warn("Response preview: {substr(raw_text, 1, 200)}")
      }
      NULL
    })

    # If parsing failed, stop
    if (is.null(parsed)) {
      log_warn("Failed to parse response as JSON")
      break
    }

    # Extract items from OParl list structure: list(data = [...], links = list(next = ...))
    items <- parsed$data %||% list()
    all_items <- c(all_items, items)

    # Stop if we've reached the item limit
    if (length(all_items) >= max_items) break

    # Get next page URL (handle reserved word 'next' safely)
    next_url <- if (!is.null(parsed$links)) {
      parsed$links[["next"]] %||% NULL
    } else {
      NULL
    }

    if (is.null(next_url)) break
  }

  # Truncate to max_items if specified
  if (is.finite(max_items)) {
    return(all_items[seq_len(min(length(all_items), max_items))])
  }

  all_items
}

#' Connect to OParl System Endpoint
#'
#' Fetches system information from an OParl API root endpoint.
#'
#' @param system_url Character string of the OParl system endpoint URL
#' @param timeout_sec HTTP timeout in seconds (default: 15)
#'
#' @return List containing parsed OParl system object
#'
#' @examples
#' # Connect to Augsburg OParl API
#' system <- oparl_connect("https://augsburg.sitzung-online.de/public/oparl/system")
#' print(system$name)
#'
#' @export
oparl_connect <- function(system_url, timeout_sec = OPARL_HTTP_TIMEOUT) {
  response <- httr::GET(system_url, httr::timeout(timeout_sec))

  if (httr::status_code(response) == 200) {
    system_info <- httr::content(response, as = "parsed", type = "application/json")
    return(system_info)
  } else {
    stop(
      "Failed to connect to OParl API. ",
      "Status code: ", httr::status_code(response),
      "\nURL: ", system_url
    )
  }
}

#' Parse OParl Meetings to Data Frame
#'
#' Converts a list of OParl meeting objects to a tidy data frame.
#'
#' @param meetings_list List of OParl meeting objects
#'
#' @return Tibble with meeting information
#'
#' @export
parse_meetings <- function(meetings_list) {
  purrr::map_dfr(meetings_list, function(meeting) {
    # Handle organization (may be URL reference or expanded object)
    org <- if (!is.null(meeting$organization) && length(meeting$organization) > 0) {
      as.character(meeting$organization[[1]])
    } else {
      NA_character_
    }

    tibble(
      id = meeting$id %||% NA_character_,
      name = meeting$name %||% NA_character_,
      start_date = meeting$start %||% NA_character_,
      meeting_state = meeting$meetingState %||% NA_character_,
      organization = org
    )
  })
}

#' Parse OParl Agenda Items to Data Frame
#'
#' Converts a list of OParl agenda item objects to a tidy data frame.
#'
#' @param agenda_list List of OParl agenda item objects
#'
#' @return Tibble with agenda item information
#'
#' @export
parse_agenda_items <- function(agenda_list) {
  purrr::map_dfr(agenda_list, function(item) {
    # Handle consultation - may be NULL, empty list, or list of URLs
    consultation_url <- if (!is.null(item$consultation) && length(item$consultation) > 0) {
      as.character(item$consultation[[1]])
    } else {
      NA_character_
    }

    # Handle meeting reference - may be character URL or list
    meeting_id <- if (!is.null(item$meeting)) {
      if (is.list(item$meeting) && length(item$meeting) > 0) {
        as.character(item$meeting[[1]])
      } else {
        as.character(item$meeting)
      }
    } else {
      NA_character_
    }

    tibble(
      id = item$id %||% NA_character_,
      name = item$name %||% NA_character_,
      number = item$number %||% NA_character_,
      public = as.logical(item$public %||% NA),
      result = item$result %||% NA_character_,
      consultation_url = consultation_url,
      meeting_id = meeting_id
    )
  })
}

#' Parse OParl Papers to Data Frame
#'
#' Converts a list of full OParl paper/document objects to a tidy data frame,
#' including the URL to the main PDF document.
#'
#' @param papers_list List of full OParl paper objects.
#'
#' @return Tibble with paper information including id, name, and pdf_url.
#'
#' @export
parse_papers <- function(papers_list) {
  purrr::map_dfr(papers_list, ~{
    tibble::tibble(
      id = .x$id %||% NA_character_,
      name = .x$name %||% NA_character_,
      # Safely extract the PDF URL, preferring mainFile over the file list
      pdf_url = .x$mainFile$accessUrl %||% .x$file[[1]]$accessUrl %||% NA_character_
    )
  })
}

#' Fetch OParl Bodies (Political Entities)
#'
#' Fetches all political bodies (e.g., city councils) from an OParl system.
#'
#' @param system_info OParl system object (from oparl_connect)
#'
#' @return List of body objects
#'
#' @export
fetch_bodies <- function(system_info) {
  bodies_url <- system_info$body
  response <- httr::GET(bodies_url)
  bodies_data <- httr::content(response, as = "parsed", type = "application/json")
  bodies_data$data
}
