# Changes Summary - locations_table.csv Removal

## What Changed?

### 1. ✅ Removed locations_table.csv Export

**Files Modified:**
- `scripts/run_pipeline.py` - Removed `_export_locations()` method and call
- `src/storage.py` - Updated `export_locations_for_map()` to work directly with papers
- `PIPELINE_WORKFLOW.md` - Removed all references to locations_table.csv

**Why?**
You'll analyze Parquet data directly in Jupyter notebooks instead of using an intermediate CSV file. This is more efficient and flexible!

### 2. ✅ Updated GeoJSON Export

**What's New:**
- GeoJSON is now generated directly from Parquet data
- Each location marker includes PDF link to original document
- No intermediate locations_table needed

### 3. ✅ Created Analysis Notebook

**New File:** `notebooks/02_test_pipeline_output.ipynb`

This comprehensive notebook includes:

#### 📊 **Section 1-5: Parquet Analysis**
- Load council data from Parquet
- Show statistics (papers, locations, geocoding success rate)
- Display top mentioned locations
- Breakdown by source (gazetteer vs other)

#### 🗺️ **Section 6: Interactive Map**
- Loads GeoJSON with location data
- Creates Folium map centered on Augsburg
- Each marker shows:
  - Location name
  - Paper title and date
  - **Clickable PDF link** 📄
- Tooltip on hover

#### 🔗 **Section 7-8: RDF Conversion**
- Converts N-Triples (.nt) → Turtle (.ttl)
- Adds proper namespace prefixes
- Shows sample output
- **Ready for YASGUI upload!**

#### 📝 **Section 8: YASGUI Instructions**
Includes example SPARQL queries:
- Count all papers
- List papers with titles and dates
- Find papers mentioning specific locations

#### 📦 **Section 9-10: Summary & Next Steps**
- File size overview
- Next steps for full pipeline run
- Ideas for deeper analysis

---

## How to Use

### Step 1: Run Test Pipeline (10 PDFs)

```bash
cd /Users/benedikt.pilgram/Code/OPARL_Analysis_AuX
python scripts/run_pipeline.py --test --limit 10
```

**Expected Output Files:**
- `data/processed/council_data.parquet` - Main data (partitioned)
- `data/processed/metadata.nt` - RDF N-Triples
- `data/processed/augsburg_map.geojson` - Map data with PDF links

**Estimated Time:** 2-3 minutes

---

### Step 2: Open Analysis Notebook

```bash
jupyter notebook notebooks/02_test_pipeline_output.ipynb
```

Or in VS Code:
1. Open `notebooks/02_test_pipeline_output.ipynb`
2. Select Python kernel
3. Run all cells (Ctrl+Shift+Enter or Run All)

---

### Step 3: Explore Results

**In the notebook you'll see:**

1. ✅ How many papers were processed
2. ✅ How many locations were extracted
3. ✅ Geocoding success rate (should be ~95%+ with gazetteer!)
4. ✅ Top 10 most mentioned locations
5. ✅ Interactive map with clickable PDF links
6. ✅ Turtle file ready for YASGUI

---

### Step 4: Upload to YASGUI

1. Open: https://yasgui.triply.cc/
2. Go to "Data" tab
3. Upload: `data/processed/metadata.ttl`
4. Run SPARQL queries (examples in notebook!)

**Test Query:**
```sparql
PREFIX oparl: <http://oparl.org/schema/1.1/>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?paper ?title ?date
WHERE {
  ?paper a oparl:Paper ;
         dct:title ?title ;
         dct:date ?date .
}
ORDER BY DESC(?date)
LIMIT 10
```

---

## Pipeline Stages (Updated)

The pipeline now has **7 stages** (was 8):

1. ✅ Fetch papers from OParl API
2. ✅ Extract text from PDFs
3. ✅ Extract locations (gazetteer-based)
4. ✅ Geocode locations (minimal - mostly from gazetteer!)
5. ✅ Write to Parquet
6. ✅ Write to RDF (N-Triples)
7. ✅ Generate GeoJSON with PDF links

