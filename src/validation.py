"""
validation.py - Data Validation and Quality Checks

This module provides:
1. SHACL shape validation for RDF output
2. Data quality checks for papers and locations
3. Report generation for validation results
"""

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json
import logging
from dataclasses import dataclass, field
from enum import Enum

# RDF validation
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, SH, XSD

# Data validation
import pandas as pd

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """Represents a single validation issue"""
    severity: ValidationSeverity
    category: str  # e.g., "missing_field", "invalid_date", "shacl_violation"
    message: str
    resource_id: Optional[str] = None
    field: Optional[str] = None
    value: Optional[Any] = None
    expected: Optional[Any] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    timestamp: datetime
    total_resources: int
    issues: List[ValidationIssue]
    summary: Dict[str, int]

    def __post_init__(self):
        """Calculate summary statistics"""
        self.summary = {
            'total_issues': len(self.issues),
            'errors': sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR),
            'warnings': sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING),
            'info': sum(1 for i in self.issues if i.severity == ValidationSeverity.INFO)
        }

    def is_valid(self) -> bool:
        """Returns True if no errors found"""
        return self.summary['errors'] == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_resources': self.total_resources,
            'summary': self.summary,
            'issues': [
                {
                    'severity': i.severity.value,
                    'category': i.category,
                    'message': i.message,
                    'resource_id': i.resource_id,
                    'field': i.field,
                    'value': str(i.value) if i.value is not None else None,
                    'expected': str(i.expected) if i.expected is not None else None,
                    'details': i.details
                }
                for i in self.issues
            ]
        }


class SHACLValidator:
    """
    SHACL Shape validator for RDF graphs

    Validates OParl RDF output against SHACL shapes
    """

    def __init__(self):
        self.oparl_ns = Namespace("https://schema.oparl.org/1.1/")
        self.geo_ns = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
        self.shapes_graph = self._create_shapes_graph()

    def _create_shapes_graph(self) -> Graph:
        """
        Create SHACL shapes graph for OParl validation

        Defines constraints for:
        - Paper must have type, name, date
        - Location must have coordinates
        - Files must have accessUrl
        """
        g = Graph()

        # Define namespaces
        g.bind('sh', SH)
        g.bind('oparl', self.oparl_ns)
        g.bind('geo', self.geo_ns)

        # Paper Shape
        paper_shape = URIRef("http://example.org/shapes/PaperShape")
        g.add((paper_shape, RDF.type, SH.NodeShape))
        g.add((paper_shape, SH.targetClass, self.oparl_ns.Paper))

        # Paper must have name
        name_prop = URIRef("http://example.org/shapes/PaperShape/name")
        g.add((paper_shape, SH.property, name_prop))
        g.add((name_prop, SH.path, self.oparl_ns.name))
        g.add((name_prop, SH.minCount, Literal(1)))
        g.add((name_prop, SH.datatype, XSD.string))

        # Paper must have date
        date_prop = URIRef("http://example.org/shapes/PaperShape/date")
        g.add((paper_shape, SH.property, date_prop))
        g.add((date_prop, SH.path, self.oparl_ns.date))
        g.add((date_prop, SH.minCount, Literal(1)))
        g.add((date_prop, SH.datatype, XSD.date))

        # Paper must have type
        type_prop = URIRef("http://example.org/shapes/PaperShape/type")
        g.add((paper_shape, SH.property, type_prop))
        g.add((type_prop, SH.path, RDF.type))
        g.add((type_prop, SH.minCount, Literal(1)))

        # Location Shape
        location_shape = URIRef("http://example.org/shapes/LocationShape")
        g.add((location_shape, RDF.type, SH.NodeShape))
        g.add((location_shape, SH.targetClass, self.geo_ns.Point))

        # Location must have lat/lon
        lat_prop = URIRef("http://example.org/shapes/LocationShape/lat")
        g.add((location_shape, SH.property, lat_prop))
        g.add((lat_prop, SH.path, self.geo_ns.lat))
        g.add((lat_prop, SH.minCount, Literal(1)))
        g.add((lat_prop, SH.datatype, XSD.decimal))

        lon_prop = URIRef("http://example.org/shapes/LocationShape/lon")
        g.add((location_shape, SH.property, lon_prop))
        g.add((lon_prop, SH.path, self.geo_ns.long))
        g.add((lon_prop, SH.minCount, Literal(1)))
        g.add((lon_prop, SH.datatype, XSD.decimal))

        return g

    def validate(self, data_graph: Graph) -> List[ValidationIssue]:
        """
        Validate RDF graph against SHACL shapes

        Args:
            data_graph: RDF graph to validate

        Returns:
            List of validation issues
        """
        issues = []

        try:
            # Use pyshacl for validation
            from pyshacl import validate

            conforms, results_graph, results_text = validate(
                data_graph,
                shacl_graph=self.shapes_graph,
                inference='rdfs',
                abort_on_first=False
            )

            if not conforms:
                # Parse validation results
                for violation in results_graph.subjects(RDF.type, SH.ValidationResult):
                    severity = results_graph.value(violation, SH.resultSeverity)
                    message = results_graph.value(violation, SH.resultMessage)
                    focus_node = results_graph.value(violation, SH.focusNode)
                    path = results_graph.value(violation, SH.resultPath)

                    # Map SHACL severity to our severity
                    if severity == SH.Violation:
                        sev = ValidationSeverity.ERROR
                    elif severity == SH.Warning:
                        sev = ValidationSeverity.WARNING
                    else:
                        sev = ValidationSeverity.INFO

                    issues.append(ValidationIssue(
                        severity=sev,
                        category='shacl_violation',
                        message=str(message) if message else 'SHACL validation failed',
                        resource_id=str(focus_node) if focus_node else None,
                        field=str(path) if path else None
                    ))

        except ImportError:
            logger.warning("pyshacl not installed - SHACL validation skipped")
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category='validation_skipped',
                message='pyshacl library not installed - SHACL validation not performed'
            ))

        except Exception as e:
            logger.error(f"SHACL validation error: {e}")
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category='validation_error',
                message=f'SHACL validation failed: {str(e)}'
            ))

        return issues


