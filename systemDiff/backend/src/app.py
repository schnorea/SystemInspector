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
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import logging
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

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
    
    def load_project(self, project_id: str, tar_path: str) -> Dict:
        """Load a project from tar file and extract manifest."""
        logger.info(f"Loading project {project_id} from {tar_path}")
        
        try:
            # Create temporary directory for extraction
            temp_dir = tempfile.mkdtemp(prefix=f"project_{project_id}_")
            
            # Extract tar file
            with tarfile.open(tar_path, 'r:*') as tar:
                tar.extractall(temp_dir)
            
            # Load manifest
            manifest_path = os.path.join(temp_dir, 'manifest.json')
            if not os.path.exists(manifest_path):
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

# Global analyzer instance
analyzer = ProjectAnalyzer()

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS or \
           filename.endswith('.tar.gz')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/upload', methods=['POST'])
def upload_project():
    """Upload a project file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    project_id = request.form.get('project_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not project_id:
        return jsonify({'error': 'Project ID required'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{project_id}_{filename}")
        file.save(filepath)
        
        # Load project
        project_summary = analyzer.load_project(project_id, filepath)
        
        return jsonify({
            'message': 'Project uploaded successfully',
            'project': project_summary
        })
    
    except Exception as e:
        logger.error(f"Error uploading project: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all loaded projects."""
    projects = []
    for project_id in analyzer.projects:
        try:
            summary = analyzer.get_project_summary(project_id)
            projects.append(summary)
        except Exception as e:
            logger.error(f"Error getting summary for project {project_id}: {e}")
    
    return jsonify({'projects': projects})

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
        analyzer.cleanup_project(project_id)
        return jsonify({'message': 'Project deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare/<project1_id>/<project2_id>', methods=['GET'])
def compare_projects(project1_id, project2_id):
    """Compare two projects."""
    try:
        comparison = analyzer.compare_projects(project1_id, project2_id)
        return jsonify(comparison)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error comparing projects: {e}")
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

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return jsonify({'error': 'File too large'}), 413

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
