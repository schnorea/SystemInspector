#!/usr/bin/env python3
"""
Unit tests for systemRecord
"""

import unittest
import tempfile
import os
import shutil
import json
import tarfile
import yaml
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import SystemRecorder

class TestSystemRecorder(unittest.TestCase):
    """Test cases for SystemRecorder class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")
        self.config_file = os.path.join(self.test_dir, "test_config.yaml")
        
        # Create test configuration
        test_config = {
            'logging': {'level': 'INFO'},
            'paths': {
                'scan': [self.test_dir],
                'include': ['*.txt', '*.py'],
                'exclude': ['*exclude*']
            },
            'archive': {
                'max_file_size': 1024,
                'patterns': ['*.txt']
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        # Create test files
        self.test_file = os.path.join(self.test_dir, "test.txt")
        with open(self.test_file, 'w') as f:
            f.write("Test content")
        
        self.exclude_file = os.path.join(self.test_dir, "exclude_me.txt")
        with open(self.exclude_file, 'w') as f:
            f.write("Should be excluded")
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_config_loading(self):
        """Test configuration loading."""
        recorder = SystemRecorder(self.config_file, self.output_dir)
        self.assertIsNotNone(recorder.config)
        self.assertEqual(recorder.config['logging']['level'], 'INFO')
    
    def test_path_inclusion(self):
        """Test path inclusion logic."""
        recorder = SystemRecorder(self.config_file, self.output_dir)
        
        # Should include .txt files
        self.assertTrue(recorder._should_include_path(self.test_file))
        
        # Should exclude files with 'exclude' in name
        self.assertFalse(recorder._should_include_path(self.exclude_file))
    
    def test_file_archiving_check(self):
        """Test file archiving logic."""
        recorder = SystemRecorder(self.config_file, self.output_dir)
        
        # Should archive .txt files under size limit
        self.assertTrue(recorder._should_archive_file(self.test_file, 100))
        
        # Should not archive files over size limit
        self.assertFalse(recorder._should_archive_file(self.test_file, 2048))
    
    def test_hash_calculation(self):
        """Test file hash calculation."""
        recorder = SystemRecorder(self.config_file, self.output_dir)
        hash_value = recorder._calculate_hash(self.test_file)
        
        # Should return a valid SHA256 hash
        self.assertEqual(len(hash_value), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_value))
    
    def test_file_metadata(self):
        """Test file metadata collection."""
        recorder = SystemRecorder(self.config_file, self.output_dir)
        metadata = recorder._get_file_metadata(self.test_file)
        
        # Should contain expected metadata fields
        self.assertIn('size', metadata)
        self.assertIn('mode', metadata)
        self.assertIn('mtime', metadata)
        self.assertTrue(metadata['is_file'])
        self.assertFalse(metadata['is_directory'])
    
    def test_system_recording(self):
        """Test full system recording process."""
        recorder = SystemRecorder(self.config_file, self.output_dir)
        archive_path = recorder.record_system("test_project")
        
        # Check that archive was created
        self.assertTrue(os.path.exists(archive_path))
        
        # Check that manifest contains expected data
        self.assertIn(self.test_file, recorder.manifest['files'])
        self.assertNotIn(self.exclude_file, recorder.manifest['files'])
        
        # Verify archive contents
        with tarfile.open(archive_path, 'r:gz') as tar:
            names = tar.getnames()
            self.assertIn('manifest.json', names)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "integration_config.yaml")
        
        # Create more complex test structure
        self.subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.subdir)
        
        # Create various test files
        files_to_create = [
            ("config.txt", "Configuration content"),
            ("script.py", "#!/usr/bin/env python\nprint('hello')"),
            ("binary.bin", b"\x00\x01\x02\x03"),
            ("subdir/nested.txt", "Nested file content")
        ]
        
        for filename, content in files_to_create:
            filepath = os.path.join(self.test_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            mode = 'wb' if isinstance(content, bytes) else 'w'
            with open(filepath, mode) as f:
                f.write(content)
        
        # Create integration config
        config = {
            'logging': {'level': 'DEBUG'},
            'paths': {
                'scan': [self.test_dir],
                'include': ['*.txt', '*.py', '*.bin'],
                'exclude': []
            },
            'archive': {
                'max_file_size': 10240,
                'patterns': ['*.txt', '*.py']
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f)
    
    def tearDown(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_full_workflow(self):
        """Test complete recording workflow."""
        output_dir = os.path.join(self.test_dir, "output")
        recorder = SystemRecorder(self.config_file, output_dir)
        
        # Run full recording
        archive_path = recorder.record_system("integration_test")
        
        # Verify results
        self.assertTrue(os.path.exists(archive_path))
        
        # Check manifest content
        manifest = recorder.manifest
        self.assertGreater(len(manifest['files']), 0)
        self.assertIn('metadata', manifest)
        self.assertEqual(manifest['metadata']['version'], '1.0')
        
        # Verify archive structure
        with tarfile.open(archive_path, 'r:gz') as tar:
            # Extract and verify manifest
            manifest_member = tar.extractfile('manifest.json')
            manifest_data = json.loads(manifest_member.read().decode())
            
            self.assertIn('files', manifest_data)
            self.assertIn('metadata', manifest_data)


if __name__ == '__main__':
    unittest.main()
