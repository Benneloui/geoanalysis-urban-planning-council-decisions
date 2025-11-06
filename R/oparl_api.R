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
#' # Fetch all meetings from Cologne
#' meetings <- oparl_fetch_all(
#'   "https://ratsinformation.stadt-koeln.de/oparl/body/1/meeting",
#'   max_pages = 10
#' )
#'
#' # Fetch with time filter
#' recent_meetings <- oparl_fetch_all(
#'   "https://ratsinformation.stadt-koeln.de/oparl/body/1/meeting",
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

  repeat {
    page_count <- page_count + 1
    if (page_count > max_pages || is.null(next_url)) break

    # Fetch page with retry logic
    resp <- httr::RETRY(
      "GET", next_url,
      httr::timeout(timeout_sec),
      times = retries,
      pause_min = pause_sec,
      terminate_on = c(400, 401, 403, 404)  # Don't retry client errors
    )

    # Check response status
    if (httr::status_code(resp) != 200) {
      warning(
        "Failed to fetch ", next_url,
        "; status: ", httr::status_code(resp)
      )
      break
    }

    # Parse JSON response
    parsed <- httr::content(resp, as = "parsed", type = "application/json")

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
#' # Connect to Cologne OParl API
#' system <- oparl_connect("https://ratsinformation.stadt-koeln.de/oparl/system")
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
    tibble(
      id = item$id %||% NA_character_,
      name = item$name %||% NA_character_,
      number = item$number %||% NA_character_,
      public = as.logical(item$public %||% NA),
      result = item$result %||% NA_character_,
      consultation_url = as.character((item$consultation %||% list())[[1]] %||% NA_character_)
    )
  })
}

#' Parse OParl Papers to Data Frame
#'
#' Converts a list of OParl paper/document objects to a tidy data frame.
#'
#' @param papers_list List of OParl paper objects
#'
#' @return Tibble with paper information
#'
#' @export
parse_papers <- function(papers_list) {
  purrr::map_dfr(papers_list, function(p) {
    tibble(
      id = p$id %||% NA_character_,
      name = p$name %||% p$title %||% NA_character_,
      published = p$publishedDate %||% p$created %||% NA_character_
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
