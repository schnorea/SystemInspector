#!/usr/bin/env python3
"""
systemDiff Backend - System Comparison API

Provides REST API for comparing systemRecord project files and
serving diff visualization data to the frontend.
"""

import os
import json
import tarfile
import tempfile
import shutil
import difflib
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import logging
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure CORS to allow requests from frontend
CORS(app, 
     origins=['*'],  # Allow all origins for development
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = '/tmp/systemdiff_uploads'
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {'tar', 'gz', 'tar.gz'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class ProjectAnalyzer:
    """Analyzes and compares systemRecord project files."""
    
    def __init__(self):
        self.projects = {}
        self.projects_cache_file = "/tmp/systemdiff_uploads/projects_cache.json"
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._load_projects_cache()
    
    def _load_projects_cache(self):
        """Load projects from cache file."""
        try:
            if os.path.exists(self.projects_cache_file):
                with open(self.projects_cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                # Validate and reload projects
                for project_id, project_info in cache_data.items():
                    tar_path = project_info.get('tar_path')
                    if tar_path and os.path.exists(tar_path):
                        try:
                            # Reload project from tar file
                            self.load_project(project_id, tar_path, from_cache=True)
                            logger.info(f"Restored project {project_id} from cache")
                        except Exception as e:
                            logger.warning(f"Failed to restore project {project_id}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to load projects cache: {e}")
            self.projects = {}
    
    def _save_projects_cache(self):
        """Save projects to cache file."""
        try:
            # Create simplified cache data
            cache_data = {}
            for project_id, project_info in self.projects.items():
                cache_data[project_id] = {
                    'tar_path': project_info.get('tar_path'),
                    'loaded_at': project_info.get('loaded_at')
                }
            
            os.makedirs(os.path.dirname(self.projects_cache_file), exist_ok=True)
            with open(self.projects_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save projects cache: {e}")
    
    def load_project(self, project_id: str, tar_path: str, from_cache: bool = False) -> Dict:
        """Load a project from tar file and extract manifest."""
        with self._lock:  # Thread safety
            logger.info(f"Loading project {project_id} from {tar_path}")
            
            try:
                # Verify file exists and is readable
                if not os.path.exists(tar_path):
                    raise FileNotFoundError(f"Project file not found: {tar_path}")
                
                if not os.access(tar_path, os.R_OK):
                    raise PermissionError(f"Cannot read project file: {tar_path}")
                
                # Check file size
                file_size = os.path.getsize(tar_path)
                logger.info(f"Project file size: {file_size} bytes")
                
                if file_size == 0:
                    raise ValueError("Project file is empty")
                
                # Create temporary directory for extraction
                temp_dir = tempfile.mkdtemp(prefix=f"project_{project_id}_")
                logger.info(f"Extracting to temporary directory: {temp_dir}")
                
                # Extract tar file with better error handling
                try:
                    with tarfile.open(tar_path, 'r:*') as tar:
                        # Check if tar file is valid
                        tar_members = tar.getmembers()
                        logger.info(f"Tar file contains {len(tar_members)} members")
                        tar.extractall(temp_dir)
                except tarfile.TarError as e:
                    raise ValueError(f"Invalid tar file format: {e}")
                
                # Load manifest
                manifest_path = os.path.join(temp_dir, 'manifest.json')
                if not os.path.exists(manifest_path):
                    # List contents of temp_dir for debugging
                    contents = os.listdir(temp_dir)
                    logger.error(f"Manifest not found. Directory contents: {contents}")
                    raise ValueError("No manifest.json found in project file")
                
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                # Store project info
                project_info = {
                    'id': project_id,
                    'manifest': manifest,
                    'temp_dir': temp_dir,
                    'tar_path': tar_path,
                    'loaded_at': datetime.now().isoformat()
                }
                
                self.projects[project_id] = project_info
                
                # Save projects cache (but not when loading from cache to avoid recursion)
                if not from_cache:
                    self._save_projects_cache()
                
                return {
                    'id': project_id,
                    'metadata': manifest.get('metadata', {}),
                    'file_count': len(manifest.get('files', {})),
                    'directory_count': len(manifest.get('directories', {})),
                    'error_count': len(manifest.get('errors', []))
                }
                
            except Exception as e:
                logger.error(f"Error loading project {project_id}: {e}")
                raise
    
    def get_project_summary(self, project_id: str) -> Dict:
        """Get summary information for a project."""
        with self._lock:
            if project_id not in self.projects:
                raise ValueError(f"Project {project_id} not found")
            
            project = self.projects[project_id]
            manifest = project['manifest']
        
        return {
            'id': project_id,
            'metadata': manifest.get('metadata', {}),
            'statistics': {
                'total_files': len(manifest.get('files', {})),
                'total_directories': len(manifest.get('directories', {})),
                'archived_files': sum(1 for f in manifest.get('files', {}).values() if f.get('archived', False)),
                'errors': len(manifest.get('errors', []))
            },
            'loaded_at': project['loaded_at']
        }
    
    def compare_projects(self, project1_id: str, project2_id: str) -> Dict:
        """Compare two projects and return differences."""
        with self._lock:
            if project1_id not in self.projects or project2_id not in self.projects:
                raise ValueError("One or both projects not found")
            
            logger.info(f"Comparing projects {project1_id} and {project2_id}")
            
            project1 = self.projects[project1_id]
            project2 = self.projects[project2_id]
        
        manifest1 = project1['manifest']
        manifest2 = project2['manifest']
        
        files1 = manifest1.get('files', {})
        files2 = manifest2.get('files', {})
        
        # Find differences
        all_paths = set(files1.keys()) | set(files2.keys())
        
        changes = {
            'new_files': [],
            'deleted_files': [],
            'modified_files': [],
            'unchanged_files': []
        }
        
        for path in all_paths:
            if path in files1 and path in files2:
                # File exists in both
                file1 = files1[path]
                file2 = files2[path]
                
                if file1.get('hash') != file2.get('hash'):
                    changes['modified_files'].append({
                        'path': path,
                        'before': file1,
                        'after': file2
                    })
                else:
                    changes['unchanged_files'].append({
                        'path': path,
                        'file': file1
                    })
            elif path in files1:
                # File deleted
                changes['deleted_files'].append({
                    'path': path,
                    'file': files1[path]
                })
            else:
                # File added
                changes['new_files'].append({
                    'path': path,
                    'file': files2[path]
                })
        
        # Calculate statistics
        stats = {
            'total_files_before': len(files1),
            'total_files_after': len(files2),
            'new_files': len(changes['new_files']),
            'deleted_files': len(changes['deleted_files']),
            'modified_files': len(changes['modified_files']),
            'unchanged_files': len(changes['unchanged_files'])
        }
        
        return {
            'project1': project1_id,
            'project2': project2_id,
            'comparison_date': datetime.now().isoformat(),
            'statistics': stats,
            'changes': changes
        }
    
    def get_file_diff(self, project1_id: str, project2_id: str, file_path: str) -> Dict:
        """Get detailed diff for a specific file."""
        if project1_id not in self.projects or project2_id not in self.projects:
            raise ValueError("One or both projects not found")
        
        project1 = self.projects[project1_id]
        project2 = self.projects[project2_id]
        
        # Extract file contents from archives
        content1 = self._extract_file_content(project1, file_path)
        content2 = self._extract_file_content(project2, file_path)
        
        if content1 is None and content2 is None:
            return {'error': 'File not found in either project'}
        
        # Generate diff
        if content1 is None:
            diff_html = self._generate_diff_html([], content2.splitlines(), file_path)
            diff_type = 'added'
        elif content2 is None:
            diff_html = self._generate_diff_html(content1.splitlines(), [], file_path)
            diff_type = 'deleted'
        else:
            diff_html = self._generate_diff_html(content1.splitlines(), content2.splitlines(), file_path)
            diff_type = 'modified'
        
        return {
            'file_path': file_path,
            'diff_type': diff_type,
            'diff_html': diff_html,
            'content1_size': len(content1) if content1 else 0,
            'content2_size': len(content2) if content2 else 0
        }
    
    def _extract_file_content(self, project: Dict, file_path: str) -> Optional[str]:
        """Extract file content from project archive."""
        try:
            archive_path = f"archived_files{file_path}"
            
            with tarfile.open(project['tar_path'], 'r:*') as tar:
                try:
                    member = tar.getmember(archive_path)
                    f = tar.extractfile(member)
                    if f:
                        content = f.read()
                        # Try to decode as text
                        try:
                            return content.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                return content.decode('latin1')
                            except UnicodeDecodeError:
                                return f"<Binary file - {len(content)} bytes>"
                except KeyError:
                    return None
        except Exception as e:
            logger.error(f"Error extracting file {file_path}: {e}")
            return None
    
    def _generate_diff_html(self, lines1: List[str], lines2: List[str], filename: str) -> str:
        """Generate HTML diff representation."""
        differ = difflib.HtmlDiff()
        return differ.make_file(
            lines1, lines2,
            fromdesc=f"Before: {filename}",
            todesc=f"After: {filename}",
            context=True,
            numlines=3
        )
    
    def cleanup_project(self, project_id: str):
        """Clean up temporary files for a project."""
        if project_id in self.projects:
            project = self.projects[project_id]
            if 'temp_dir' in project and os.path.exists(project['temp_dir']):
                shutil.rmtree(project['temp_dir'])
            del self.projects[project_id]
            logger.info(f"Cleaned up project {project_id}")
    
    def generate_mode2_config(self, project1_id: str, project2_id: str) -> Dict:
        """Generate Mode 2 configuration based on comparison of two Mode 1 projects."""
        if project1_id not in self.projects or project2_id not in self.projects:
            raise ValueError("One or both projects not found")
        
        logger.info(f"Generating Mode 2 config from projects {project1_id} and {project2_id}")
        
        project1 = self.projects[project1_id]
        project2 = self.projects[project2_id]
        
        manifest1 = project1['manifest']
        manifest2 = project2['manifest']
        
        files1 = manifest1.get('files', {})
        files2 = manifest2.get('files', {})
        
        # Find differences
        all_paths = set(files1.keys()) | set(files2.keys())
        
        new_files = set()
        deleted_files = set()
        modified_files = set()
        
        for path in all_paths:
            if path in files1 and path in files2:
                # File exists in both - check if modified
                file1 = files1[path]
                file2 = files2[path]
                
                if file1.get('hash') != file2.get('hash'):
                    modified_files.add(path)
            elif path in files1:
                # File deleted
                deleted_files.add(path)
            else:
                # File added
                new_files.add(path)
        
        # Generate file patterns for inclusion
        all_changed_files = new_files | deleted_files | modified_files
        
        # Extract unique directories and file patterns
        directories = set()
        file_extensions = set()
        specific_files = set()
        
        for filepath in all_changed_files:
            # Add directory
            directories.add(str(Path(filepath).parent))
            
            # Add file extension
            suffix = Path(filepath).suffix
            if suffix:
                file_extensions.add(f"*{suffix}")
            
            # Add specific filename patterns for config files
            name = Path(filepath).name
            if any(pattern in name.lower() for pattern in ['conf', 'config', 'cfg', 'ini', 'yaml', 'yml', 'json']):
                specific_files.add(name)
        
        # Create targeted configuration
        mode2_config = {
            "logging": {
                "level": "INFO"
            },
            "paths": {
                "scan": sorted(list(directories)),
                "include": sorted(list(file_extensions | specific_files)) if (file_extensions or specific_files) else ["*"],
                "exclude": [
                    "*/tmp/*",
                    "*/temp/*", 
                    "*/.git/*",
                    "*/__pycache__/*",
                    "*.pyc",
                    "*/cache/*",
                    "*/logs/*.log.*"
                ]
            },
            "archive": {
                "max_file_size": 104857600,  # 100MB
                "patterns": sorted(list(file_extensions | specific_files)) if (file_extensions or specific_files) else ["*"],
                "exclude_from_archive": [
                    "*/passwd",
                    "*/shadow", 
                    "*/sudoers",
                    "*/.ssh/*",
                    "*/ssl/private/*",
                    "*/keys/*",
                    "*/secrets/*"
                ]
            },
            "performance": {
                "worker_threads": 4,
                "hash_chunk_size": 65536,
                "max_files": 0
            },
            "mode2_metadata": {
                "generated_from": {
                    "before_project": project1_id,
                    "after_project": project2_id,
                    "generated_at": datetime.now().isoformat()
                },
                "changes_summary": {
                    "new_files": len(new_files),
                    "deleted_files": len(deleted_files), 
                    "modified_files": len(modified_files),
                    "total_changes": len(all_changed_files)
                }
            }
        }
        
        return mode2_config
    
    def delete_project(self, project_id: str):
        """Delete a project and clean up resources."""
        with self._lock:
            if project_id in self.projects:
                project = self.projects[project_id]
                # Clean up temporary directory
                temp_dir = project.get('temp_dir')
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"Cleaned up temp directory for project {project_id}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
                
                # Remove from projects dict
                del self.projects[project_id]
                
                # Update cache
                self._save_projects_cache()
                
                logger.info(f"Deleted project {project_id}")
            else:
                logger.warning(f"Attempted to delete non-existent project {project_id}")
    
    def cleanup_stale_projects(self):
        """Remove projects whose tar files no longer exist."""
        with self._lock:
            stale_projects = []
            for project_id, project_info in self.projects.items():
                tar_path = project_info.get('tar_path')
                if tar_path and not os.path.exists(tar_path):
                    stale_projects.append(project_id)
            
            for project_id in stale_projects:
                logger.info(f"Removing stale project {project_id}")
                self.delete_project(project_id)
            
            if stale_projects:
                logger.info(f"Cleaned up {len(stale_projects)} stale projects")

# Global analyzer instance
analyzer = ProjectAnalyzer()

def allowed_file(filename):
    """Check if file extension is allowed."""
    if not filename or '.' not in filename:
        return False
    
    # Check for .tar.gz files first
    if filename.lower().endswith('.tar.gz'):
        return True
    
    # Check single extensions
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.before_request
def before_request():
    """Handle CORS preflight requests."""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

@app.after_request
def after_request(response):
    """Add CORS headers to all responses."""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/api/upload', methods=['POST'])
def upload_project():
    """Upload a project file."""
    logger.info(f"Upload request received")
    
    if 'file' not in request.files:
        logger.error("No file provided in request")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    project_id = request.form.get('project_id')
    
    logger.info(f"Upload request: file={file.filename}, project_id={project_id}")
    
    if file.filename == '':
        logger.error("No file selected")
        return jsonify({'error': 'No file selected'}), 400
    
    if not project_id:
        logger.error("No project ID provided")
        return jsonify({'error': 'Project ID required'}), 400
    
    if not allowed_file(file.filename):
        logger.error(f"Invalid file type: {file.filename}")
        return jsonify({'error': f'Invalid file type. Allowed types: {ALLOWED_EXTENSIONS}'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{project_id}_{filename}")
        logger.info(f"Saving file to: {filepath}")
        
        file.save(filepath)
        logger.info(f"File saved successfully, size: {os.path.getsize(filepath)} bytes")
        
        # Load project
        project_summary = analyzer.load_project(project_id, filepath)
        logger.info(f"Project {project_id} loaded successfully")
        
        return jsonify({
            'message': 'Project uploaded successfully',
            'project': project_summary
        })
    
    except ValueError as e:
        logger.error(f"Validation error uploading project {project_id}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error uploading project {project_id}: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all loaded projects."""
    logger.info("GET /api/projects request received")
    
    try:
        # Clean up stale projects first
        analyzer.cleanup_stale_projects()
        
        # Use lock to ensure thread-safe access to projects
        with analyzer._lock:
            projects = []
            project_ids = list(analyzer.projects.keys())
            logger.info(f"Found {len(project_ids)} projects: {project_ids}")
            
            for project_id in project_ids:
                try:
                    # Double-check the project still exists
                    if project_id in analyzer.projects:
                        summary = analyzer.get_project_summary(project_id)
                        projects.append(summary)
                        logger.info(f"Added project {project_id} to response")
                    else:
                        logger.warning(f"Project {project_id} disappeared during iteration")
                except Exception as e:
                    logger.error(f"Error getting summary for project {project_id}: {e}")
            
            logger.info(f"Returning {len(projects)} projects")
            return jsonify({
                'projects': projects,
                'total_count': len(projects),
                'timestamp': datetime.now().isoformat()
            })
    
    except Exception as e:
        logger.error(f"Unexpected error in list_projects: {e}")
        return jsonify({'error': f'Failed to list projects: {str(e)}'}), 500

@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details."""
    try:
        summary = analyzer.get_project_summary(project_id)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project."""
    try:
        analyzer.delete_project(project_id)
        return jsonify({'message': 'Project deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare/<project1_id>/<project2_id>', methods=['GET'])
def compare_projects(project1_id, project2_id):
    """Compare two projects."""
    logger.info(f"Compare request: {project1_id} vs {project2_id}")
    logger.info(f"Available projects: {list(analyzer.projects.keys())}")
    
    try:
        comparison = analyzer.compare_projects(project1_id, project2_id)
        return jsonify(comparison)
    except ValueError as e:
        logger.error(f"ValueError comparing projects {project1_id} vs {project2_id}: {e}")
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Unexpected error comparing projects {project1_id} vs {project2_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diff/<project1_id>/<project2_id>', methods=['POST'])
def get_file_diff(project1_id, project2_id):
    """Get diff for a specific file."""
    data = request.get_json()
    if not data or 'file_path' not in data:
        return jsonify({'error': 'File path required'}), 400
    
    file_path = data['file_path']
    
    try:
        diff = analyzer.get_file_diff(project1_id, project2_id, file_path)
        return jsonify(diff)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting file diff: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<project1_id>/<project2_id>/<format>', methods=['GET'])
def export_comparison(project1_id, project2_id, format):
    """Export comparison results."""
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use csv or json'}), 400
    
    try:
        comparison = analyzer.compare_projects(project1_id, project2_id)
        
        if format == 'json':
            # Return JSON export
            response = app.response_class(
                response=json.dumps(comparison, indent=2),
                status=200,
                mimetype='application/json'
            )
            response.headers['Content-Disposition'] = f'attachment; filename=comparison_{project1_id}_{project2_id}.json'
            return response
        
        elif format == 'csv':
            # Generate CSV export
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Change Type', 'File Path', 'Size Before', 'Size After', 'Hash Before', 'Hash After'])
            
            # Write data
            for change_type, files in comparison['changes'].items():
                for file_info in files:
                    if change_type == 'modified_files':
                        writer.writerow([
                            'Modified',
                            file_info['path'],
                            file_info['before']['metadata'].get('size', ''),
                            file_info['after']['metadata'].get('size', ''),
                            file_info['before'].get('hash', ''),
                            file_info['after'].get('hash', '')
                        ])
                    elif change_type == 'new_files':
                        writer.writerow([
                            'Added',
                            file_info['path'],
                            '',
                            file_info['file']['metadata'].get('size', ''),
                            '',
                            file_info['file'].get('hash', '')
                        ])
                    elif change_type == 'deleted_files':
                        writer.writerow([
                            'Deleted',
                            file_info['path'],
                            file_info['file']['metadata'].get('size', ''),
                            '',
                            file_info['file'].get('hash', ''),
                            ''
                        ])
            
            response = app.response_class(
                response=output.getvalue(),
                status=200,
                mimetype='text/csv'
            )
            response.headers['Content-Disposition'] = f'attachment; filename=comparison_{project1_id}_{project2_id}.csv'
            return response
    
    except Exception as e:
        logger.error(f"Error exporting comparison: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-config/<project1_id>/<project2_id>', methods=['GET'])
def generate_mode2_config(project1_id, project2_id):
    """Generate Mode 2 configuration from two Mode 1 projects."""
    try:
        config = analyzer.generate_mode2_config(project1_id, project2_id)
        
        # Convert to YAML format for download
        import yaml
        yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        response = app.response_class(
            response=yaml_content,
            status=200,
            mimetype='application/x-yaml'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=mode2_config_{project1_id}_{project2_id}.yaml'
        return response
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error generating Mode 2 config: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return jsonify({'error': 'File too large'}), 413

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
