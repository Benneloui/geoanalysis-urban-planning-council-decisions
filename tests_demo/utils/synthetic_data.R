# ============================================================================
# Synthetic Data Generator
# ============================================================================
# Generates synthetic Bebauungsplan data for demonstration and testing purposes.
# Useful when real data is not available or for reproducible examples.
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(tibble)
  library(dplyr)
})

#' Generate Synthetic Bebauungsplan Data
#'
#' Creates synthetic development plan (Bebauungsplan) data for Cologne districts.
#' Useful for testing and demonstration when real OParl data is not available.
#'
#' @param n_items Number of synthetic items to generate (default: 15)
#' @param start_date Start date for temporal distribution (default: "2023-01-15")
#' @param freq Frequency of dates: "month", "week", "day" (default: "month")
#' @param decision_probs Probability vector for c(Beschlossen, Abgelehnt, Vertagt)
#'
#' @return Tibble with synthetic B-Plan data
#'
#' @examples
#' synthetic <- generate_synthetic_bplan_data(n_items = 20)
#' synthetic_weekly <- generate_synthetic_bplan_data(freq = "week")
#'
#' @export
generate_synthetic_bplan_data <- function(n_items = 15,
                                          start_date = "2023-01-15",
                                          freq = "month",
                                          decision_probs = c(0.7, 0.1, 0.2)) {

  # Cologne districts
  districts <- c(
    "Innenstadt", "Altstadt-Nord", "Altstadt-Süd", "Deutz", "Kalk",
    "Mülheim", "Ehrenfeld", "Nippes", "Lindenthal", "Rodenkirchen",
    "Sülz", "Porz", "Chorweiler", "Poll", "Bayenthal"
  )

  # Plan types
  plan_types <- c(
    "Wohngebiet", "Wohnsiedlung", "Wohnbebauung", "Wohnpark",
    "Gewerbegebiet", "Gewerbefläche", "Mischgebiet",
    "Quartiersplatz", "Zentrum", "Neubaugebiet",
    "Verdichtung", "Einzelhandel", "Naturschutz"
  )

  # Use only as many districts as items
  use_districts <- if (n_items <= length(districts)) {
    districts[1:n_items]
  } else {
    sample(districts, n_items, replace = TRUE)
  }

  # Generate plan names
  names <- paste0(
    "Bebauungsplan ",
    use_districts,
    " ",
    sample(plan_types, n_items, replace = TRUE)
  )

  # Generate dates
  dates <- seq(as.Date(start_date), by = freq, length.out = n_items)

  # Generate decision types
  decision_types <- sample(
    c("Beschlossen", "Abgelehnt", "Vertagt"),
    n_items,
    replace = TRUE,
    prob = decision_probs
  )

  # Create tibble
  tibble(
    id = paste0("synthetic_", 1:n_items),
    name = names,
    district = use_districts,
    date = dates,
    decision_type = decision_types
  )
}

#' Generate Synthetic Data with Specific Pattern
#'
#' Creates synthetic data with a predetermined pattern for specific testing scenarios.
#'
#' @return Tibble with 15 synthetic B-Plan items
#'
#' @export
generate_demo_bplan_data <- function() {
  tibble(
    id = paste0("synthetic_", 1:15),
    name = c(
      "Bebauungsplan Innenstadt-West Nr. 1234",
      "B-Plan Wohnsiedlung Altstadt-Nord",
      "Bebauungsplan Gewerbegebiet Deutz",
      "B-Plan Kalk-Ost Wohngebiet",
      "Bebauungsplan Mülheim Zentrum",
      "B-Plan Ehrenfeld Quartiersplatz",
      "Bebauungsplan Nippes Wohnbebauung",
      "B-Plan Lindenthal Mischgebiet",
      "Bebauungsplan Rodenkirchen Gewerbefläche",
      "B-Plan Sülz Neubaugebiet",
      "Bebauungsplan Porz Verdichtung",
      "B-Plan Chorweiler Wohnpark",
      "Bebauungsplan Poll Einzelhandel",
      "B-Plan Bayenthal Naturschutz",
      "Bebauungsplan Altstadt-Süd Wohnen"
    ),
    district = c(
      "Innenstadt", "Altstadt-Nord", "Deutz", "Kalk", "Mülheim",
      "Ehrenfeld", "Nippes", "Lindenthal", "Rodenkirchen", "Sülz",
      "Porz", "Chorweiler", "Poll", "Bayenthal", "Altstadt-Süd"
    ),
    date = seq(as.Date("2023-01-15"), by = "month", length.out = 15),
    decision_type = sample(
      c("Beschlossen", "Abgelehnt", "Vertagt"),
      15,
      replace = TRUE,
      prob = c(0.7, 0.1, 0.2)
    )
  )
}

#' Check if Synthetic Data Should Be Used
#'
#' Determines whether to use synthetic data based on real data availability.
#'
#' @param real_data Data frame of real data
#' @param min_threshold Minimum number of rows to consider real data sufficient
#' @param use_synthetic_override Logical, force use of synthetic data (default: NULL)
#'
#' @return Logical, TRUE if synthetic data should be used
#'
#' @export
should_use_synthetic <- function(real_data,
                                 min_threshold = 5,
                                 use_synthetic_override = NULL) {

  # If override is specified, use it
  if (!is.null(use_synthetic_override)) {
    return(use_synthetic_override)
  }

  # Otherwise, check if real data is sufficient
  nrow(real_data) < min_threshold
}
