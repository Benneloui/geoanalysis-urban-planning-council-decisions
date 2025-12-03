# OParl API Guide - Stadt Augsburg

## Quick Start: How to Use This API

This API lets you access all public political documents, meetings, and decisions from Augsburg's city council.

### Basic Concept

- **Get all meetings** → Call `https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1`
- **Download a PDF document** → Find the paper, get its `mainFile.accessUrl`, then download it
- **See what was discussed in a meeting** → Get the meeting, then fetch its `agendaItem` list
- **Find all documents about a topic** → Search through papers using the papers endpoint
- **Track a specific committee** → Get organizations, find your committee, then get its meetings

### Step-by-Step Examples

#### Example 1: Getting Today's Meetings

**What you want:** See what meetings are happening today.

**How to do it:**
1. Call: `GET https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1`
2. You get: A list of meetings with dates, names, and locations
3. Filter by date: Look for `start` field matching today's date

```bash
curl 'https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1'
```

#### Example 2: Downloading a Document

**What you want:** Download a PDF of a specific proposal or document.

**How to do it:**
1. Call: `GET https://www.augsburg.sitzung-online.de/public/oparl/papers?body=1`
2. Find the paper you want by looking at `name` or `reference`
3. Get the `mainFile.accessUrl` from that paper
4. Download: Open that URL in your browser or use curl

```python
import requests

# Get papers
papers = requests.get('https://www.augsburg.sitzung-online.de/public/oparl/papers?body=1').json()
first_paper = papers['data'][0]

# Download the PDF
pdf_url = first_paper['mainFile']['accessUrl']
pdf_response = requests.get(pdf_url)
with open('document.pdf', 'wb') as f:
    f.write(pdf_response.content)
```

#### Example 3: Finding All Documents About a Topic

**What you want:** Find all papers that mention "Verkehr" (traffic).

**How to do it:**
1. Call: `GET https://www.augsburg.sitzung-online.de/public/oparl/papers?body=1`
2. Loop through all pages (check `links.next` for pagination)
3. For each paper, check if `name` contains your keyword
4. Collect matching papers and their PDF links

---

## System Information

- **Name:** ALLRIS OParl der Stadt Augsburg
- **OParl Version:** https://schema.oparl.org/1.1/
- **Vendor:** https://www.cc-egov.de
- **Product:** https://cc-egov.de/de-de/produkte/allris
- **License:** https://creativecommons.org/licenses/by/4.0/
- **Contact:** info@augsburg.de
- **Website:** https://www.augsburg.sitzung-online.de/public/
- **API Endpoint:** `https://www.augsburg.sitzung-online.de/public/oparl/system`

## API Capabilities & Available Data

This OParl API provides access to the following data types:

✅ **Bodies** - Political bodies and their structure
✅ **Organizations** - 10 organizations found
✅ **Persons** - 0 persons found
✅ **Meetings** - 10 meetings found
✅ **Papers** - 10 papers/documents found

**Total API Calls Made:** 5

## Bodies (Gremien)

Found **1** bodies.

### Body 1: Stadt Augsburg

- **ID:** `https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1`
- **Short Name:** 01
- **AGS:** None

**Available Endpoints:**
- Organizations: `https://www.augsburg.sitzung-online.de/public/oparl/organizations?body=1`
- Persons: `https://www.augsburg.sitzung-online.de/public/oparl/persons?body=1`
- Meetings: `https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1`
- Papers: `https://www.augsburg.sitzung-online.de/public/oparl/papers?body=1`

## Organizations

Total organizations found: **10**

**Sample Organizations:**
- Stadtrat Augsburg
- Allgemeiner Ausschuss
- Ausschuss für Bildung und Migration (Bildungsausschuss)
- Ausschuss für Digitalisierung, Organisation, Personal (DOPA)
- Bau-, Hochbau- und Konversionsausschuss (Bauausschuss)

## Persons

Total persons found: **0**

**Sample Persons:**

## Meetings (Sitzungen)

Total meetings found: **10**

**Sample Meetings:**

### Meeting 1
- **Name:** Sitzung des Ausschusses für Digitalisierung, Organisation, Personal
- **Date:** 2027-12-01T14:30:00+01:00
- **Location:** None
- **Has Agenda Items:** No
- **Has Invitation:** No
- **Has Results Protocol:** No

