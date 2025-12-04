#!/usr/bin/env python3
"""
OParl Data Pipeline - Main Orchestration Script
================================================

Coordinates the complete data pipeline from OParl API to Parquet/RDF.

Pipeline stages:
1. Fetch papers from OParl API (streaming)
2. Extract text from PDFs (in-memory)
3. Extract spatial entities (locations, B-Pläne, Flurnummern)
4. Geocode locations
5. Write to Parquet (partitioned)
6. Write to RDF (incremental N-Triples)
7. Generate GeoJSON for mapping

Usage:
    # Run with default config
    python scripts/run_pipeline.py

    # Custom parameters
    python scripts/run_pipeline.py --city augsburg --start-date 2024-01-01 --limit 100

    # Test run (small sample)
    python scripts/run_pipeline.py --test --limit 10
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from client import OParlClient
from extraction import PDFExtractor
from spatial import SpatialProcessor
from storage import ParquetWriter, RDFWriter, export_locations_for_map
from state import StateManager


class PipelineOrchestrator:
    """
    Main pipeline orchestrator that coordinates all processing stages.

    Attributes:
        config: Configuration dictionary from config.yaml
        city: City being processed
        batch_size: Papers to process per batch
        state: State manager for crash recovery
    """

    def __init__(
        self,
        config_path: str = "config.yaml",
        city: str = None,
        batch_size: int = 50
    ):
        """
        Initialize pipeline orchestrator.

        Args:
            config_path: Path to config.yaml
            city: City name (overrides config default)
            batch_size: Papers per batch for checkpoint system
        """
        # Load configuration
        self.config = self._load_config(config_path)
        self.city = city or self.config['project']['city']
        self.batch_size = batch_size

        # Setup logging
        self._setup_logging()

        # Initialize components
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 70)
        self.logger.info(f"OParl Pipeline Orchestrator - {self.city.upper()}")
        self.logger.info("=" * 70)

        # Initialize state manager
        state_db_path = self._resolve_path(
            self.config['paths']['output']['state_db']
        )
        self.state = StateManager(db_path=state_db_path)

        # Initialize clients
        self.client = OParlClient(city=self.city, config_path=config_path)
        self.extractor = PDFExtractor(
            timeout=self.config['oparl']['http_timeout_sec']
        )
        self.spatial = SpatialProcessor(city=self.city, config=self.config)

        # Initialize writers
        parquet_dir = self._resolve_path(
            self.config['paths']['output']['parquet_dir']
        )
        rdf_file = self._resolve_path(
            self.config['paths']['output']['rdf_nt_file']
        )

        self.parquet_writer = ParquetWriter(
            base_dir=parquet_dir,
            config_path=config_path
        )
        self.rdf_writer = RDFWriter(
            output_file=rdf_file,
            config_path=config_path
        )

        # Statistics
        self.stats = {
            'papers_fetched': 0,
            'papers_processed': 0,
            'papers_failed': 0,
            'locations_extracted': 0,
            'locations_geocoded': 0,
            'start_time': None,  # Will be converted to string when serializing
            'end_time': None
        }

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _resolve_path(self, path_template: str) -> str:
        """Resolve path with ${variable} substitution."""
        # Simple variable substitution
        path = path_template
        path = path.replace('${processed}', self.config['paths']['processed'])
        return path

    def _setup_logging(self):
        """Configure logging to file and console."""
        log_dir = Path(self.config['paths']['logs'])
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f"pipeline_{self.city}_{timestamp}.log"

        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

        print(f"Logging to: {log_file}")

    def run(
        self,
        start_date: str = None,
        end_date: str = None,
        limit_papers: int = None,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Run the complete pipeline.

        Args:
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            limit_papers: Maximum papers to process (None = unlimited)
            skip_existing: Skip already processed papers

        Returns:
            Statistics dictionary
        """
        self.stats['start_time'] = datetime.now()

        # Start pipeline run in state DB
        run_id = self.state.start_pipeline_run(
            city=self.city,
            config={
                'start_date': start_date,
                'end_date': end_date,
                'limit_papers': limit_papers,
                'batch_size': self.batch_size
            }
        )

        self.logger.info(f"Pipeline run ID: {run_id}")
        self.logger.info(f"Batch size: {self.batch_size}")
        self.logger.info(f"Skip existing: {skip_existing}")

        try:
            # Stage 1: Fetch and process papers in batches
            self._process_papers(
                start_date=start_date,
                end_date=end_date,
                limit_papers=limit_papers,
                skip_existing=skip_existing
            )

            # Stage 2: Export GeoJSON for mapping
            self._export_geojson()

            # Stage 4: Finalize RDF (convert to Turtle)
            self._finalize_rdf()

            # Mark run as completed
            self.stats['end_time'] = datetime.now()
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            self.stats['duration_seconds'] = duration

            # Convert datetime to ISO strings for JSON serialization
            stats_serializable = self.stats.copy()
            stats_serializable['start_time'] = self.stats['start_time'].isoformat()
            stats_serializable['end_time'] = self.stats['end_time'].isoformat()

            self.state.end_pipeline_run(run_id, status='completed', stats=stats_serializable)

            # Print summary
            self._print_summary()

            return self.stats

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)

            # Convert datetime to ISO strings for JSON serialization
            stats_serializable = self.stats.copy()
            if self.stats.get('start_time'):
                stats_serializable['start_time'] = self.stats['start_time'].isoformat()
            if self.stats.get('end_time'):
                stats_serializable['end_time'] = self.stats['end_time'].isoformat()

            self.state.end_pipeline_run(run_id, status='failed', stats=stats_serializable)
            raise

        finally:
            # Cleanup
            self._cleanup()

    def _process_papers(
        self,
        start_date: str = None,
        end_date: str = None,
        limit_papers: int = None,
        skip_existing: bool = True
    ):
        """
        Main processing loop: fetch, extract, geocode, save.

        Processes papers in batches with checkpointing for crash recovery.
        """
        self.logger.info("\n" + "=" * 70)
        self.logger.info("STAGE 1: FETCHING AND PROCESSING PAPERS")
        self.logger.info("=" * 70)

        # Use config dates if not specified
        if start_date is None:
            start_date = self.config['oparl']['start_date']
        if end_date is None:
            end_date = self.config['oparl']['end_date']

        self.logger.info(f"Date range: {start_date} to {end_date}")

        # Get already processed IDs
        processed_ids = set()
        if skip_existing:
            processed_ids = self.state.get_processed_ids(resource_type='paper')
            self.logger.info(f"Skipping {len(processed_ids)} already processed papers")

        # Fetch papers from API (generator = memory efficient)
        paper_generator = self.client.fetch_papers(
            start_date=start_date,
            end_date=end_date
        )

        batch = []
        total_fetched = 0
        total_processed = 0

        for paper in paper_generator:
            # Check limit
            if limit_papers and total_fetched >= limit_papers:
                self.logger.info(f"Reached limit: {limit_papers} papers")
                break

            total_fetched += 1
            self.stats['papers_fetched'] = total_fetched

            # Skip if already processed
            if skip_existing and paper['id'] in processed_ids:
                continue

            batch.append(paper)

            # Process batch when full
            if len(batch) >= self.batch_size:
                processed = self._process_batch(batch)
                total_processed += processed
                self.stats['papers_processed'] = total_processed

                # Checkpoint
                self.state.checkpoint(
                    resource_type='paper',
                    batch_size=len(batch),
                    metadata={'total_fetched': total_fetched}
                )

                batch = []

                self.logger.info(
                    f"Progress: Fetched {total_fetched}, Processed {total_processed}"
                )

        # Process remaining papers
        if batch:
            processed = self._process_batch(batch)
            total_processed += processed
            self.stats['papers_processed'] = total_processed

            self.state.checkpoint(
                resource_type='paper',
                batch_size=len(batch),
                metadata={'total_fetched': total_fetched}
            )

        self.logger.info(f"\nCompleted: {total_processed} papers processed")

    def _process_batch(self, papers: List[Dict[str, Any]]) -> int:
        """
        Process a batch of papers through all stages.

        Args:
            papers: List of paper objects from OParl API

        Returns:
            Number of successfully processed papers
        """
        self.logger.info(f"\nProcessing batch of {len(papers)} papers...")

        # Stage 1: Extract text from PDFs
        self.logger.info("  → Extracting PDF text...")
        extraction_results = self.extractor.extract_batch(
            papers,
            max_workers=3,  # Conservative to avoid overwhelming servers
            delay_between_downloads=1.0
        )

        # Merge extraction results back into papers
        valid_papers = []
        for paper, result in zip(papers, extraction_results):
            if result.success and result.text:
                # Add extracted text to paper
                paper['full_text'] = result.text
                paper['extraction_method'] = result.method
                paper['page_count'] = result.page_count
                valid_papers.append(paper)
            else:
                # Mark failed papers in state
                self.state.mark_processed(
                    paper['id'],
                    'paper',
                    status='failed',
                    error_message=result.error or 'PDF extraction failed'
                )
                self.stats['papers_failed'] += 1

        failed_count = len(papers) - len(valid_papers)
        if failed_count > 0:
            self.logger.warning(f"  → {failed_count} papers failed text extraction")

        if not valid_papers:
            self.logger.warning("  → No valid papers in batch, skipping")
            return 0

        # Stage 2: Extract and geocode locations
        self.logger.info(f"  → Extracting locations from {len(valid_papers)} papers...")
        enriched_papers = self.spatial.enrich_papers_with_locations(valid_papers)

        # Count locations
        total_locations = sum(
            len(p.get('locations', [])) for p in enriched_papers
        )
        geocoded_locations = sum(
            sum(1 for loc in p.get('locations', []) if loc.get('latitude'))
            for p in enriched_papers
        )

        self.logger.info(f"  → Extracted {total_locations} locations")
        self.logger.info(f"  → Geocoded {geocoded_locations} locations")

        self.stats['locations_extracted'] += total_locations
        self.stats['locations_geocoded'] += geocoded_locations

        # Stage 3: Write to Parquet
        self.logger.info("  → Writing to Parquet...")
        self.parquet_writer.write_batch(
            enriched_papers,
            city=self.city,
            append=True
        )

        # Stage 4: Write to RDF (incremental N-Triples)
        self.logger.info("  → Writing to RDF...")
        self.rdf_writer.add_papers(enriched_papers)

        # Stage 5: Mark as processed in state DB
        paper_ids = [p['id'] for p in enriched_papers]
        self.state.mark_batch_processed(paper_ids, 'paper', status='completed')

        self.logger.info(f"  ✓ Batch complete: {len(enriched_papers)} papers")

        return len(enriched_papers)

    def _export_geojson(self):
        """Export GeoJSON for web mapping."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("STAGE 2: EXPORTING GEOJSON FOR MAPPING")
        self.logger.info("=" * 70)

        # Read papers directly from parquet
        df_papers = self.parquet_writer.read_partition(city=self.city)

        if df_papers.empty:
            self.logger.warning("No papers found, skipping GeoJSON export")
            return

        # Convert to list of dicts
        papers_list = df_papers.to_dict('records')

        output_file = Path(self.config['paths']['processed']) / f"{self.city}_map.geojson"

        geojson = export_locations_for_map(
            papers_with_locations=papers_list,
            output_file=str(output_file),
            filter_city=self.city
        )

        feature_count = len(geojson['features'])
        self.logger.info(f"✓ GeoJSON created: {feature_count} features")
        self.logger.info(f"  File: {output_file}")

    def _finalize_rdf(self):
        """Finalize RDF output (convert N-Triples to Turtle)."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("STAGE 3: FINALIZING RDF OUTPUT")
        self.logger.info("=" * 70)

        # Serialize to final format
        final_format = self.config['processing']['rdf'].get('final_format', 'turtle')
        output_file = self.rdf_writer.serialize(format=final_format)

        self.logger.info(f"✓ RDF serialized: {len(self.rdf_writer.graph)} triples")
        self.logger.info(f"  Format: {final_format}")
        self.logger.info(f"  File: {output_file}")

    def _cleanup(self):
        """Clean up resources."""
        self.logger.info("\nCleaning up resources...")

        try:
            self.client.close()
            self.extractor.close()
            self.spatial.close()
            self.state.close()
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")

    def _print_summary(self):
        """Print pipeline execution summary."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("PIPELINE EXECUTION SUMMARY")
        self.logger.info("=" * 70)

        duration = self.stats.get('duration_seconds', 0)
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        self.logger.info(f"City: {self.city}")
        self.logger.info(f"Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
        self.logger.info(f"\nPapers:")
        self.logger.info(f"  - Fetched: {self.stats['papers_fetched']}")
        self.logger.info(f"  - Processed: {self.stats['papers_processed']}")
        self.logger.info(f"  - Failed: {self.stats['papers_failed']}")
        self.logger.info(f"\nLocations:")
        self.logger.info(f"  - Extracted: {self.stats['locations_extracted']}")
        self.logger.info(f"  - Geocoded: {self.stats['locations_geocoded']}")

        if self.stats['papers_processed'] > 0:
            avg_locations = self.stats['locations_extracted'] / self.stats['papers_processed']
            geocode_rate = (self.stats['locations_geocoded'] / self.stats['locations_extracted'] * 100) if self.stats['locations_extracted'] > 0 else 0
            self.logger.info(f"  - Avg per paper: {avg_locations:.1f}")
            self.logger.info(f"  - Geocoding success: {geocode_rate:.1f}%")

        self.logger.info("\n" + "=" * 70)
        self.logger.info("✓ PIPELINE COMPLETED SUCCESSFULLY")
        self.logger.info("=" * 70)


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="OParl Data Pipeline - Extract, enrich, and convert council data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults from config.yaml
  python scripts/run_pipeline.py

  # Process specific city
  python scripts/run_pipeline.py --city augsburg

  # Custom date range
  python scripts/run_pipeline.py --start-date 2024-01-01 --end-date 2024-12-31

  # Test run (10 papers)
  python scripts/run_pipeline.py --test

  # Process 100 papers with custom batch size
  python scripts/run_pipeline.py --limit 100 --batch-size 25

  # Reprocess failed papers
  python scripts/run_pipeline.py --reprocess-failed
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config.yaml (default: config.yaml)'
    )

    parser.add_argument(
        '--city',
        type=str,
        help='City to process (overrides config default)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (ISO format: 2024-01-01T00:00:00Z)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (ISO format: 2024-12-31T23:59:59Z)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of papers to process'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Papers per batch for checkpointing (default: 50)'
    )

    parser.add_argument(
        '--no-skip-existing',
        action='store_true',
        help='Reprocess already processed papers'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process only 10 papers'
    )

    parser.add_argument(
        '--reprocess-failed',
        action='store_true',
        help='Clear failed papers and reprocess them'
    )

    args = parser.parse_args()

    # Test mode overrides
    if args.test:
        args.limit = 10
        args.batch_size = 5
        print("=" * 70)
        print("TEST MODE: Processing 10 papers with batch size 5")
        print("=" * 70)

    try:
        # Initialize orchestrator
        orchestrator = PipelineOrchestrator(
            config_path=args.config,
            city=args.city,
            batch_size=args.batch_size
        )

        # Clear failed papers if requested
        if args.reprocess_failed:
            count = orchestrator.state.clear_failed()
            print(f"Cleared {count} failed papers for reprocessing")

        # Run pipeline
        stats = orchestrator.run(
            start_date=args.start_date,
            end_date=args.end_date,
            limit_papers=args.limit,
            skip_existing=not args.no_skip_existing
        )

        # Exit with success
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n\nPipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
