"""
Data Storage
============

Handles writing processed data to Parquet and RDF formats with partitioning,
compression, and incremental updates.

Usage:
    from src.storage import ParquetWriter, RDFWriter

    # Write to Parquet
    writer = ParquetWriter(base_dir="data/processed")
    writer.write_batch(papers_data, city="augsburg")

    # Write to RDF
    rdf_writer = RDFWriter(output_file="data/processed/metadata.nt")
    rdf_writer.add_papers(papers_data)
    rdf_writer.serialize(format="turtle")
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS, GEO
import yaml

logger = logging.getLogger(__name__)


class ParquetWriter:
    """
    Write data to partitioned Parquet format with compression.

    Attributes:
        base_dir: Base directory for Parquet files
        partition_cols: Columns to partition by (e.g., ['city', 'year'])
        compression: Compression algorithm (snappy, gzip, brotli)
    """

    def __init__(
        self,
        base_dir: str = "data/processed/council_data.parquet",
        partition_cols: List[str] = None,
        compression: str = "snappy",
        config_path: Optional[str] = None
    ):
        """
        Initialize Parquet writer.

        Args:
            base_dir: Base directory for output
            partition_cols: Columns for partitioning
            compression: Compression algorithm
            config_path: Path to config.yaml (optional)
        """
        self.base_dir = Path(base_dir)

        # Load config if provided
        if config_path:
            config = self._load_config(config_path)
            proc = config.get('processing', {}).get('parquet', {})
            self.partition_cols = partition_cols or proc.get('partition_cols', ['city', 'year'])
            self.compression = compression or proc.get('compression', 'snappy')
        else:
            self.partition_cols = partition_cols or ['city', 'year']
            self.compression = compression

        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ParquetWriter initialized: {self.base_dir}")
        logger.info(f"Partitioning: {self.partition_cols}, Compression: {self.compression}")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from config.yaml."""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _prepare_dataframe(self, data: List[Dict[str, Any]], city: str) -> pd.DataFrame:
        """
        Prepare DataFrame with partitioning columns.

        Args:
            data: List of paper/meeting dictionaries
            city: City name

        Returns:
            Prepared DataFrame
        """
        df = pd.DataFrame(data)

        # Add city column
        df['city'] = city

        # Extract year from date field
        if 'date' in df.columns:
            df['year'] = pd.to_datetime(df['date'], errors='coerce').dt.year
        else:
            df['year'] = datetime.now().year

        # Convert text columns to string type
        text_cols = ['full_text', 'id', 'name', 'reference', 'type']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype('string')

        return df

    def write_batch(
        self,
        data: List[Dict[str, Any]],
        city: str,
        append: bool = True
    ) -> int:
        """
        Write batch of data to Parquet.

        Args:
            data: List of dictionaries (papers/meetings)
            city: City name
            append: If True, append to existing data; if False, overwrite

        Returns:
            Number of rows written

        Example:
            writer.write_batch(papers, city="augsburg")
        """
        if not data:
            logger.warning("No data to write")
            return 0

        df = self._prepare_dataframe(data, city)

        logger.info(f"Writing {len(df)} rows to {self.base_dir}")

        # Convert to PyArrow Table
        table = pa.Table.from_pandas(df)

        # Write with partitioning
        pq.write_to_dataset(
            table,
            root_path=str(self.base_dir),
            partition_cols=self.partition_cols,
            compression=self.compression,
            existing_data_behavior='overwrite_or_ignore' if append else 'delete_matching'
        )

        logger.info(f"Successfully wrote {len(df)} rows")
        return len(df)

    def read_all(self) -> pd.DataFrame:
        """
        Read all data from Parquet dataset.

        Returns:
            Complete DataFrame
        """
        if not self.base_dir.exists():
            logger.warning(f"No data found at {self.base_dir}")
            return pd.DataFrame()

        dataset = pq.ParquetDataset(
            str(self.base_dir),
            use_legacy_dataset=False
        )

        table = dataset.read()
        df = table.to_pandas()

        logger.info(f"Read {len(df)} rows from {self.base_dir}")
        return df

    def read_partition(self, city: str, year: Optional[int] = None) -> pd.DataFrame:
        """
        Read specific partition.

        Args:
            city: City name
            year: Year (optional)

        Returns:
            Filtered DataFrame
        """
        df = self.read_all()

        df = df[df['city'] == city]
        if year:
            df = df[df['year'] == year]

        logger.info(f"Read {len(df)} rows for {city}/{year or 'all years'}")
        return df

    def write_locations_table(
        self,
        papers_with_locations: List[Dict[str, Any]],
        city: str,
        output_file: Optional[str] = None
    ) -> int:
        """
        Create a separate locations table with direct PDF links.

        Each row represents one location extracted from one paper,
        with links back to the paper and PDF.

        Args:
            papers_with_locations: Papers with 'locations' field
            city: City name
            output_file: Custom output path (optional)

        Returns:
            Number of location rows written

        Example output structure:
            | location_id | paper_id | pdf_url | location_type | location_value |
            | latitude | longitude | display_name | extracted_method |
        """
        if output_file is None:
            output_file = self.base_dir.parent / f"{city}_locations.parquet"
        else:
            output_file = Path(output_file)

        location_rows = []

        for paper in papers_with_locations:
            paper_id = paper.get('id', '')
            paper_name = paper.get('name', '')
            paper_date = paper.get('date', '')
            pdf_url = paper.get('pdf_url', '')

            locations = paper.get('locations', [])

            for loc in locations:
                row = {
                    'location_id': f"{paper_id}_{loc.get('type')}_{loc.get('value', '').replace(' ', '_')}",
                    'paper_id': paper_id,
                    'paper_name': paper_name,
                    'paper_date': paper_date,
                    'pdf_url': pdf_url,
                    'location_type': loc.get('type'),
                    'location_value': loc.get('value'),
                    'latitude': loc.get('latitude'),
                    'longitude': loc.get('longitude'),
                    'display_name': loc.get('display_name'),
                    'query': loc.get('query'),
                    'method': loc.get('method'),
                    'context': loc.get('context'),  # Original text context
                    'city': city
                }
                location_rows.append(row)

        if not location_rows:
            logger.warning("No locations to write")
            return 0

        df = pd.DataFrame(location_rows)

        # Ensure string types
        string_cols = ['location_id', 'paper_id', 'paper_name', 'pdf_url',
                       'location_type', 'location_value', 'display_name',
                       'query', 'method', 'context', 'city']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype('string')

        logger.info(f"Writing {len(df)} locations to {output_file}")
        df.to_parquet(output_file, compression=self.compression)

        logger.info(f"Locations table created: {len(df)} rows")
        return len(df)


