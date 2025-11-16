#!/usr/bin/env Rscript
# Quick test of meeting fetch

library(httr)
library(jsonlite)

source("R/utils.R")
source("R/oparl_api.R")

cat("Testing Augsburg Meeting Fetch\n")
cat("================================\n\n")

# Connect
cat("1. Connecting to system...\n")
system_info <- oparl_connect("https://www.augsburg.sitzung-online.de/public/oparl/system", timeout_sec = 30)
cat("   Connected to:", system_info$name, "\n\n")

# Get bodies
cat("2. Fetching bodies...\n")
bodies <- fetch_bodies(system_info)
body <- bodies[[1]]
cat("   Body:", body$name, "\n")
cat("   Meeting URL:", body$meeting, "\n\n")

# Try to fetch meetings
cat("3. Fetching first page of meetings (with filter)...\n")
meetings_list <- oparl_fetch_all(
  body$meeting,
  query = list(modified_since = "2020-01-01T00:00:00Z"),
  max_pages = 1,  # Only 1 page for testing
  max_items = 20,
  timeout_sec = 60,
  retries = 2
)

cat("✅ SUCCESS! Fetched", length(meetings_list), "meetings\n")