### Meeting 2
- **Name:** Stadtrat Augsburg (ganztägig)
- **Date:** 2026-12-17T09:00:00+01:00
- **Location:** None
- **Has Agenda Items:** No
- **Has Invitation:** No
- **Has Results Protocol:** No

### Meeting 3
- **Name:** Wirtschaftsförderungs-, Beteiligungs- und Liegenschaftsausschuss
- **Date:** 2026-12-16T09:30:00+01:00
- **Location:** None
- **Has Agenda Items:** No
- **Has Invitation:** No
- **Has Results Protocol:** No

## Papers (Vorlagen/Dokumente)

Total papers found: **10**

**Sample Papers:**

### Paper 1
- **Name:** Zukunftsbericht Integration-Wegweiser für eine Kommune (Fortschreibung Integrationsbericht)
- **Reference:** TVO-BSV/25/61736-2
- **Type:** Tischvorlage
- **Has Main File:** Yes
- **Has Auxiliary Files:** No

### Paper 2
- **Name:** Antrag der Stadtratsfraktion BÜNDNIS 90/DIE GRÜNEN vom 27.11.2025: Zweckentfremdungssatzung
- **Reference:** ANT/25/61800
- **Type:** Antrag im Sinne von § 33 Abs. 1 GeschO (öffentlich)
- **Has Main File:** Yes
- **Has Auxiliary Files:** No

### Paper 3
- **Name:** Anfrage Fraktion Bürgerliche Mitte: Herkunftsstadtteile der Realschüler/innen, die derzeit in Landkreisschulen pendeln – Standortplanung neue Realschule Ost
- **Reference:** ANF/25/61796
- **Type:** Anfrage im Sinne von § 33a GeschO (öffentlich)
- **Has Main File:** Yes
- **Has Auxiliary Files:** No

## Understanding Object Relationships

### How Objects Connect

**The most important fields to know:**

- **`id`**: Unique URL for this object (save this to fetch it again later)
- **`name`/`title`**: Human-readable name (what you show to users)
- **`type`**: What kind of object this is (Meeting, Paper, etc.)
- **`created`/`modified`**: When it was created/updated (for syncing)
- **`deleted`**: If true, skip this object (it was removed)

**For files/PDFs:**
- **`accessUrl`**: Direct link to download PDF
- **`mimeType`**: File type (usually "pdf")
- **`size`**: File size in bytes
- **`fileName`**: Original filename

**For dates:**
- **`start`/`end`**: Meeting times
- **`date`**: Paper/document date
- Format: ISO 8601 (YYYY-MM-DDTHH:MM:SS+TZ)

### Relationships Between Objects

```
System
 └── Body (Stadt Augsburg)
      ├── Organizations (Committees)
      │    └── Meetings
      ├── Persons (Politicians)
      ├── Meetings
      │    └── AgendaItems (Topics)
      │         ├── Consultation (How it was handled)
      │         └── Files (auxiliary documents)
      └── Papers (Proposals/Documents)
           ├── MainFile (the main PDF)
           ├── AuxiliaryFiles (attachments)
           └── Consultation (links to meetings)
```

## Complete Workflows: From Question to Answer

### Workflow 1: "I want to know what the city council decided about traffic last month"

**Step-by-step:**

1. **Get all meetings from last month:**
   ```
   GET https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1
   ```
   You get: List of meetings with dates

2. **Filter meetings by date:**
   Look at the `start` field of each meeting, keep only those from last month

3. **For each meeting, get the agenda items:**
   Check if meeting has `agendaItem` field
   ```
   GET [meeting's agendaItem URL]
   ```
   You get: List of topics discussed

4. **Search agenda items for "Verkehr" (traffic):**
   Look at each item's `name` field

5. **Get the documents:**
   Each agenda item may have `consultation` which links to `paper`
   From paper, get `mainFile.accessUrl` to download PDF

### Workflow 2: "I want to download all PDFs from the education committee"

**Step-by-step:**

1. **Find the education committee:**
   ```
   GET https://www.augsburg.sitzung-online.de/public/oparl/organizations?body=1
   ```
   You get: List of all committees/organizations
   Look for one with "Bildung" in the name

