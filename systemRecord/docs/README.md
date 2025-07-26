# systemRecord - System Fingerprinting Tool

## Overview

systemRecord is a tool for creating detailed system fingerprints by analyzing files and directories, generating SHA256 hashes, and archiving selected files into a tar project file. It's designed to capture system state before and after application installations for comparison purposes.

## Features

- **File System Analysis**: Recursive directory scanning with hash generation
- **Configuration-Driven**: YAML-based configuration for flexible path selection
- **Selective Archiving**: Archive only specified files while fingerprinting all
- **Metadata Collection**: Capture file permissions, ownership, and timestamps
- **Error Handling**: Comprehensive error reporting and logging
- **Containerized**: Docker support for consistent deployment

## Installation

### Prerequisites

- Python 3.11 or higher
- Required Python packages (see requirements.txt)

### Local Installation

1. Clone or download the systemRecord directory
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Docker Installation

1. Build the Docker image:
   ```bash
   docker build -t systemrecord .
   ```

## Usage

### Command Line

```bash
python src/main.py PROJECT_NAME -c CONFIG_FILE [OPTIONS]
```

**Arguments:**
- `PROJECT_NAME`: Name for the project archive
- `-c, --config`: Path to configuration file (required)
- `-o, --output`: Output directory (default: output)
- `-v, --verbose`: Enable verbose logging

**Example:**
```bash
python src/main.py before_install -c config/default.yaml -o /tmp/output
```

### Docker Usage

```bash
# Mount system directories and configuration
docker run -v /:/system:ro -v $(pwd)/config:/config -v $(pwd)/output:/output \
    systemrecord PROJECT_NAME -c /config/default.yaml -o /output
```

## Configuration

The configuration file is in YAML format and controls what paths to scan, what to include/exclude, and archiving rules.

### Configuration Sections

#### Logging
```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Paths
```yaml
paths:
  # Paths to scan
  scan:
    - "/etc"
    - "/usr/local"
    - "/opt"
  
  # Include patterns (glob)
  include:
    - "*.conf"
    - "*.config"
    - "*.log"
  
  # Exclude patterns (glob)
  exclude:
    - "*/tmp/*"
    - "*/.git/*"
    - "*.pyc"
```

#### Archive Settings
```yaml
archive:
  # Maximum file size to archive (bytes)
  max_file_size: 104857600  # 100 MB
  
  # Patterns for files to archive
  patterns:
    - "*.conf"
    - "*.config"
    - "*.sh"
  
  # Exclude from archiving
  exclude_from_archive:
    - "*/passwd"
    - "*/shadow"
    - "*/.ssh/*"
```

## Output

systemRecord generates:

1. **Project Archive** (`PROJECT_NAME.tar.gz`): Contains manifest and archived files
2. **Manifest File** (`manifest.json`): JSON file with all collected data
3. **Log File** (`systemrecord.log`): Operation logs

### Manifest Structure

```json
{
  "metadata": {
    "version": "1.0",
    "created": "2025-01-15T10:30:00",
    "hostname": "server01",
    "platform": "Linux",
    "config_file": "/path/to/config.yaml"
  },
  "files": {
    "/path/to/file": {
      "path": "/path/to/file",
      "metadata": {
        "size": 1024,
        "mode": "0o644",
        "uid": 0,
        "gid": 0,
        "mtime": 1705312200.0,
        "is_file": true,
        "is_symlink": false
      },
      "hash": "sha256_hash_here",
      "archived": true
    }
  },
  "directories": {
    "/path/to/dir": {
      "path": "/path/to/dir",
      "metadata": { ... }
    }
  },
  "errors": []
}
```

## Use Cases

### Before/After Application Installation

1. **Before installation:**
   ```bash
   python src/main.py before_install -c config/app_config.yaml
   ```

2. **After installation:**
   ```bash
   python src/main.py after_install -c config/app_config.yaml
   ```

3. **Compare with systemDiff tool** (see systemDiff documentation)

### System Backup Verification

Create fingerprints before system changes to verify backup integrity.

### Compliance Auditing

Regular system fingerprinting for security and compliance monitoring.

## Security Considerations

- **Sensitive Files**: Configure exclusions for sensitive files (passwords, keys)
- **File Permissions**: Tool preserves file permission information
- **Archive Security**: Archives may contain sensitive configuration files
- **Access Control**: Ensure proper access controls on output files

## Performance

- **Large Filesystems**: Use inclusion/exclusion patterns to limit scope
- **Memory Usage**: Tool processes files individually to minimize memory usage
- **Hash Calculation**: Uses 64KB chunks for efficient memory usage
- **Archive Size**: Control with `max_file_size` and `patterns` settings

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Ensure read access to target directories
   - Use Docker with appropriate volume mounts

2. **Large Archives**
   - Adjust `max_file_size` setting
   - Refine `archive.patterns` to be more selective

3. **Memory Issues**
   - Reduce scope with `paths.include` patterns
   - Increase system memory or use streaming processing

### Logging

Enable debug logging for detailed troubleshooting:
```yaml
logging:
  level: "DEBUG"
```

## Testing

Run the test suite:
```bash
python -m pytest tests/
```

Or run specific tests:
```bash
python tests/test_main.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

[Add appropriate license information]
