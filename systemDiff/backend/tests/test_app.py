#!/usr/bin/env python3
"""
Unit tests for systemDiff backend
"""

import unittest
import tempfile
import os
import shutil
import json
import tarfile
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app, analyzer, ProjectAnalyzer

class TestProjectAnalyzer(unittest.TestCase):
    """Test cases for ProjectAnalyzer class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.analyzer = ProjectAnalyzer()
        
        # Create test project files
        self.project1_data = self._create_test_project("project1")
        self.project2_data = self._create_test_project("project2")
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_project(self, project_name):
        """Create a test project tar file."""
        project_dir = os.path.join(self.test_dir, project_name)
        os.makedirs(project_dir)
        
        # Create test manifest
        manifest = {
            "metadata": {
                "version": "1.0",
                "created": "2025-01-15T10:00:00",
                "hostname": "test-host",
                "platform": "Linux"
            },
            "files": {
                "/test/file1.txt": {
                    "path": "/test/file1.txt",
                    "metadata": {"size": 100, "mode": "0o644"},
                    "hash": "hash1",
                    "archived": True
                },
                "/test/file2.txt": {
                    "path": "/test/file2.txt",
                    "metadata": {"size": 200, "mode": "0o644"},
                    "hash": "hash2" if project_name == "project1" else "hash2_modified",
                    "archived": True
                }
            },
            "directories": {},
            "errors": []
        }
        
        # Add extra file to project2
        if project_name == "project2":
            manifest["files"]["/test/file3.txt"] = {
                "path": "/test/file3.txt",
                "metadata": {"size": 150, "mode": "0o644"},
                "hash": "hash3",
                "archived": True
            }
        
        # Save manifest
        manifest_path = os.path.join(project_dir, "manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Create archived files directory
        archived_dir = os.path.join(project_dir, "archived_files", "test")
        os.makedirs(archived_dir)
        
        # Create test files
        with open(os.path.join(archived_dir, "file1.txt"), 'w') as f:
            f.write("Content of file1")
        
        content2 = "Content of file2" if project_name == "project1" else "Modified content of file2"
        with open(os.path.join(archived_dir, "file2.txt"), 'w') as f:
            f.write(content2)
        
        if project_name == "project2":
            with open(os.path.join(archived_dir, "file3.txt"), 'w') as f:
                f.write("Content of file3")
        
        # Create tar file
        tar_path = os.path.join(self.test_dir, f"{project_name}.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(project_dir, arcname="", recursive=True)
        
        return {
            'manifest': manifest,
            'tar_path': tar_path
        }
    
    def test_load_project(self):
        """Test project loading."""
        project_summary = self.analyzer.load_project("test1", self.project1_data['tar_path'])
        
        self.assertEqual(project_summary['id'], "test1")
        self.assertEqual(project_summary['file_count'], 2)
        self.assertEqual(project_summary['directory_count'], 0)
        self.assertEqual(project_summary['error_count'], 0)
    
    def test_get_project_summary(self):
        """Test project summary retrieval."""
        self.analyzer.load_project("test1", self.project1_data['tar_path'])
        summary = self.analyzer.get_project_summary("test1")
        
        self.assertEqual(summary['id'], "test1")
        self.assertIn('metadata', summary)
        self.assertIn('statistics', summary)
        self.assertEqual(summary['statistics']['total_files'], 2)
    
    def test_compare_projects(self):
        """Test project comparison."""
        self.analyzer.load_project("test1", self.project1_data['tar_path'])
        self.analyzer.load_project("test2", self.project2_data['tar_path'])
        
        comparison = self.analyzer.compare_projects("test1", "test2")
        
        self.assertEqual(comparison['project1'], "test1")
        self.assertEqual(comparison['project2'], "test2")
        self.assertIn('statistics', comparison)
        self.assertIn('changes', comparison)
        
        # Check statistics
        stats = comparison['statistics']
        self.assertEqual(stats['total_files_before'], 2)
        self.assertEqual(stats['total_files_after'], 3)
        self.assertEqual(stats['new_files'], 1)  # file3.txt added
        self.assertEqual(stats['modified_files'], 1)  # file2.txt modified
        self.assertEqual(stats['unchanged_files'], 1)  # file1.txt unchanged
    
    def test_file_diff(self):
        """Test file diff generation."""
        self.analyzer.load_project("test1", self.project1_data['tar_path'])
        self.analyzer.load_project("test2", self.project2_data['tar_path'])
        
        # Test modified file diff
        diff = self.analyzer.get_file_diff("test1", "test2", "/test/file2.txt")
        
        self.assertEqual(diff['file_path'], "/test/file2.txt")
        self.assertEqual(diff['diff_type'], "modified")
        self.assertIn('diff_html', diff)
        self.assertGreater(diff['content1_size'], 0)
        self.assertGreater(diff['content2_size'], 0)
    
    def test_cleanup_project(self):
        """Test project cleanup."""
        self.analyzer.load_project("test1", self.project1_data['tar_path'])
        self.assertIn("test1", self.analyzer.projects)
        
        self.analyzer.cleanup_project("test1")
        self.assertNotIn("test1", self.analyzer.projects)


class TestFlaskAPI(unittest.TestCase):
    """Test cases for Flask API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app.test_client()
        self.app.testing = True
        
        # Clear global analyzer
        global analyzer
        analyzer.projects.clear()
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.app.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
    
    def test_list_projects_empty(self):
        """Test listing projects when none are loaded."""
        response = self.app.get('/api/projects')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['projects'], [])
    
    def test_get_nonexistent_project(self):
        """Test getting a project that doesn't exist."""
        response = self.app.get('/api/projects/nonexistent')
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_compare_nonexistent_projects(self):
        """Test comparing projects that don't exist."""
        response = self.app.get('/api/compare/proj1/proj2')
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_file_diff_missing_data(self):
        """Test file diff endpoint with missing data."""
        response = self.app.post('/api/diff/proj1/proj2', 
                                content_type='application/json',
                                data=json.dumps({}))
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_export_invalid_format(self):
        """Test export with invalid format."""
        response = self.app.get('/api/export/proj1/proj2/invalid')
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)


if __name__ == '__main__':
    unittest.main()