2. **Get meetings of that committee:**
   ```
   GET [organization's meeting URL]
   ```
   You get: All meetings of that committee

3. **For each meeting, get papers:**
   If meeting has `invitation` or `resultsProtocol`, those are files
   Get agenda items, then their consultations, then papers

4. **Download all PDFs:**
   From each paper's `mainFile.accessUrl`, download the PDF

### Workflow 3: "I want to track when specific topics are discussed"

**Step-by-step:**

1. **Get all upcoming meetings:**
   ```
   GET https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1
   ```
   Filter by `start` date in the future

2. **For each meeting, check if it has agenda items:**
   Some meetings may not have agenda items published yet

3. **Search agenda item names for your keywords:**
   Check `name` field of each agenda item

4. **Get notification details:**
   Save: meeting name, date, location, agenda item name, paper reference

### Workflow 4: "I want to build a searchable database"

**Step-by-step:**

1. **Download all papers:**
   ```
   GET https://www.augsburg.sitzung-online.de/public/oparl/papers?body=1
   ```
   Loop through pages using `links.next`

2. **For each paper:**
   - Save metadata: name, reference, date, paperType
   - Download PDF from `mainFile.accessUrl`
   - Extract text using a PDF library (PyMuPDF, pdfplumber)

3. **Store in database:**
   - Save to Parquet (for analysis) or PostgreSQL (for search)
   - Create full-text search index

4. **Link relationships:**
   - Paper → Consultation → AgendaItem → Meeting → Organization
   - Store these links to enable queries like "all papers discussed by committee X"

---

## Understanding the Data Flow

```
You want to know: "What did they decide?"
     ↓
1. Get MEETING (when did they meet?)
     ↓
2. Get AGENDA ITEMS (what did they discuss?)
     ↓
3. Get CONSULTATION (how did they handle it?)
     ↓
4. Get PAPER (what was the proposal?)
     ↓
5. Get FILE/PDF (read the details)
```

## API Response Patterns

### Pattern 1: List Endpoints
When you call a list endpoint (meetings, papers, organizations), you get:
```json
{
  "data": [ /* array of items */ ],
  "links": {
    "next": "URL to next page",
    "prev": "URL to previous page"
  },
  "pagination": { /* optional */ }
}
```

**What to do:** Loop through pages using `links.next` until it's null/empty

### Pattern 2: Single Object
When you fetch a specific item by URL, you get just the object:
```json
{
  "id": "...",
  "type": "...",
  /* object properties */
}
```

### Pattern 3: Relationships
Objects reference other objects via URLs:
```json
{
  "id": "...",
  "meeting": "https://...../meetings?id=123",  // ← fetch this URL
  "organization": [                             // ← array of URLs
    "https://...../organizations?id=456"
  ]
}
```

**What to do:** Make another API call to that URL to get the related object

## Troubleshooting & Common Issues

### Issue 1: "I get too much data, how do I filter?"
**Problem:** API returns hundreds of items, you only want recent ones

**Solution:**
- After getting data, filter by date fields: `start`, `date`, `created`, `modified`
- Example: Only meetings after 2025-01-01:
  ```python
  meetings = [m for m in data['data'] if m['start'] >= '2025-01-01']
  ```

### Issue 2: "The data has weird characters (Ã¼, â€)"
**Problem:** Text encoding issues

**Solution:**
- Make sure you're using UTF-8 encoding when reading/writing
- In Python: `response.json()` handles this automatically
- When saving to file: `open('file.txt', 'w', encoding='utf-8')`

### Issue 3: "Some meetings don't have agenda items"
**Problem:** Not all meetings have published agendas yet

**Solution:**
- Always check if field exists before accessing: `if 'agendaItem' in meeting:`
- Future meetings may not have agendas published
- Past meetings should have complete data

### Issue 4: "I need to make hundreds of API calls"
**Problem:** Building relationships requires many requests

**Solution:**
- Add delays between requests (0.5-1 second): `time.sleep(0.5)`
- Cache results: Don't fetch the same URL twice
- Use batch processing: Process 10-20 items, then take a break

### Issue 5: "Download URLs don't work"
**Problem:** Some PDFs return 403 or 404