class RDFWriter:
    """
    Write data to RDF format (N-Triples for incremental, Turtle for final).

    Attributes:
        graph: RDFLib graph
        base_uri: Base URI for resources
        namespaces: RDF namespace configuration
    """

    def __init__(
        self,
        output_file: str = "data/processed/metadata.nt",
        base_uri: str = "http://augsburg.oparl-analytics.org/",
        config_path: Optional[str] = None
    ):
        """
        Initialize RDF writer.

        Args:
            output_file: Output file path (.nt or .ttl)
            base_uri: Base URI for resources
            config_path: Path to config.yaml (optional)
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        self.base_uri = base_uri
        self.graph = Graph()

        # Load config
        if config_path:
            config = self._load_config(config_path)
            ns_config = config.get('processing', {}).get('rdf', {}).get('namespaces', {})
            self.oparl_uri = ns_config.get('oparl', 'http://oparl.org/schema/1.1/')
            self.geo_uri = ns_config.get('geo', 'http://www.opengis.net/ont/geosparql#')
        else:
            self.oparl_uri = 'http://oparl.org/schema/1.1/'
            self.geo_uri = 'http://www.opengis.net/ont/geosparql#'

        # Define namespaces
        self.OPARL = Namespace(self.oparl_uri)
        self.GEO_NS = Namespace(self.geo_uri)
        self.EX = Namespace(self.base_uri)

        # Bind namespaces
        self.graph.bind("oparl", self.OPARL)
        self.graph.bind("geo", self.GEO_NS)
        self.graph.bind("ex", self.EX)
        self.graph.bind("dcterms", DCTERMS)
        self.graph.bind("rdfs", RDFS)

        logger.info(f"RDFWriter initialized: {self.output_file}")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from config.yaml."""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _extract_id(self, url: str) -> str:
        """Extract ID from OParl URL."""
        if not url:
            return "unknown"
        return url.split('/')[-1] if '/' in url else url

    def add_paper(self, paper: Dict[str, Any]):
        """
        Add a paper to the RDF graph.

        Args:
            paper: Paper dictionary with OParl fields
        """
        if not paper.get('id'):
            return

        # Create URI
        paper_id = self._extract_id(paper['id'])
        paper_uri = URIRef(f"{self.base_uri}paper/{paper_id}")

        # Type
        self.graph.add((paper_uri, RDF.type, self.OPARL.Paper))

        # Properties
        if paper.get('name'):
            self.graph.add((paper_uri, RDFS.label, Literal(paper['name'], lang='de')))
            self.graph.add((paper_uri, self.OPARL.name, Literal(paper['name'])))

        if paper.get('reference'):
            self.graph.add((paper_uri, self.OPARL.reference, Literal(paper['reference'])))

        if paper.get('date'):
            try:
                date_obj = pd.to_datetime(paper['date'])
                self.graph.add((
                    paper_uri,
                    DCTERMS.date,
                    Literal(date_obj.date(), datatype=XSD.date)
                ))
            except:
                pass

        if paper.get('type'):
            self.graph.add((paper_uri, self.OPARL.paperType, Literal(paper['type'])))

        if paper.get('full_text'):
            self.graph.add((
                paper_uri,
                self.OPARL.text,
                Literal(paper['full_text'][:1000])  # Truncate for RDF
            ))

        # PDF URL
        if paper.get('pdf_url'):
            file_uri = URIRef(paper['pdf_url'])
            self.graph.add((paper_uri, self.OPARL.mainFile, file_uri))

        # Timestamps
        if paper.get('created'):
            try:
                created = pd.to_datetime(paper['created'])
                self.graph.add((
                    paper_uri,
                    DCTERMS.created,
                    Literal(created, datatype=XSD.dateTime)
                ))
            except:
                pass

        if paper.get('modified'):
            try:
                modified = pd.to_datetime(paper['modified'])
                self.graph.add((
                    paper_uri,
                    DCTERMS.modified,
                    Literal(modified, datatype=XSD.dateTime)
                ))
            except:
                pass

        # Add locations if present
        if paper.get('locations'):
            for loc in paper['locations']:
                self._add_location_to_paper(paper_uri, paper['id'], loc)

    def add_papers(self, papers: List[Dict[str, Any]]):
        """
        Add multiple papers to the graph.

        Args:
            papers: List of paper dictionaries
        """
        logger.info(f"Adding {len(papers)} papers to RDF graph")

        for paper in papers:
            try:
                self.add_paper(paper)
            except Exception as e:
                logger.warning(f"Error adding paper {paper.get('id')}: {e}")

        logger.info(f"Graph now contains {len(self.graph)} triples")

    def _add_location_to_paper(
        self,
        paper_uri: URIRef,
        paper_id: str,
        location: Dict[str, Any]
    ):
        """
        Add a location and its relation to a paper in the RDF graph.

        Args:
            paper_uri: Paper URI reference
            paper_id: Paper ID
            location: Location dictionary with coordinates and metadata
        """
        # Create location node
        loc_value = location.get('value', 'unknown')
        loc_type = location.get('type', 'location')
        loc_id = f"{paper_id}_{loc_type}_{loc_value}".replace(' ', '_').replace('/', '-')
        loc_uri = URIRef(f"{self.base_uri}location/{loc_id}")

        # Link paper to location
        self.graph.add((paper_uri, self.OPARL.relatesToLocation, loc_uri))

        # Location type
        self.graph.add((loc_uri, RDF.type, self.GEO_NS.Feature))

        # Location properties
        if loc_value:
            self.graph.add((loc_uri, RDFS.label, Literal(loc_value, lang='de')))

        if loc_type:
            self.graph.add((loc_uri, self.OPARL.locationType, Literal(loc_type)))

        # Coordinates and WKT
        lat = location.get('latitude')
        lon = location.get('longitude')

        if lat and lon:
            # WKT representation
            wkt = f"<http://www.opengis.net/def/crs/EPSG/0/4326> POINT({lon} {lat})"
            self.graph.add((
                loc_uri,
                self.GEO_NS.hasGeometry,
                Literal(wkt, datatype=self.GEO_NS.wktLiteral)
            ))

            # Separate lat/lon for easier querying
            self.graph.add((loc_uri, self.GEO_NS.lat, Literal(lat, datatype=XSD.double)))
            self.graph.add((loc_uri, self.GEO_NS.long, Literal(lon, datatype=XSD.double)))

        # Display name (geocoded address)
        if location.get('display_name'):
            self.graph.add((
                loc_uri,
                self.OPARL.displayName,
                Literal(location['display_name'])
            ))

        # Extraction method
        if location.get('method'):
            self.graph.add((
                loc_uri,
                self.OPARL.extractionMethod,
                Literal(location['method'])
            ))

        # Link back to PDF if available
        if location.get('pdf_url'):
            pdf_uri = URIRef(location['pdf_url'])
            self.graph.add((loc_uri, self.OPARL.sourceDocument, pdf_uri))

    def add_spatial_relation(
        self,
        paper_id: str,
        location: str,
        wkt: Optional[str] = None,
        geo_uri: Optional[str] = None
    ):
        """
        Add spatial relationship to a paper.

        Args:
            paper_id: Paper ID
            location: Location name
            wkt: WKT geometry (optional)
            geo_uri: GeoNames/external URI (optional)
        """
        paper_uri = URIRef(f"{self.base_uri}paper/{paper_id}")

        # Create location node
        loc_id = location.replace(' ', '_').replace(',', '')
        loc_uri = URIRef(f"{self.base_uri}location/{loc_id}")

        self.graph.add((paper_uri, self.OPARL.relatesToLocation, loc_uri))
        self.graph.add((loc_uri, RDF.type, self.GEO_NS.Feature))
        self.graph.add((loc_uri, RDFS.label, Literal(location, lang='de')))

        # Add WKT geometry
        if wkt:
            self.graph.add((
                loc_uri,
                self.GEO_NS.hasGeometry,
                Literal(wkt, datatype=self.GEO_NS.wktLiteral)
            ))

        # Link to external URI
        if geo_uri:
            self.graph.add((loc_uri, RDFS.seeAlso, URIRef(geo_uri)))

    def serialize(self, format: str = "nt") -> str:
        """
        Serialize graph to file.

        Args:
            format: Output format ('nt', 'turtle', 'xml')

        Returns:
            Path to output file
        """
        # Update file extension if needed
        ext_map = {'nt': '.nt', 'turtle': '.ttl', 'xml': '.rdf'}
        if format in ext_map:
            output_path = self.output_file.with_suffix(ext_map[format])
        else:
            output_path = self.output_file

        logger.info(f"Serializing {len(self.graph)} triples to {output_path} ({format})")

        self.graph.serialize(
            destination=str(output_path),
            format=format,
            encoding='utf-8'
        )

        logger.info(f"RDF serialization complete")
        return str(output_path)

    def append_to_ntriples(self, papers: List[Dict[str, Any]]):
        """
        Append papers to N-Triples file incrementally.

        Args:
            papers: List of paper dictionaries
        """
        # Create temporary graph for new triples
        temp_graph = Graph()
        temp_graph.bind("oparl", self.OPARL)
        temp_graph.bind("geo", self.GEO_NS)

        # Add papers to temp graph
        for paper in papers:
            try:
                self.add_paper(paper)
            except Exception as e:
                logger.warning(f"Error adding paper: {e}")

        # Append to file
        mode = 'a' if self.output_file.exists() else 'w'
        with open(self.output_file, mode, encoding='utf-8') as f:
            f.write(temp_graph.serialize(format='nt'))


        logger.info(f"Appended {len(papers)} papers to {self.output_file}")


