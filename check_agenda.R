#!/usr/bin/env Rscript
# Check agenda items in raw meetings data

meetings_raw <- readRDS('data-raw/council_meetings/augsburg_meetings_raw.rds')

cat('Total meetings:', length(meetings_raw), '\n')

# Check how many have agendaItem
has_agenda <- sapply(meetings_raw, function(m) !is.null(m$agendaItem))
cat('Meetings with agendaItem field:', sum(has_agenda), '\n\n')

if(sum(has_agenda) > 0) {
  # Look at first meeting with agenda
  sample_meeting <- meetings_raw[has_agenda][[1]]

  cat('Beispiel Meeting:\n')
  cat('  ID:', sample_meeting$id, '\n')
  cat('  Name:', sample_meeting$name, '\n\n')

  cat('agendaItem content:\n')
  print(sample_meeting$agendaItem)

  cat('\nType:', class(sample_meeting$agendaItem), '\n')
  cat('Length:', length(sample_meeting$agendaItem), '\n')

  # Check first 5 meetings
  cat('\n\nFirst 5 meetings with agenda:\n')
  for(i in 1:min(5, sum(has_agenda))) {
    m <- meetings_raw[has_agenda][[i]]
    cat('\n', i, ':', m$name, '\n')
    cat('   agendaItem type:', class(m$agendaItem), '\n')
    cat('   agendaItem length:', length(m$agendaItem), '\n')
    if(is.character(m$agendaItem) && length(m$agendaItem) == 1) {
      cat('   ✅ Valid single URL\n')
    } else {
      cat('   ❌ NOT a single URL string\n')
      cat('   Content:', str(m$agendaItem), '\n')
    }
  }
} else {
  cat('❌ NO meetings have agendaItem field!\n')
}