**Solution:**
- Use `accessUrl` not `downloadUrl` (downloadUrl is often empty)
- Add user agent header: `headers={'User-Agent': 'MyApp/1.0'}`
- Some documents may be restricted or deleted (`deleted: true`)

## Practical Tips

1. **Start Small:** Test with one meeting or one paper before processing everything
2. **Save Progress:** When downloading many PDFs, save which ones you've done
3. **Handle Pagination:** Always loop through `links.next` for complete data
4. **Check Deleted Flag:** Skip items where `deleted: true`
5. **Use Timestamps:** `modified` field helps you sync only changed data

---

### System Example

```json
{
  "id": "https://www.augsburg.sitzung-online.de/public/oparl/system",
  "type": "https://schema.oparl.org/1.1/System",
  "oparlVersion": "https://schema.oparl.org/1.1/",
  "license": "https://creativecommons.org/licenses/by/4.0/ ",
  "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies",
  "name": "ALLRIS OParl der Stadt Augsburg",
  "contactEmail": "info@augsburg.de",
  "contactName": "Stadt Augsburg",
  "website": "https://www.augsburg.sitzung-online.de/public/",
  "vendor": "https://www.cc-egov.de",
  "product": "https://cc-egov.de/de-de/produkte/allris",
  "created": "2025-12-03T13:52:29+01:00",
  "modified": "2025-12-03T13:52:29+01:00",
  "web": "https://www.augsburg.sitzung-online.de/public/",
  "deleted": false
}
```

### Body Example

```json
{
  "id": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
  "type": "https://schema.oparl.org/1.1/Body",
  "system": "https://www.augsburg.sitzung-online.de/public/oparl/system",
  "shortName": "01",
  "name": "Stadt Augsburg",
  "organization": "https://www.augsburg.sitzung-online.de/public/oparl/organizations?body=1",
  "person": "https://www.augsburg.sitzung-online.de/public/oparl/persons?body=1",
  "meeting": "https://www.augsburg.sitzung-online.de/public/oparl/meetings?body=1",
  "paper": "https://www.augsburg.sitzung-online.de/public/oparl/papers?body=1",
  "legislativeTerm": [
    {
      "id": "https://www.augsburg.sitzung-online.de/public/oparl/legislativeTerms?id=1_1000003",
      "type": "https://schema.oparl.org/1.1/LegislativeTerm",
      "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
      "name": "15. WP",
      "startDate": "2026-05-01",
      "endDate": "2032-04-30",
      "created": "2025-12-03T13:52:30+01:00",
      "modified": "2025-06-26T14:58:47+02:00",
      "deleted": false
    },
    {
      "id": "https://www.augsburg.sitzung-online.de/public/oparl/legislativeTerms?id=1_1000001",
      "type": "https://schema.oparl.org/1.1/LegislativeTerm",
      "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
      "name": "14. WP",
      "startDate": "2020-05-01",
      "endDate": "2026-04-30",
      "created": "2025-12-03T13:52:30+01:00",
      "modified": "2025-12-03T13:08:31+01:00",
      "deleted": false
    },
    {
      "id": "https://www.augsburg.sitzung-online.de/public/oparl/legislativeTerms?id=1_2",
      "type": "https://schema.oparl.org/1.1/LegislativeTerm",
      "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
      "name": "13. WP",
      "startDate": "2014-05-01",
      "endDate": "2020-04-30",
      "created": "2025-12-03T13:52:30+01:00",
      "modified": "2025-12-03T13:52:30+01:00",
      "deleted": false
    },
    {
      "id": "https://www.augsburg.sitzung-online.de/public/oparl/legislativeTerms?id=1_1",
      "type": "https://schema.oparl.org/1.1/LegislativeTerm",
      "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
      "name": "12. WP",
      "startDate": "2008-05-01",
      "endDate": "2014-04-30",
      "created": "2025-12-03T13:52:30+01:00",
      "modified": "2025-12-03T13:52:30+01:00",
      "deleted": false
    }
  ],
  "agendaItem": "https://www.augsburg.sitzung-online.de/public/oparl/agendaItems?body=1",
  "consultation": "https://www.augsburg.sitzung-online.de/public/oparl/consultations?body=1",
  "file": "https://www.augsburg.sitzung-online.de/public/oparl/files?body=1",
  "locationList": "https://www.augsburg.sitzung-online.de/public/oparl/locations?body=1",
  "legislativeTermList": "https://www.augsburg.sitzung-online.de/public/oparl/legislativeTerms?body=1",
  "membership": "https://www.augsburg.sitzung-online.de/public/oparl/memberships?body=1",
  "location": {
    "id": "https://www.augsburg.sitzung-online.de/public/oparl/locations?id=15957",
    "type": "https://schema.oparl.org/1.1/Location",
    "created": "2025-12-03T13:52:30+01:00",
    "modified": "2025-12-03T13:52:30+01:00",
    "deleted": false
  },
  "web": "https://www.augsburg.sitzung-online.de/public/",
  "created": "2025-11-30T05:41:44+01:00",
  "modified": "2025-11-30T05:41:44+01:00",
  "deleted": false
}
```