class DataQualityChecker:
    """
    Data quality checker for papers and locations

    Checks for:
    - Missing required fields
    - Invalid dates
    - Invalid coordinates
    - Duplicate entries
    - Data consistency
    """

    def __init__(self):
        self.required_paper_fields = ['id', 'name', 'date']
        self.required_location_fields = ['text', 'type', 'paper_id']

    def validate_papers(self, papers: List[Dict[str, Any]]) -> List[ValidationIssue]:
        """
        Validate paper records

        Args:
            papers: List of paper dictionaries

        Returns:
            List of validation issues
        """
        issues = []

        if not papers:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category='empty_data',
                message='No papers to validate'
            ))
            return issues

        seen_ids = set()

        for i, paper in enumerate(papers):
            paper_id = paper.get('id', f'paper_{i}')

            # Check required fields
            for field in self.required_paper_fields:
                if field not in paper or paper[field] is None:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category='missing_field',
                        message=f'Required field "{field}" is missing',
                        resource_id=paper_id,
                        field=field
                    ))

            # Check for duplicates
            if 'id' in paper:
                if paper['id'] in seen_ids:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category='duplicate',
                        message='Duplicate paper ID',
                        resource_id=paper_id,
                        field='id'
                    ))
                seen_ids.add(paper['id'])

            # Validate date format
            if 'date' in paper and paper['date']:
                try:
                    datetime.fromisoformat(paper['date'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category='invalid_date',
                        message='Invalid date format',
                        resource_id=paper_id,
                        field='date',
                        value=paper['date'],
                        expected='ISO 8601 format (YYYY-MM-DD)'
                    ))

            # Check PDF URL if mainFile exists
            if 'mainFile' in paper:
                if isinstance(paper['mainFile'], dict):
                    if 'accessUrl' not in paper['mainFile']:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            category='missing_field',
                            message='PDF accessUrl is missing',
                            resource_id=paper_id,
                            field='mainFile.accessUrl'
                        ))

            # Check for empty name
            if 'name' in paper and not str(paper['name']).strip():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category='empty_value',
                    message='Paper name is empty',
                    resource_id=paper_id,
                    field='name'
                ))

        return issues

    def validate_locations(self, locations: List[Dict[str, Any]]) -> List[ValidationIssue]:
        """
        Validate location records

        Args:
            locations: List of location dictionaries

        Returns:
            List of validation issues
        """
        issues = []

        if not locations:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                category='empty_data',
                message='No locations to validate'
            ))
            return issues

        for i, location in enumerate(locations):
            loc_id = location.get('paper_id', f'location_{i}')

            # Check required fields
            for field in self.required_location_fields:
                if field not in location or location[field] is None:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category='missing_field',
                        message=f'Field "{field}" is missing in location',
                        resource_id=loc_id,
                        field=field
                    ))

            # Validate coordinates if present
            if 'coordinates' in location and location['coordinates']:
                coords = location['coordinates']

                if 'lat' in coords and 'lon' in coords:
                    try:
                        lat = float(coords['lat'])
                        lon = float(coords['lon'])

                        # Check valid ranges
                        if not (-90 <= lat <= 90):
                            issues.append(ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                category='invalid_coordinates',
                                message='Latitude out of range',
                                resource_id=loc_id,
                                field='coordinates.lat',
                                value=lat,
                                expected='-90 to 90'
                            ))

                        if not (-180 <= lon <= 180):
                            issues.append(ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                category='invalid_coordinates',
                                message='Longitude out of range',
                                resource_id=loc_id,
                                field='coordinates.lon',
                                value=lon,
                                expected='-180 to 180'
                            ))

                    except (ValueError, TypeError):
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            category='invalid_coordinates',
                            message='Coordinates must be numeric',
                            resource_id=loc_id,
                            field='coordinates'
                        ))

            # Check location text is not empty
            if 'text' in location and not str(location['text']).strip():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category='empty_value',
                    message='Location text is empty',
                    resource_id=loc_id,
                    field='text'
                ))

        return issues

    def validate_parquet_dataset(self, dataset_path: Path) -> List[ValidationIssue]:
        """
        Validate Parquet dataset

        Args:
            dataset_path: Path to Parquet dataset

        Returns:
            List of validation issues
        """
        issues = []

        if not dataset_path.exists():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category='missing_data',
                message=f'Dataset not found: {dataset_path}'
            ))
            return issues

        try:
            df = pd.read_parquet(dataset_path)

            # Check for empty dataset
            if len(df) == 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category='empty_data',
                    message='Dataset is empty'
                ))
                return issues

            # Check for null values in critical columns
            critical_cols = ['id', 'name', 'city', 'year']
            for col in critical_cols:
                if col in df.columns:
                    null_count = df[col].isna().sum()
                    if null_count > 0:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            category='null_values',
                            message=f'Column "{col}" has {null_count} null values',
                            field=col,
                            details={'null_count': null_count, 'total_rows': len(df)}
                        ))

            # Check for duplicate IDs
            if 'id' in df.columns:
                duplicate_count = df['id'].duplicated().sum()
                if duplicate_count > 0:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category='duplicate',
                        message=f'Found {duplicate_count} duplicate IDs',
                        field='id',
                        details={'duplicate_count': duplicate_count}
                    ))

        except Exception as e:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category='validation_error',
                message=f'Error reading Parquet dataset: {str(e)}'
            ))

        return issues