**Removed:** ~~Export locations_table.csv~~ (analyze Parquet directly instead)

---

## Benefits of This Approach

### 🚀 **Performance**
- No intermediate CSV generation
- Direct Parquet → GeoJSON conversion
- Faster pipeline execution

### 📊 **Flexibility**
- Analyze raw Parquet data with full power of pandas
- Custom filtering, grouping, aggregations
- No pre-aggregated CSV constraints

### 🔗 **Better Integration**
- GeoJSON includes PDF links directly
- Click on map marker → opens original PDF
- Easy verification of extracted locations

### 🎯 **Research Focus**
- All data in one place (Parquet)
- Custom analysis for your research questions
- Export subsets as needed (CSV, Excel, etc.)

---

## What to Check in the Notebook

### ✅ **Data Quality Checks:**

1. **Geocoding Success Rate**
   - Should be 90-95%+ (thanks to gazetteer!)
   - If lower: check which locations failed

2. **Location Source Breakdown**
   - Most should be `source: "gazetteer"`
   - Few should need Nominatim fallback

3. **Top Locations**
   - Should be real Augsburg streets (Ludwigstraße, Königsplatz, etc.)
   - NOT garbage words (Arbeitsplatz, Prozent, Politik) ❌

4. **PDF Links**
   - Click on map markers
   - Verify PDF opens correctly
   - Check if location is actually in the document

5. **RDF Triples**
   - Valid Turtle syntax
   - Proper namespace prefixes
   - Geographic coordinates in WKT format

---

## Next Steps

### ✅ **After Test Validation:**

1. **Run Full Pipeline** (6 months):
   ```bash
   python scripts/run_pipeline.py --city augsburg
   ```

2. **Analyze Full Dataset:**
   - Re-run notebook on complete data
   - Temporal patterns (which months/areas most active?)
   - Spatial clusters (where do decisions concentrate?)

3. **Research Analysis:**
   - Heatmaps of council activity
   - Time-series of location mentions
   - Topic modeling + spatial analysis

4. **Share Results:**
   - Upload TTL to public SPARQL endpoint
   - Export GeoJSON to web dashboard
   - Publish findings with interactive maps

---

## Troubleshooting

### **Issue:** No locations found
**Solution:**
- Check if PDFs have extractable text (not scanned images)
- Verify gazetteer loaded correctly (1509 streets)
- Check blocklist isn't too aggressive

### **Issue:** Low geocoding rate
**Solution:**
- Most locations should be from gazetteer (no geocoding needed)
- If many "unknown" locations, check text extraction quality

### **Issue:** Map shows no markers
**Solution:**
- Verify GeoJSON file exists and has features
- Check if locations have coordinates (latitude/longitude)
- Look for errors in pipeline logs

### **Issue:** Turtle file won't load in YASGUI
**Solution:**
- Check file size (might be too large for browser)
- Verify Turtle syntax (should be valid)
- Try smaller subset first (test run with --limit 5)

---

## Files Overview

```
data/processed/
├── council_data.parquet/         # Main data (partitioned by city/year/month)
│   └── city=augsburg/
│       └── year=2025/
│           └── month=06/
│               └── part-0.parquet
├── metadata.nt                   # RDF N-Triples (append-only)
├── metadata.ttl                  # RDF Turtle (converted in notebook)
├── augsburg_map.geojson          # Map data with PDF links
└── pipeline_state.db             # State tracking (crash recovery)

notebooks/
└── 02_test_pipeline_output.ipynb  # Analysis notebook (NEW!)
```

---

## Ready to Test!

Run the pipeline and open the notebook:

```bash
# Terminal 1: Run pipeline
python scripts/run_pipeline.py --test --limit 10

# Terminal 2: Start Jupyter (or use VS Code)
jupyter notebook notebooks/02_test_pipeline_output.ipynb
```

🎉 **Happy Analyzing!**