### Organization Example

```json
{
  "id": "https://www.augsburg.sitzung-online.de/public/oparl/organizations?typ=gr&id=1",
  "type": "https://schema.oparl.org/1.1/Organization",
  "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
  "name": "Stadtrat Augsburg",
  "shortName": "Rat",
  "location": {
    "id": "https://www.augsburg.sitzung-online.de/public/oparl/locations?id=2",
    "type": "https://schema.oparl.org/1.1/Location",
    "created": "2025-12-03T13:52:31+01:00",
    "modified": "2025-12-03T13:52:31+01:00",
    "deleted": false
  },
  "startDate": "2006-07-19",
  "organizationType": "Hauptorgan",
  "classification": "Stadtrat",
  "meeting": "https://www.augsburg.sitzung-online.de/public/oparl/meetings?organization=1",
  "membership": [
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=2",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7683",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=5",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7685",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=8197",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=6",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7687",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=8",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7688",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7689",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=10",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7690",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=11",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7691",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=12",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7692",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=13",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7693",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=14",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=5646",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7694",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=15",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=5647",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7695",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=16",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=5648",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7696",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=17",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7697",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=18",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7698",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=19",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7699",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=20",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7700",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=21",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1045",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7701",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=22",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7702",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=23",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7703",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=24",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1048",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7704",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=25",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1049",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7705",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=26",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1050",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7706",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=27",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1051",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7707",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=28",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1052",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7708",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=29",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1053",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3613",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7709",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1054",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7710",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=31",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1055",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7711",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=32",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7712",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=33",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1057",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7713",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1058",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7714",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1059",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7715",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=36",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1060",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7716",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=37",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1061",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7717",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=38",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1062",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7718",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=39",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1063",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7719",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=40",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1064",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1065",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=42",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1066",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=43",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1067",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7723",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=44",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1068",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1069",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3629",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=46",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1070",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=47",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=1071",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=48",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=49",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=50",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=10290",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=51",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=52",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=53",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=54",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=55",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=56",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=57",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=5178",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=59",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=60",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3646",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3647",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3648",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3649",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3650",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=6722",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3651",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3652",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3653",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3654",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3655",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3656",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3658",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3659",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3660",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3661",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3662",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3663",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3152",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3664",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3665",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3666",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3667",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3668",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3669",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3670",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3671",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3672",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=2650",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3674",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3681",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3682",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=3683",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7355",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7356",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9973",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9974",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9975",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9976",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9977",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9978",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9979",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9980",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9981",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9982",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9983",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=9984",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=11015",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=11016",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=285",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=10072",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=2445",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=10710",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=995",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=996",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=997",
    "https://www.augsburg.sitzung-online.de/public/oparl/memberships?id=7670"
  ],
  "web": "https://www.augsburg.sitzung-online.de/public/gr020?GRLFDNR=1",
  "created": "2025-11-30T05:41:44+01:00",
  "modified": "2025-11-30T05:41:44+01:00",
  "deleted": false
}
```

### Person Example

```json
{}
```

### Meeting Example

