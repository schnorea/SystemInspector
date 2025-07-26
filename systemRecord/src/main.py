#!/usr/bin/env python3
"""
systemRecord - System Fingerprinting Tool

Creates system fingerprints by analyzing files and directories,
generating hashes, and archiving selected files into a tar project file.
"""

import os
import sys
import argparse
import logging
import hashlib
import tarfile
import json
import yaml
import time
import stat
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class SystemRecorder:
    """Main class for system recording functionality."""
    
    def __init__(self, config_path: str, output_dir: str = "output", mode: int = 1):
        """Initialize the SystemRecorder with configuration."""
        self.config_path = config_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.mode = mode
        
        # Load configuration
        self.config = self._load_config()
        
        # Setup logging
        self._setup_logging()
        
        # Initialize data structures
        self.manifest = {
            "metadata": {
                "version": "2.0",  # Updated version for mode support
                "created": datetime.now().isoformat(),
                "hostname": os.uname().nodename,
                "platform": os.uname().sysname,
                "config_file": config_path,
                "mode": mode
            },
            "files": {},
            "directories": {},
            "errors": []
        }
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config file {self.config_path}: {e}")
            sys.exit(1)
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        log_file = self.output_dir / 'systemrecord.log'
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _should_include_path(self, path: str) -> bool:
        """Check if a path should be included based on configuration and mode."""
        path_obj = Path(path)
        
        # Mode 1: Broader scope - only exclude patterns matter
        if self.mode == 1:
            # Check exclusion patterns
            exclude_patterns = self.config.get('paths', {}).get('exclude', [])
            if exclude_patterns:
                excluded = any(path_obj.match(pattern) for pattern in exclude_patterns)
                if excluded:
                    return False
            return True
        
        # Mode 2: Use both include and exclude patterns for targeted scanning
        if self.mode == 2:
            # Check inclusion patterns
            include_patterns = self.config.get('paths', {}).get('include', [])
            if include_patterns:
                included = any(path_obj.match(pattern) for pattern in include_patterns)
                if not included:
                    return False
            
            # Check exclusion patterns
            exclude_patterns = self.config.get('paths', {}).get('exclude', [])
            if exclude_patterns:
                excluded = any(path_obj.match(pattern) for pattern in exclude_patterns)
                if excluded:
                    return False
        
        return True
    
    def _should_archive_file(self, path: str, size: int) -> bool:
        """Check if a file should be archived based on configuration and mode."""
        # Mode 1: No archiving - only fingerprinting
        if self.mode == 1:
            return False
        
        # Mode 2: Archive based on configuration
        if self.mode == 2:
            # Check file size limit
            max_size = self.config.get('archive', {}).get('max_file_size', 100 * 1024 * 1024)  # 100MB default
            if size > max_size:
                return False
            
            # Check archive patterns
            archive_patterns = self.config.get('archive', {}).get('patterns', ['*'])
            path_obj = Path(path)
            return any(path_obj.match(pattern) for pattern in archive_patterns)
        
        return False
    
    def _calculate_hash(self, filepath: str) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {filepath}: {e}")
            self.manifest["errors"].append(f"Hash calculation failed for {filepath}: {e}")
            return ""
    
    def _get_file_metadata(self, filepath: str) -> Dict:
        """Get file metadata including permissions, ownership, and timestamps."""
        try:
            stat_info = os.stat(filepath)
            return {
                "size": stat_info.st_size,
                "mode": oct(stat_info.st_mode),
                "uid": stat_info.st_uid,
                "gid": stat_info.st_gid,
                "mtime": stat_info.st_mtime,
                "ctime": stat_info.st_ctime,
                "atime": stat_info.st_atime,
                "is_symlink": os.path.islink(filepath),
                "is_directory": os.path.isdir(filepath),
                "is_file": os.path.isfile(filepath)
            }
        except Exception as e:
            self.logger.error(f"Error getting metadata for {filepath}: {e}")
            return {}
    
    def _scan_directory(self, root_path: str) -> None:
        """Recursively scan directory and collect file information."""
        self.logger.info(f"Scanning directory: {root_path}")
        
        try:
            for root, dirs, files in os.walk(root_path):
                # Filter directories based on configuration
                dirs[:] = [d for d in dirs if self._should_include_path(os.path.join(root, d))]
                
                # Process files
                for file in files:
                    filepath = os.path.join(root, file)
                    
                    if not self._should_include_path(filepath):
                        continue
                    
                    try:
                        metadata = self._get_file_metadata(filepath)
                        if not metadata:
                            continue
                        
                        file_info = {
                            "path": filepath,
                            "metadata": metadata,
                            "hash": self._calculate_hash(filepath) if metadata.get("is_file") else "",
                            "archived": False
                        }
                        
                        # Check if file should be archived
                        if metadata.get("is_file") and self._should_archive_file(filepath, metadata.get("size", 0)):
                            file_info["archived"] = True
                        
                        self.manifest["files"][filepath] = file_info
                        
                    except Exception as e:
                        self.logger.error(f"Error processing file {filepath}: {e}")
                        self.manifest["errors"].append(f"File processing failed for {filepath}: {e}")
                
                # Process directories
                for directory in dirs:
                    dirpath = os.path.join(root, directory)
                    try:
                        metadata = self._get_file_metadata(dirpath)
                        if metadata:
                            self.manifest["directories"][dirpath] = {
                                "path": dirpath,
                                "metadata": metadata
                            }
                    except Exception as e:
                        self.logger.error(f"Error processing directory {dirpath}: {e}")
                        self.manifest["errors"].append(f"Directory processing failed for {dirpath}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error scanning directory {root_path}: {e}")
            self.manifest["errors"].append(f"Directory scan failed for {root_path}: {e}")
    
    def _create_project_archive(self, project_name: str) -> str:
        """Create tar archive with manifest and selected files."""
        archive_path = self.output_dir / f"{project_name}.tar.gz"
        
        self.logger.info(f"Creating project archive: {archive_path}")
        
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                # Add manifest file
                manifest_path = self.output_dir / "manifest.json"
                with open(manifest_path, 'w') as f:
                    json.dump(self.manifest, f, indent=2)
                tar.add(manifest_path, arcname="manifest.json")
                
                # Add archived files
                for filepath, file_info in self.manifest["files"].items():
                    if file_info.get("archived", False):
                        try:
                            if os.path.exists(filepath):
                                # Use relative path in archive to avoid absolute path issues
                                arcname = f"archived_files{filepath}"
                                tar.add(filepath, arcname=arcname)
                        except Exception as e:
                            self.logger.error(f"Error archiving file {filepath}: {e}")
                            self.manifest["errors"].append(f"Archive failed for {filepath}: {e}")
            
            self.logger.info(f"Project archive created successfully: {archive_path}")
            return str(archive_path)
        
        except Exception as e:
            self.logger.error(f"Error creating project archive: {e}")
            raise
    
    def record_system(self, project_name: str) -> str:
        """Main method to record system state."""
        self.logger.info(f"Starting system recording for project: {project_name}")
        
        # Get paths to scan from configuration
        scan_paths = self.config.get('paths', {}).get('scan', ['/'])
        
        for path in scan_paths:
            if os.path.exists(path):
                self._scan_directory(path)
            else:
                self.logger.warning(f"Scan path does not exist: {path}")
        
        # Create project archive
        archive_path = self._create_project_archive(project_name)
        
        # Log summary
        total_files = len(self.manifest["files"])
        archived_files = sum(1 for f in self.manifest["files"].values() if f.get("archived"))
        total_dirs = len(self.manifest["directories"])
        errors = len(self.manifest["errors"])
        
        self.logger.info(f"Recording complete:")
        self.logger.info(f"  - Files processed: {total_files}")
        self.logger.info(f"  - Files archived: {archived_files}")
        self.logger.info(f"  - Directories processed: {total_dirs}")
        self.logger.info(f"  - Errors encountered: {errors}")
        
        return archive_path
    
    def generate_mode2_config(self, before_project: str, after_project: str, output_config_path: str) -> str:
        """Generate a targeted Mode 2 configuration based on comparison of two Mode 1 projects."""
        try:
            # Load both project manifests
            before_manifest = self._load_project_manifest(before_project)
            after_manifest = self._load_project_manifest(after_project)
            
            if not before_manifest or not after_manifest:
                raise ValueError("Could not load project manifests")
            
            # Find differences
            before_files = set(before_manifest.get("files", {}).keys())
            after_files = set(after_manifest.get("files", {}).keys())
            
            # Categorize changes
            new_files = after_files - before_files
            deleted_files = before_files - after_files
            common_files = before_files & after_files
            
            # Find modified files
            modified_files = set()
            for filepath in common_files:
                before_hash = before_manifest["files"][filepath].get("hash", "")
                after_hash = after_manifest["files"][filepath].get("hash", "")
                if before_hash != after_hash:
                    modified_files.add(filepath)
            
            # Generate file patterns for inclusion
            all_changed_files = new_files | deleted_files | modified_files
            
            # Extract unique directories and file patterns
            directories = set()
            file_extensions = set()
            
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
                    file_extensions.add(name)
            
            # Create targeted configuration
            mode2_config = {
                "logging": {
                    "level": "INFO"
                },
                "paths": {
                    "scan": sorted(list(directories)),
                    "include": sorted(list(file_extensions)) if file_extensions else ["*"],
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
                    "patterns": sorted(list(file_extensions)) if file_extensions else ["*"],
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
                        "before_project": before_project,
                        "after_project": after_project,
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
            
            # Write configuration file
            with open(output_config_path, 'w') as f:
                yaml.dump(mode2_config, f, default_flow_style=False, sort_keys=False)
            
            self.logger.info(f"Generated Mode 2 configuration: {output_config_path}")
            self.logger.info(f"  - New files: {len(new_files)}")
            self.logger.info(f"  - Deleted files: {len(deleted_files)}")
            self.logger.info(f"  - Modified files: {len(modified_files)}")
            self.logger.info(f"  - Total changed files: {len(all_changed_files)}")
            self.logger.info(f"  - Unique directories: {len(directories)}")
            self.logger.info(f"  - File patterns: {len(file_extensions)}")
            
            return output_config_path
            
        except Exception as e:
            self.logger.error(f"Error generating Mode 2 config: {e}")
            raise
    
    def _load_project_manifest(self, tar_path: str) -> Optional[Dict]:
        """Load manifest from a project tar file."""
        try:
            with tarfile.open(tar_path, 'r:*') as tar:
                manifest_member = tar.getmember('manifest.json')
                manifest_file = tar.extractfile(manifest_member)
                if manifest_file:
                    return json.loads(manifest_file.read().decode())
        except Exception as e:
            self.logger.error(f"Error loading manifest from {tar_path}: {e}")
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="systemRecord - System Fingerprinting Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Record command
    record_parser = subparsers.add_parser('record', help='Record system fingerprint')
    record_parser.add_argument("project_name", help="Name for the project archive")
    record_parser.add_argument("-c", "--config", required=True, help="Path to configuration file")
    record_parser.add_argument("-o", "--output", default="output", help="Output directory (default: output)")
    record_parser.add_argument("-m", "--mode", type=int, choices=[1, 2], default=1, 
                              help="Mode: 1=Broad fingerprinting (default), 2=Targeted with archiving")
    record_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    # Generate config command
    config_parser = subparsers.add_parser('generate-config', help='Generate Mode 2 config from Mode 1 comparison')
    config_parser.add_argument("before_project", help="Path to before project tar file")
    config_parser.add_argument("after_project", help="Path to after project tar file")
    config_parser.add_argument("-o", "--output", required=True, help="Output path for generated config file")
    config_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Handle no command specified (backward compatibility)
    if not args.command:
        # Old style: treat all args as record command
        parser = argparse.ArgumentParser(description="systemRecord - System Fingerprinting Tool")
        parser.add_argument("project_name", help="Name for the project archive")
        parser.add_argument("-c", "--config", required=True, help="Path to configuration file")
        parser.add_argument("-o", "--output", default="output", help="Output directory (default: output)")
        parser.add_argument("-m", "--mode", type=int, choices=[1, 2], default=1, 
                           help="Mode: 1=Broad fingerprinting (default), 2=Targeted with archiving")
        parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
        args = parser.parse_args()
        args.command = 'record'
    
    if args.command == 'record':
        # Validate configuration file exists
        if not os.path.exists(args.config):
            print(f"Error: Configuration file {args.config} not found")
            sys.exit(1)
        
        try:
            # Create recorder instance with mode
            recorder = SystemRecorder(args.config, args.output, args.mode)
            
            # Record system
            archive_path = recorder.record_system(args.project_name)
            
            print(f"System recording completed successfully!")
            print(f"Mode: {args.mode} ({'Broad fingerprinting' if args.mode == 1 else 'Targeted with archiving'})")
            print(f"Project archive created: {archive_path}")
            
        except Exception as e:
            print(f"Error during system recording: {e}")
            sys.exit(1)
    
    elif args.command == 'generate-config':
        # Validate project files exist
        if not os.path.exists(args.before_project):
            print(f"Error: Before project file {args.before_project} not found")
            sys.exit(1)
        if not os.path.exists(args.after_project):
            print(f"Error: After project file {args.after_project} not found")
            sys.exit(1)
        
        try:
            # Create recorder instance (mode doesn't matter for config generation)
            recorder = SystemRecorder("/dev/null", ".", 1)  # Dummy config
            
            # Generate Mode 2 configuration
            config_path = recorder.generate_mode2_config(
                args.before_project, 
                args.after_project, 
                args.output
            )
            
            print(f"Mode 2 configuration generated successfully!")
            print(f"Configuration file: {config_path}")
            print(f"Use this config with: systemRecord record project_name -c {config_path} -m 2")
            
        except Exception as e:
            print(f"Error generating configuration: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