class ValidationReportGenerator:
    """Generate comprehensive validation reports"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        papers: Optional[List[Dict[str, Any]]] = None,
        locations: Optional[List[Dict[str, Any]]] = None,
        rdf_graph: Optional[Graph] = None,
        parquet_path: Optional[Path] = None
    ) -> ValidationReport:
        """
        Generate comprehensive validation report

        Args:
            papers: List of paper dictionaries
            locations: List of location dictionaries
            rdf_graph: RDF graph to validate
            parquet_path: Path to Parquet dataset

        Returns:
            ValidationReport object
        """
        all_issues = []
        total_resources = 0

        # Validate papers
        if papers:
            logger.info(f"Validating {len(papers)} papers...")
            checker = DataQualityChecker()
            paper_issues = checker.validate_papers(papers)
            all_issues.extend(paper_issues)
            total_resources += len(papers)

        # Validate locations
        if locations:
            logger.info(f"Validating {len(locations)} locations...")
            checker = DataQualityChecker()
            location_issues = checker.validate_locations(locations)
            all_issues.extend(location_issues)
            total_resources += len(locations)

        # Validate RDF graph
        if rdf_graph:
            logger.info(f"Validating RDF graph with {len(rdf_graph)} triples...")
            validator = SHACLValidator()
            rdf_issues = validator.validate(rdf_graph)
            all_issues.extend(rdf_issues)

        # Validate Parquet dataset
        if parquet_path:
            logger.info(f"Validating Parquet dataset at {parquet_path}...")
            checker = DataQualityChecker()
            parquet_issues = checker.validate_parquet_dataset(parquet_path)
            all_issues.extend(parquet_issues)

        # Create report
        report = ValidationReport(
            timestamp=datetime.now(),
            total_resources=total_resources,
            issues=all_issues
        )

        return report

    def save_report(self, report: ValidationReport, format: str = 'json') -> Path:
        """
        Save validation report to file

        Args:
            report: ValidationReport object
            format: 'json', 'txt', or 'html'

        Returns:
            Path to saved report
        """
        timestamp_str = report.timestamp.strftime('%Y%m%d_%H%M%S')

        if format == 'json':
            output_file = self.output_dir / f'validation_report_{timestamp_str}.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        elif format == 'txt':
            output_file = self.output_dir / f'validation_report_{timestamp_str}.txt'
            with open(output_file, 'w', encoding='utf-8') as f:
                self._write_text_report(f, report)

        elif format == 'html':
            output_file = self.output_dir / f'validation_report_{timestamp_str}.html'
            with open(output_file, 'w', encoding='utf-8') as f:
                self._write_html_report(f, report)

        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Validation report saved to {output_file}")
        return output_file

    def _write_text_report(self, f, report: ValidationReport):
        """Write text format report"""
        f.write("=" * 80 + "\n")
        f.write("VALIDATION REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Timestamp: {report.timestamp.isoformat()}\n")
        f.write(f"Total Resources: {report.total_resources}\n")
        f.write(f"Total Issues: {report.summary['total_issues']}\n")
        f.write(f"  - Errors: {report.summary['errors']}\n")
        f.write(f"  - Warnings: {report.summary['warnings']}\n")
        f.write(f"  - Info: {report.summary['info']}\n")
        f.write(f"\nValid: {'✓ YES' if report.is_valid() else '✗ NO'}\n\n")

        if report.issues:
            f.write("=" * 80 + "\n")
            f.write("ISSUES\n")
            f.write("=" * 80 + "\n\n")

            for issue in report.issues:
                f.write(f"[{issue.severity.value.upper()}] {issue.category}\n")
                f.write(f"  Message: {issue.message}\n")
                if issue.resource_id:
                    f.write(f"  Resource: {issue.resource_id}\n")
                if issue.field:
                    f.write(f"  Field: {issue.field}\n")
                if issue.value is not None:
                    f.write(f"  Value: {issue.value}\n")
                if issue.expected is not None:
                    f.write(f"  Expected: {issue.expected}\n")
                f.write("\n")

    def _write_html_report(self, f, report: ValidationReport):
        """Write HTML format report"""
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Validation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .summary { background: #f0f0f0; padding: 15px; margin-bottom: 20px; }
        .valid { color: green; font-weight: bold; }
        .invalid { color: red; font-weight: bold; }
        .issue { border-left: 4px solid; padding: 10px; margin: 10px 0; }
        .error { border-color: #d32f2f; background: #ffebee; }
        .warning { border-color: #f57c00; background: #fff3e0; }
        .info { border-color: #0288d1; background: #e1f5fe; }
        .severity { font-weight: bold; text-transform: uppercase; }
    </style>
</head>
<body>
    <h1>Validation Report</h1>
""")

        # Summary
        f.write('<div class="summary">\n')
        f.write(f'<p><strong>Timestamp:</strong> {report.timestamp.isoformat()}</p>\n')
        f.write(f'<p><strong>Total Resources:</strong> {report.total_resources}</p>\n')
        f.write(f'<p><strong>Total Issues:</strong> {report.summary["total_issues"]}</p>\n')
        f.write(f'<p><strong>Errors:</strong> {report.summary["errors"]}</p>\n')
        f.write(f'<p><strong>Warnings:</strong> {report.summary["warnings"]}</p>\n')
        f.write(f'<p><strong>Info:</strong> {report.summary["info"]}</p>\n')

        status_class = "valid" if report.is_valid() else "invalid"
        status_text = "✓ VALID" if report.is_valid() else "✗ INVALID"
        f.write(f'<p class="{status_class}"><strong>Status:</strong> {status_text}</p>\n')
        f.write('</div>\n')

        # Issues
        if report.issues:
            f.write('<h2>Issues</h2>\n')
            for issue in report.issues:
                css_class = issue.severity.value
                f.write(f'<div class="issue {css_class}">\n')
                f.write(f'<p class="severity">[{issue.severity.value}] {issue.category}</p>\n')
                f.write(f'<p><strong>Message:</strong> {issue.message}</p>\n')
                if issue.resource_id:
                    f.write(f'<p><strong>Resource:</strong> {issue.resource_id}</p>\n')
                if issue.field:
                    f.write(f'<p><strong>Field:</strong> {issue.field}</p>\n')
                if issue.value is not None:
                    f.write(f'<p><strong>Value:</strong> {issue.value}</p>\n')
                if issue.expected is not None:
                    f.write(f'<p><strong>Expected:</strong> {issue.expected}</p>\n')
                f.write('</div>\n')

        f.write("""
</body>
</html>
""")


# Example usage
if __name__ == '__main__':
    import sys

    # Example: Validate RDF file
    if len(sys.argv) > 1:
        rdf_file = Path(sys.argv[1])

        if rdf_file.exists():
            print(f"Validating {rdf_file}...")

            # Load RDF graph
            graph = Graph()
            graph.parse(rdf_file, format='turtle')

            # Generate report
            generator = ValidationReportGenerator(Path('validation_reports'))
            report = generator.generate_report(rdf_graph=graph)

            # Save report
            generator.save_report(report, format='html')
            generator.save_report(report, format='txt')

            # Print summary
            print(f"\nValidation Summary:")
            print(f"  Total Issues: {report.summary['total_issues']}")
            print(f"  Errors: {report.summary['errors']}")
            print(f"  Warnings: {report.summary['warnings']}")
            print(f"  Valid: {'YES' if report.is_valid() else 'NO'}")
        else:
            print(f"File not found: {rdf_file}")
    else:
        print("Usage: python validation.py <rdf_file.ttl>")