```json
{
  "id": "https://www.augsburg.sitzung-online.de/public/oparl/meetings?id=1000066",
  "type": "https://schema.oparl.org/1.1/Meeting",
  "name": "Sitzung des Ausschusses für Digitalisierung, Organisation, Personal",
  "meetingState": "terminiert",
  "cancelled": false,
  "start": "2027-12-01T14:30:00+01:00",
  "end": "2027-12-02T00:00:00+01:00",
  "organization": [
    "https://www.augsburg.sitzung-online.de/public/oparl/organizations?typ=gr&id=164"
  ],
  "created": "2025-11-30T05:41:44+01:00",
  "modified": "2025-11-30T05:41:44+01:00",
  "deleted": false
}
```

### Paper Example

```json
{
  "id": "https://www.augsburg.sitzung-online.de/public/oparl/papers?id=1001737",
  "type": "https://schema.oparl.org/1.1/Paper",
  "body": "https://www.augsburg.sitzung-online.de/public/oparl/bodies?id=1",
  "name": "Zukunftsbericht Integration-Wegweiser für eine Kommune (Fortschreibung Integrationsbericht)",
  "reference": "TVO-BSV/25/61736-2",
  "date": "2025-12-01",
  "paperType": "Tischvorlage",
  "mainFile": {
    "id": "https://www.augsburg.sitzung-online.de/public/oparl/files?id=1059421&dtyp=130",
    "type": "https://schema.oparl.org/1.1/File",
    "name": "Sammeldokument öffentlich",
    "date": "2025-12-01",
    "fileName": "2025-12-01 TVO-BSV_25_61736-2 Zukunftsbericht Inte SAO.pdf",
    "mimeType": "pdf",
    "size": 3163823,
    "accessUrl": "https://www.augsburg.sitzung-online.de/public/doc?DOLFDNR=1059421&DOCTYP=130&OTYP=41&ANNOTS=1",
    "downloadUrl": "",
    "created": "2025-12-01T13:46:24+01:00",
    "modified": "2025-12-01T14:09:05+01:00",
    "deleted": false
  },
  "originatorPerson": [
    null
  ],
  "consultation": [
    {
      "id": "https://www.augsburg.sitzung-online.de/public/oparl/consultations?id=1001439&bi=1001359",
      "type": "https://schema.oparl.org/1.1/Consultation",
      "paper": "https://www.augsburg.sitzung-online.de/public/oparl/papers?id=1001737",
      "organization": [
        "https://www.augsburg.sitzung-online.de/public/oparl/organizations?typ=gr&id=160"
      ],
      "agendaItem": "https://www.augsburg.sitzung-online.de/public/oparl/agendaItems?id=1002246",
      "meeting": "https://www.augsburg.sitzung-online.de/public/oparl/meetings?id=2825",
      "authoritative": true,
      "role": "Entscheidung",
      "created": "2025-12-01T13:46:37+01:00",
      "modified": "2025-12-03T13:52:55+01:00",
      "deleted": false
    }
  ],
  "web": "https://www.augsburg.sitzung-online.de/public/vo020?VOLFDNR=1001737",
  "created": "2025-12-01T13:46:24+01:00",
  "modified": "2025-12-01T13:50:31+01:00",
  "deleted": false
}
```

---

## Quick Reference Cheat Sheet

| I want to... | Endpoint | What I get |
|-------------|----------|------------|
| See all meetings | `/meetings?body=1` | List of meetings with dates, names |
| See all documents | `/papers?body=1` | List of papers/proposals with titles |
| See all committees | `/organizations?body=1` | List of committees/councils |
| Get PDF of a paper | Get paper → `mainFile.accessUrl` | Direct PDF download link |
| See meeting agenda | Get meeting → `agendaItem` URL | List of topics discussed |
| Find committee meetings | Get org → `meeting` URL | Meetings of that committee |
| See meeting protocol | Get meeting → `resultsProtocol` | PDF of meeting minutes |
| Track a paper's journey | Paper → `consultation` → `agendaItem` | Where/when it was discussed |

## Main API Endpoints Summary

```
Base: https://www.augsburg.sitzung-online.de/public/oparl

/system                    → System info (start here)
/bodies                    → Get body/city info
/meetings?body=1           → All meetings
/papers?body=1             → All papers/documents
/organizations?body=1      → All committees/organizations
/persons?body=1            → All people (if available)
/agendaItems?body=1        → All agenda items
/files?body=1              → All files
```

---

*Generated by OParl API Analyzer*
*Total API calls made: 5*
*For questions or issues, contact: info@augsburg.de*
