# ============================================================================
# Visualization Functions
# ============================================================================
# Functions for creating consistent, publication-quality visualizations
# of spatial-temporal patterns in council decisions.
#
# Author: Benedikt Pilgram
# Date: October 2025
# ============================================================================

# Load required libraries
suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(sf)
})

# Color scheme for decision types
DECISION_COLORS <- c(
  "Beschlossen" = "#2ecc71",  # Green
  "Approved" = "#2ecc71",
  "Abgelehnt" = "#e74c3c",    # Red
  "Rejected" = "#e74c3c",
  "Vertagt" = "#f39c12",      # Orange
  "Postponed" = "#f39c12",
  "Withdrawn" = "#95a5a6"     # Gray
)

#' Create Temporal Trend Plot
#'
#' Creates a histogram showing the temporal distribution of decisions.
#'
#' @param df Data frame with 'date' and optionally 'decision_type' columns
#' @param bins Number of histogram bins (default: 12)
#' @param title Plot title
#' @param subtitle Plot subtitle
#' @param color_by Column name to color by (default: "decision_type")
#'
#' @return ggplot2 object
#'
#' @examples
#' df <- tibble(date = seq(as.Date("2023-01-01"), by = "month", length.out = 12),
#'              decision_type = "Beschlossen")
#' plot <- plot_temporal_trend(df)
#'
#' @export
plot_temporal_trend <- function(df,
                                bins = 12,
                                title = "Temporal Distribution of B-Plan Decisions",
                                subtitle = NULL,
                                color_by = "decision_type") {

  # Check if color column exists
  use_color <- color_by %in% names(df)

  # Get present decision types for legend
  if (use_color) {
    present_levels <- intersect(names(DECISION_COLORS), unique(df[[color_by]]))
    decision_colors <- DECISION_COLORS[present_levels]
  }

  # Create plot
  p <- ggplot(df, aes(x = date))

  if (use_color) {
    p <- p + geom_histogram(aes(fill = .data[[color_by]]), bins = bins, alpha = 0.8)
    if (length(present_levels) > 0) {
      p <- p + scale_fill_manual(values = decision_colors, breaks = present_levels)
    }
  } else {
    p <- p + geom_histogram(bins = bins, alpha = 0.8, fill = "#3498db")
  }

  p <- p +
    labs(
      title = title,
      subtitle = subtitle,
      x = "Date",
      y = "Number of Decisions",
      fill = if (use_color) "Decision Type" else NULL
    ) +
    theme_minimal() +
    theme(
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(size = 11),
      legend.position = "bottom"
    )

  p
}

#' Create District Frequency Plot
#'
#' Creates a horizontal bar chart showing decision frequency by district.
#'
#' @param df Data frame with 'district' and optionally 'decision_type' columns
#' @param title Plot title
#' @param subtitle Plot subtitle
#' @param color_by Column name to color by (default: "decision_type")
#'
#' @return ggplot2 object
#'
#' @export
plot_district_frequency <- function(df,
                                    title = "B-Plan Activity by District",
                                    subtitle = "Where are development plans being negotiated?",
                                    color_by = "decision_type") {

  # Check if color column exists
  use_color <- color_by %in% names(df)

  # Get present decision types
  if (use_color) {
    present_levels <- intersect(names(DECISION_COLORS), unique(df[[color_by]]))
    decision_colors <- DECISION_COLORS[present_levels]
  }

  # Count by district
  if (use_color) {
    plot_data <- df %>%
      count(district, .data[[color_by]])
  } else {
    plot_data <- df %>%
      count(district) %>%
      mutate(dummy_color = "All")
  }

  # Create plot
  p <- ggplot(plot_data, aes(x = reorder(district, n), y = n))

  if (use_color) {
    p <- p + geom_col(aes(fill = .data[[color_by]]), alpha = 0.8)
    if (length(present_levels) > 0) {
      p <- p + scale_fill_manual(values = decision_colors, breaks = present_levels)
    }
  } else {
    p <- p + geom_col(alpha = 0.8, fill = "#3498db")
  }

  p <- p +
    coord_flip() +
    labs(
      title = title,
      subtitle = subtitle,
      x = "District",
      y = "Number of Decisions",
      fill = if (use_color) "Decision Type" else NULL
    ) +
    theme_minimal() +
    theme(
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(size = 11),
      legend.position = "bottom"
    )

  p
}

