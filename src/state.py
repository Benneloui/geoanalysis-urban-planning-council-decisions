"""
Pipeline State Management
=========================

SQLite-based state tracking for crash recovery and incremental processing.
Tracks which papers/meetings have been processed to enable resuming after failures.

Usage:
    from src.state import StateManager

    state = StateManager(db_path="data/processed/pipeline_state.db")

    # Check if paper was processed
    if not state.is_processed("paper_123"):
        # Process paper
        process_paper(paper)
        state.mark_processed("paper_123", "paper")

    # Checkpoint batch
    state.checkpoint(processed_ids, resource_type="paper")
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manage pipeline state using SQLite for crash recovery.

    Tracks:
    - Processed resource IDs (papers, meetings, agenda items)
    - Processing timestamps
    - Processing status (pending, completed, failed)
    - Last checkpoint information
    - Pipeline metadata

    Attributes:
        db_path: Path to SQLite database
        connection: SQLite connection
    """

    def __init__(
        self,
        db_path: str = "data/processed/pipeline_state.db",
        auto_commit: bool = True
    ):
        """
        Initialize state manager.

        Args:
            db_path: Path to SQLite database file OR config dict
            auto_commit: Auto-commit after each operation
        """
        # Handle config dict as first argument (for tests)
        if isinstance(db_path, dict):
            config = db_path
            storage_config = config.get('storage', {})
            base_path = storage_config.get('base_path', 'data/processed')
            db_path = f"{base_path}/pipeline_state.db"
            auto_commit = True

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.auto_commit = auto_commit

        # Create connection
        self.connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False
        )
        self.connection.row_factory = sqlite3.Row  # Enable column access by name

        # Initialize schema
        self._init_schema()

        logger.info(f"StateManager initialized: {self.db_path}")

    def _init_schema(self):
        """Create database tables if they don't exist."""
        cursor = self.connection.cursor()

        # Table: processed_resources
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_resources (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                status TEXT DEFAULT 'completed',
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP,
                metadata TEXT,
                error_message TEXT
            )
        """)

        # Table: checkpoints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                checkpoint_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                batch_size INTEGER,
                total_processed INTEGER,
                metadata TEXT
            )
        """)

        # Table: pipeline_runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'running',
                city TEXT,
                config TEXT,
                stats TEXT
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_resource_type
            ON processed_resources(resource_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON processed_resources(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_at
            ON processed_resources(processed_at)
        """)

        self.connection.commit()
        logger.debug("Database schema initialized")

    def is_processed(self, resource_id: str) -> bool:
        """
        Check if a resource has been successfully processed.

        Args:
            resource_id: Resource identifier (OParl ID/URL)

        Returns:
            True only if resource was processed with 'completed' status.
            Failed resources return False and can be retried.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT status FROM processed_resources WHERE id = ?",
            (resource_id,)
        )
        result = cursor.fetchone()

        # Return True only for completed status, False for failed/missing
        return result is not None and result['status'] == 'completed'

    def mark_processed(
        self,
        resource_id: str,
        resource_type: str,
        status: str = 'completed',
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """
        Mark a resource as processed.

        Args:
            resource_id: Resource identifier
            resource_type: Type (paper, meeting, agenda_item)
            status: Processing status (completed, failed, pending)
            metadata: Additional metadata dictionary
            error_message: Error message if status is failed
        """
        cursor = self.connection.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute("""
            INSERT OR REPLACE INTO processed_resources
            (id, resource_type, status, processed_at, metadata, error_message)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """, (resource_id, resource_type, status, metadata_json, error_message))

        if self.auto_commit:
            self.connection.commit()

    def mark_batch_processed(
        self,
        resource_ids: List[str],
        resource_type: str,
        status: str = 'completed'
    ):
        """
        Mark multiple resources as processed in a single transaction.

        Args:
            resource_ids: List of resource identifiers
            resource_type: Type of resources
            status: Processing status
        """
        cursor = self.connection.cursor()

        data = [
            (rid, resource_type, status)
            for rid in resource_ids
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO processed_resources
            (id, resource_type, status, processed_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, data)

        if self.auto_commit:
            self.connection.commit()

        logger.info(f"Marked {len(resource_ids)} {resource_type}(s) as {status}")

    def get_processed_ids(
        self,
        resource_type: Optional[str] = None,
        status: str = 'completed'
    ) -> Set[str]:
        """
        Get set of processed resource IDs.

        Args:
            resource_type: Filter by resource type (optional)
            status: Filter by status

        Returns:
            Set of processed resource IDs
        """
        cursor = self.connection.cursor()

        if resource_type:
            cursor.execute(
                "SELECT id FROM processed_resources WHERE resource_type = ? AND status = ?",
                (resource_type, status)
            )
        else:
            cursor.execute(
                "SELECT id FROM processed_resources WHERE status = ?",
                (status,)
            )

        return {row['id'] for row in cursor.fetchall()}

    def get_failed_resources(
        self,
        resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of failed resources with error messages.

        Args:
            resource_type: Filter by resource type (optional)

        Returns:
            List of failed resource dictionaries
        """
        cursor = self.connection.cursor()

        if resource_type:
            cursor.execute("""
                SELECT id, resource_type, error_message, processed_at
                FROM processed_resources
                WHERE status = 'failed' AND resource_type = ?
                ORDER BY processed_at DESC
            """, (resource_type,))
        else:
            cursor.execute("""
                SELECT id, resource_type, error_message, processed_at
                FROM processed_resources
                WHERE status = 'failed'
                ORDER BY processed_at DESC
            """)

        return [dict(row) for row in cursor.fetchall()]

    def checkpoint(
        self,
        resource_type: str,
        batch_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Create a checkpoint for the current processing state.

        Args:
            resource_type: Type of resources being processed
            batch_size: Number of resources in this batch
            metadata: Additional checkpoint metadata

        Returns:
            Checkpoint ID
        """
        cursor = self.connection.cursor()

        # Count total processed
        cursor.execute(
            "SELECT COUNT(*) as count FROM processed_resources WHERE resource_type = ? AND status = 'completed'",
            (resource_type,)
        )
        total_processed = cursor.fetchone()['count']

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute("""
            INSERT INTO checkpoints
            (resource_type, batch_size, total_processed, metadata)
            VALUES (?, ?, ?, ?)
        """, (resource_type, batch_size, total_processed, metadata_json))

        checkpoint_id = cursor.lastrowid

        if self.auto_commit:
            self.connection.commit()

        logger.info(
            f"Checkpoint {checkpoint_id}: {batch_size} {resource_type}(s), "
            f"Total: {total_processed}"
        )

        return checkpoint_id

    def get_last_checkpoint(
        self,
        resource_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the last checkpoint for a resource type.

        Args:
            resource_type: Type of resources

        Returns:
            Checkpoint dictionary or None (metadata field is deserialized from JSON)
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM checkpoints
            WHERE resource_type = ?
            ORDER BY checkpoint_time DESC
            LIMIT 1
        """, (resource_type,))

        row = cursor.fetchone()
        if row:
            checkpoint = dict(row)
            # Deserialize metadata JSON if present
            if checkpoint.get('metadata'):
                try:
                    metadata = json.loads(checkpoint['metadata'])
                    # Merge metadata into top-level dict for easier access
                    checkpoint.update(metadata)
                except (json.JSONDecodeError, TypeError):
                    pass
            return checkpoint
        return None

    def start_pipeline_run(
        self,
        city: str,
        config: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Start a new pipeline run.

        Args:
            city: City being processed
            config: Configuration dictionary

        Returns:
            Run ID
        """
        cursor = self.connection.cursor()

        config_json = json.dumps(config) if config else None

        cursor.execute("""
            INSERT INTO pipeline_runs (city, config, status)
            VALUES (?, ?, 'running')
        """, (city, config_json))

        run_id = cursor.lastrowid

        if self.auto_commit:
            self.connection.commit()

        logger.info(f"Started pipeline run {run_id} for {city}")
        return run_id

    def end_pipeline_run(
        self,
        run_id: int,
        status: str = 'completed',
        stats: Optional[Dict[str, Any]] = None
    ):
        """
        End a pipeline run.

        Args:
            run_id: Run ID from start_pipeline_run
            status: Final status (completed, failed)
            stats: Processing statistics
        """
        cursor = self.connection.cursor()

        stats_json = json.dumps(stats) if stats else None

        cursor.execute("""
            UPDATE pipeline_runs
            SET end_time = CURRENT_TIMESTAMP, status = ?, stats = ?
            WHERE run_id = ?
        """, (status, stats_json, run_id))

        if self.auto_commit:
            self.connection.commit()

        logger.info(f"Pipeline run {run_id} ended with status: {status}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Statistics dictionary with overall counts and breakdowns by type
        """
        cursor = self.connection.cursor()

        stats = {}

        # Count by resource type and status
        cursor.execute("""
            SELECT resource_type, status, COUNT(*) as count
            FROM processed_resources
            GROUP BY resource_type, status
        """)

        by_type = {}
        total_completed = 0
        total_failed = 0

        for row in cursor.fetchall():
            rtype = row['resource_type']
            if rtype not in by_type:
                by_type[rtype] = {}
            by_type[rtype][row['status']] = row['count']

            # Accumulate totals
            if row['status'] == 'completed':
                total_completed += row['count']
            elif row['status'] == 'failed':
                total_failed += row['count']

        stats['by_resource_type'] = by_type
        stats['completed'] = total_completed
        stats['failed'] = total_failed

        # Recent checkpoints
        cursor.execute("""
            SELECT resource_type, checkpoint_time, total_processed
            FROM checkpoints
            ORDER BY checkpoint_time DESC
            LIMIT 5
        """)

        stats['recent_checkpoints'] = [dict(row) for row in cursor.fetchall()]

        # Pipeline runs
        cursor.execute("""
            SELECT run_id, city, start_time, end_time, status
            FROM pipeline_runs
            ORDER BY start_time DESC
            LIMIT 5
        """)

        stats['recent_runs'] = [dict(row) for row in cursor.fetchall()]

        return stats

    def clear_failed(self):
        """Remove all failed resource entries to allow reprocessing."""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM processed_resources WHERE status = 'failed'")
        deleted = cursor.rowcount

        if self.auto_commit:
            self.connection.commit()

        logger.info(f"Cleared {deleted} failed resource(s)")
        return deleted

    def reset(self):
        """Reset all state (WARNING: deletes all tracking data)."""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM processed_resources")
        cursor.execute("DELETE FROM checkpoints")
        cursor.execute("DELETE FROM pipeline_runs")

        if self.auto_commit:
            self.connection.commit()

        logger.warning("State database reset - all tracking data deleted")

    def commit(self):
        """Manually commit changes (when auto_commit=False)."""
        self.connection.commit()

    def close(self):
        """Close database connection."""
        self.connection.close()
        logger.info("StateManager closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            self.commit()
        self.close()
