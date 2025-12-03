"""
Unit tests for state.py - State Management
"""
import pytest
from pathlib import Path
import sqlite3

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from state import StateManager


class TestStateManager:
    """Test cases for StateManager"""

    def test_init(self, temp_dir):
        """Test state manager initialization"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        assert state_file.exists()
        assert manager.db_path == state_file

    def test_mark_processed(self, temp_dir):
        """Test marking resource as processed"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        resource_id = 'https://api.example.org/paper/123'
        resource_type = 'paper'

        manager.mark_processed(resource_id, resource_type)

        assert manager.is_processed(resource_id, resource_type)

    def test_is_processed_new_resource(self, temp_dir):
        """Test checking unprocessed resource"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        assert not manager.is_processed('https://api.example.org/paper/999', 'paper')

    def test_mark_failed(self, temp_dir):
        """Test marking resource as failed"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        resource_id = 'https://api.example.org/paper/456'
        resource_type = 'paper'
        error_msg = 'PDF extraction failed'

        manager.mark_failed(resource_id, resource_type, error_msg)

        # Should still be marked as processed
        assert manager.is_processed(resource_id, resource_type)

    def test_checkpoint(self, temp_dir):
        """Test checkpoint creation"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        checkpoint_data = {
            'papers_processed': 100,
            'locations_extracted': 250
        }

        manager.checkpoint('batch_1', checkpoint_data)

        # Verify checkpoint was saved
        checkpoint = manager.get_checkpoint('batch_1')
        assert checkpoint is not None
        assert checkpoint['papers_processed'] == 100

    def test_get_nonexistent_checkpoint(self, temp_dir):
        """Test getting checkpoint that doesn't exist"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        checkpoint = manager.get_checkpoint('nonexistent')
        assert checkpoint is None

    def test_get_statistics(self, temp_dir):
        """Test getting processing statistics"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        # Process some resources
        manager.mark_processed('https://api.example.org/paper/1', 'paper')
        manager.mark_processed('https://api.example.org/paper/2', 'paper')
        manager.mark_failed('https://api.example.org/paper/3', 'paper', 'Error')

        stats = manager.get_statistics()

        assert stats['total_processed'] == 3
        assert stats['successful'] == 2
        assert stats['failed'] == 1

    def test_get_failed_resources(self, temp_dir):
        """Test retrieving failed resources"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        # Mark some as failed
        manager.mark_failed('https://api.example.org/paper/1', 'paper', 'Error 1')
        manager.mark_failed('https://api.example.org/paper/2', 'paper', 'Error 2')

        failed = manager.get_failed_resources('paper')

        assert len(failed) == 2
        assert all(r['resource_type'] == 'paper' for r in failed)

    def test_reset_failed(self, temp_dir):
        """Test resetting failed resources"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        resource_id = 'https://api.example.org/paper/1'

        # Mark as failed
        manager.mark_failed(resource_id, 'paper', 'Error')
        assert manager.is_processed(resource_id, 'paper')

        # Reset
        manager.reset_failed(resource_id, 'paper')
        assert not manager.is_processed(resource_id, 'paper')

    def test_concurrent_access(self, temp_dir):
        """Test concurrent access to state DB"""
        state_file = temp_dir / 'state.db'

        # Create two managers with same DB
        manager1 = StateManager(state_file)
        manager2 = StateManager(state_file)

        # Both mark different resources
        manager1.mark_processed('https://api.example.org/paper/1', 'paper')
        manager2.mark_processed('https://api.example.org/paper/2', 'paper')

        # Both should see all processed
        assert manager1.is_processed('https://api.example.org/paper/1', 'paper')
        assert manager1.is_processed('https://api.example.org/paper/2', 'paper')
        assert manager2.is_processed('https://api.example.org/paper/1', 'paper')
        assert manager2.is_processed('https://api.example.org/paper/2', 'paper')

    def test_start_pipeline_run(self, temp_dir):
        """Test starting a pipeline run"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        config = {'city': 'augsburg', 'batch_size': 50}
        run_id = manager.start_pipeline_run(config)

        assert run_id is not None
        assert isinstance(run_id, int)

    def test_complete_pipeline_run(self, temp_dir):
        """Test completing a pipeline run"""
        state_file = temp_dir / 'state.db'
        manager = StateManager(state_file)

        config = {'city': 'augsburg'}
        run_id = manager.start_pipeline_run(config)

        stats = {
            'papers_processed': 100,
            'locations_extracted': 250
        }

        manager.complete_pipeline_run(run_id, 'completed', stats)

        # Verify run was completed
        conn = sqlite3.connect(state_file)
        cursor = conn.cursor()
        cursor.execute('SELECT status, statistics FROM pipeline_runs WHERE run_id = ?', (run_id,))
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 'completed'
        assert 'papers_processed' in row[1]


class TestStateManagerPersistence:
    """Test persistence across manager instances"""

    def test_state_persists(self, temp_dir):
        """Test that state persists across manager instances"""
        state_file = temp_dir / 'state.db'

        # First manager
        manager1 = StateManager(state_file)
        manager1.mark_processed('https://api.example.org/paper/1', 'paper')

        # Close and create new manager
        del manager1

        manager2 = StateManager(state_file)
        assert manager2.is_processed('https://api.example.org/paper/1', 'paper')

    def test_checkpoint_persists(self, temp_dir):
        """Test that checkpoints persist"""
        state_file = temp_dir / 'state.db'

        # First manager
        manager1 = StateManager(state_file)
        manager1.checkpoint('batch_1', {'count': 100})

        # New manager
        del manager1

        manager2 = StateManager(state_file)
        checkpoint = manager2.get_checkpoint('batch_1')
        assert checkpoint['count'] == 100