#' Create Spatial Distribution Map
#'
#' Creates a map showing spatial distribution of decisions.
#'
#' @param sf_obj sf object with point geometries
#' @param color_by Column name to color by (default: "decision_type")
#' @param title Plot title
#' @param subtitle Plot subtitle
#' @param point_size Point size (default: 3)
#'
#' @return ggplot2 object
#'
#' @export
plot_spatial_map <- function(sf_obj,
                             color_by = "decision_type",
                             title = "Spatial Distribution of B-Plan Decisions",
                             subtitle = "Each point represents a council decision on a development plan",
                             point_size = 3) {

  # Check if color column exists
  use_color <- color_by %in% names(sf_obj)

  # Get present decision types
  if (use_color) {
    present_levels <- intersect(names(DECISION_COLORS), unique(sf_obj[[color_by]]))
    decision_colors <- DECISION_COLORS[present_levels]
  }

  # Create plot
  p <- ggplot(sf_obj)

  if (use_color) {
    p <- p + geom_sf(aes(color = .data[[color_by]]), size = point_size, alpha = 0.7)
    if (length(present_levels) > 0) {
      p <- p + scale_color_manual(values = decision_colors, breaks = present_levels)
    }
  } else {
    p <- p + geom_sf(size = point_size, alpha = 0.7, color = "#3498db")
  }

  p <- p +
    labs(
      title = title,
      subtitle = subtitle,
      color = if (use_color) "Decision Type" else NULL
    ) +
    theme_minimal() +
    theme(
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(size = 11),
      legend.position = "bottom",
      axis.text = element_blank(),
      axis.title = element_blank(),
      panel.grid = element_line(color = "gray90")
    ) +
    guides(size = "none")

  p
}

#' Save Plot to File
#'
#' Saves a ggplot object with consistent settings.
#'
#' @param plot ggplot2 object
#' @param filename Output filename
#' @param width Plot width in inches (default: 10)
#' @param height Plot height in inches (default: 8)
#' @param dpi Resolution in DPI (default: 300 for publication quality)
#' @param output_dir Output directory (default: "outputs/figures")
#'
#' @export
save_plot <- function(plot,
                     filename,
                     width = 10,
                     height = 8,
                     dpi = 300,
                     output_dir = "outputs/figures") {

  # Create output directory if it doesn't exist
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Construct full path
  filepath <- file.path(output_dir, filename)

  # Save plot
  ggplot2::ggsave(
    filepath,
    plot,
    width = width,
    height = height,
    dpi = dpi
  )

  cat("Plot saved to:", filepath, "\n")
  invisible(filepath)
}

#' Create Summary Statistics Table
#'
#' Generates summary statistics from spatial-temporal data.
#'
#' @param df Data frame with date, district, and decision_type columns
#'
#' @return Tibble with summary statistics
#'
#' @export
create_summary_stats <- function(df) {
  if (nrow(df) == 0) {
    return(tibble(
      total_decisions = 0,
      districts_covered = 0,
      date_range_start = as.Date(NA),
      date_range_end = as.Date(NA),
      approved_pct = NA_real_,
      rejected_pct = NA_real_,
      postponed_pct = NA_real_
    ))
  }

  # Calculate percentages for German and English decision types
  approved_count <- sum(
    df$decision_type %in% c("Beschlossen", "Approved"),
    na.rm = TRUE
  )
  rejected_count <- sum(
    df$decision_type %in% c("Abgelehnt", "Rejected"),
    na.rm = TRUE
  )
  postponed_count <- sum(
    df$decision_type %in% c("Vertagt", "Postponed"),
    na.rm = TRUE
  )

  df %>%
    summarise(
      total_decisions = n(),
      districts_covered = n_distinct(district, na.rm = TRUE),
      date_range_start = min(date, na.rm = TRUE),
      date_range_end = max(date, na.rm = TRUE),
      approved_pct = round(100 * approved_count / n(), 1),
      rejected_pct = round(100 * rejected_count / n(), 1),
      postponed_pct = round(100 * postponed_count / n(), 1)
    )
}

#' Print Summary Statistics
#'
#' Prints formatted summary statistics to console.
#'
#' @param summary_stats Tibble from create_summary_stats()
#'
#' @export
print_summary_stats <- function(summary_stats) {
  cat("📊 SUMMARY STATISTICS:\n")
  cat("   Total B-Plan decisions:", summary_stats$total_decisions, "\n")
  cat("   Districts covered:", summary_stats$districts_covered, "\n")

  if (!is.na(summary_stats$date_range_start) && !is.na(summary_stats$date_range_end)) {
    cat("   Time period:", format(summary_stats$date_range_start, "%Y-%m-%d"), "to",
        format(summary_stats$date_range_end, "%Y-%m-%d"), "\n")
  } else {
    cat("   Time period: n/a\n")
  }

  cat("   Approval rate:", summary_stats$approved_pct, "%\n")
  cat("   Rejection rate:", summary_stats$rejected_pct, "%\n")
  cat("   Postponement rate:", summary_stats$postponed_pct, "%\n\n")
}