def export_locations_for_map(
    locations_parquet: str,
    output_geojson: str,
    filter_city: Optional[str] = None
) -> Dict[str, Any]:
    """
    Export locations to GeoJSON format for web mapping.

    Each feature contains:
    - Geometry (Point with coordinates)
    - Properties: location info, paper name/date, PDF link

    Args:
        locations_parquet: Path to locations parquet file
        output_geojson: Output GeoJSON file path
        filter_city: Filter by city (optional)

    Returns:
        GeoJSON FeatureCollection dictionary

    Example usage:
        geojson = export_locations_for_map(
            "data/processed/augsburg_locations.parquet",
            "data/output/locations.geojson",
            filter_city="augsburg"
        )
    """
    import json

    # Read locations
    df = pd.read_parquet(locations_parquet)

    if filter_city:
        df = df[df['city'] == filter_city]

    # Filter rows with coordinates
    df = df[df['latitude'].notna() & df['longitude'].notna()]

    logger.info(f"Exporting {len(df)} locations to GeoJSON")

    features = []

    for _, row in df.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row['longitude']), float(row['latitude'])]
            },
            "properties": {
                "location_id": str(row.get('location_id', '')),
                "location_type": str(row.get('location_type', '')),
                "location_value": str(row.get('location_value', '')),
                "paper_id": str(row.get('paper_id', '')),
                "paper_name": str(row.get('paper_name', '')),
                "paper_date": str(row.get('paper_date', '')),
                "pdf_url": str(row.get('pdf_url', '')),
                "display_name": str(row.get('display_name', '')),
                "method": str(row.get('method', ''))
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "city": filter_city,
            "generated_at": datetime.now().isoformat()
        }
    }

    # Write to file
    output_path = Path(output_geojson)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    logger.info(f"GeoJSON exported to {output_path}")
    return geojson