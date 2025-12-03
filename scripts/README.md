# Pipeline Scripts

## Overview

This directory contains the main orchestration scripts for the OParl data pipeline.

## Main Script: `run_pipeline.py`

The primary entry point that coordinates all pipeline stages:

1. **Fetch** papers from OParl API (streaming)
2. **Extract** text from PDFs (in-memory)
3. **Extract** spatial entities (addresses, B-Pläne, Flurnummern)
4. **Geocode** locations with hierarchical fallback
5. **Write** to Parquet (partitioned by city/year)
6. **Write** to RDF (N-Triples → Turtle)
7. **Export** locations table for analysis
8. **Generate** GeoJSON for web mapping

## Quick Start

```bash
# Basic run with defaults from config.yaml
python scripts/run_pipeline.py

# Test run (10 papers only)
python scripts/run_pipeline.py --test

# Custom date range
python scripts/run_pipeline.py \
    --start-date 2024-01-01T00:00:00Z \
    --end-date 2024-12-31T23:59:59Z

# Process 100 papers maximum
python scripts/run_pipeline.py --limit 100

# Custom batch size (for memory management)
python scripts/run_pipeline.py --batch-size 25
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Path to config.yaml | `config.yaml` |
| `--city NAME` | City to process | From config |
| `--start-date DATE` | Start date (ISO 8601) | From config |
| `--end-date DATE` | End date (ISO 8601) | From config |
| `--limit N` | Max papers to process | Unlimited |
| `--batch-size N` | Papers per batch | 50 |
| `--no-skip-existing` | Reprocess all papers | Skip existing |
| `--test` | Test mode (10 papers) | Full run |
| `--reprocess-failed` | Retry failed papers | Skip failed |

## Examples

### Test Run

Quick test with 10 papers:

```bash
python scripts/run_pipeline.py --test
```

### Production Run

Process all data from 2023 onwards:

```bash
python scripts/run_pipeline.py \
    --city augsburg \
    --start-date 2023-01-01T00:00:00Z \
    --batch-size 50
```

### Incremental Update

Process only new/modified papers (skip already processed):

```bash
python scripts/run_pipeline.py \
    --start-date 2024-11-01T00:00:00Z
```

### Reprocess Failed Papers

Clear failed papers and retry:

```bash
python scripts/run_pipeline.py \
    --reprocess-failed \
    --limit 50
```

### Memory-Constrained Environment

Use smaller batches:

```bash
python scripts/run_pipeline.py \
    --batch-size 10 \
    --limit 100
```

## Output Files

After running the pipeline, you'll find:

```
data/processed/
├── council_data.parquet/        # Partitioned paper data
│   ├── city=augsburg/
│   │   ├── year=2023/
│   │   ├── year=2024/
│   │   └── year=2025/
├── augsburg_locations.parquet   # Separate locations table
├── augsburg_map.geojson         # GeoJSON for web maps
├── metadata.nt                  # RDF N-Triples
├── metadata.ttl                 # RDF Turtle (final)
└── pipeline_state.db            # SQLite state tracking

logs/
└── pipeline_augsburg_20241203_143022.log  # Detailed logs
```

## Crash Recovery

The pipeline uses SQLite-based state tracking for crash recovery:

- **Automatic Resume**: If the pipeline crashes, it will skip already processed papers on the next run
- **Checkpoints**: State is saved after each batch
- **Failed Paper Tracking**: Failed papers are marked and can be retried

```bash
# Resume after crash (automatically skips processed papers)
python scripts/run_pipeline.py

# Check statistics
python -c "
from src.state import StateManager
state = StateManager('data/processed/pipeline_state.db')
print(state.get_statistics())
"
```

## Monitoring Progress

The pipeline provides detailed logging:

```bash
# Watch log in real-time
tail -f logs/pipeline_augsburg_*.log

# Check current progress
grep "Progress:" logs/pipeline_augsburg_*.log | tail -1
```

## Performance Tuning

### Memory Usage

Controlled by `--batch-size`:
- **Large batches (50-100)**: Faster, uses more memory
- **Small batches (10-25)**: Slower, uses less memory

### Download Speed

Configure in `config.yaml`:
```yaml
oparl:
  http_timeout_sec: 40
  retry_attempts: 5
```

Or adjust in code (`run_pipeline.py`, `_process_batch()`):
```python
self.extractor.extract_batch(
    papers,
    max_workers=3,  # Parallel downloads (increase for faster)
    delay_between_downloads=1.0  # Delay in seconds (decrease for faster)
)
```

### Geocoding Rate Limits

Nominatim has rate limits (1 req/sec). Configure in `spatial.py`:
```python
self.spatial = SpatialProcessor(
    city=self.city,
    rate_limit_sec=1.0  # Increase to be more conservative
)
```

## Troubleshooting

### Import Errors

```bash
# Ensure you're in the project root
cd /path/to/Geomodelierung

# Check Python path
python -c "import sys; print(sys.path)"

# Run with explicit path
PYTHONPATH=. python scripts/run_pipeline.py
```

### PDF Extraction Failures

Some PDFs may be scanned or corrupted:
- The pipeline automatically falls back to OCR (if Tesseract is installed)
- Failed extractions are logged and marked in state DB
- Use `--reprocess-failed` to retry after installing OCR

### Geocoding Timeouts

If geocoding is slow or timing out:
```bash
# Process fewer papers at once
python scripts/run_pipeline.py --batch-size 10

# Or skip geocoding temporarily (edit spatial.py)
```

### Out of Memory

```bash
# Use smaller batches
python scripts/run_pipeline.py --batch-size 10

# Process fewer papers
python scripts/run_pipeline.py --limit 50
```

## Development

### Adding New Stages

Edit `_process_batch()` in `run_pipeline.py`:

```python
def _process_batch(self, papers: List[Dict[str, Any]]) -> int:
    # ... existing stages ...

    # Add new stage
    self.logger.info("  → Running custom analysis...")
    analyzed_papers = self.custom_analyzer.analyze(enriched_papers)

    # ... continue ...
```

### Custom Post-Processing

Create a new script in `scripts/`:

```python
# scripts/analyze_results.py
import pandas as pd

df = pd.read_parquet("data/processed/augsburg_locations.parquet")
print(df.describe())
```

## Integration

### Jupyter Notebooks

```python
# In notebooks/analysis.ipynb
import sys
sys.path.insert(0, '../src')

from storage import ParquetWriter

writer = ParquetWriter()
df = writer.read_partition(city="augsburg", year=2024)
```

### Scheduled Runs

```bash
# crontab entry: daily at 2 AM
0 2 * * * cd /path/to/Geomodelierung && python scripts/run_pipeline.py --start-date $(date -d '7 days ago' +\%Y-\%m-\%d)T00:00:00Z
```

### CI/CD

```yaml
# .github/workflows/pipeline.yml
jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run pipeline test
        run: python scripts/run_pipeline.py --test
```

## Next Steps

After running the pipeline:

1. **Analyze data**: See `notebooks/` for analysis examples
2. **Visualize locations**: Use the GeoJSON in web maps
3. **Query RDF**: Load Turtle file into GraphDB/Oxigraph
4. **Export to CSV**: Use Pandas to convert Parquet → CSV

```python
import pandas as pd

# Export locations to CSV
df = pd.read_parquet("data/processed/augsburg_locations.parquet")
df.to_csv("augsburg_locations.csv", index=False)
```
