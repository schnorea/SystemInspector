# systemRecord - System Fingerprinting Tool

## Overview

systemRecord is a tool for creating detailed system fingerprints with two distinct operational modes:

**Mode 1 - Broad Fingerprinting:**
- Scans the entire file system structure to identify all changes
- Records SHA256 hashes and metadata for all files (excluding ignore patterns)
- No file archiving - focuses on change detection and identification
- Creates comprehensive baseline for comparison
- Ideal for initial analysis and change discovery

**Mode 2 - Targeted Analysis:**
- Focused scanning based on known changes (from Mode 1 or manual configuration)
- Archives actual file contents for detailed diff analysis
- Uses targeted configuration to examine specific files and directories
- Enables detailed before/after file content comparison
- Ideal for in-depth analysis of specific changes

The tool is designed to work in a two-phase approach: use Mode 1 to identify what changed, then use Mode 2 for detailed analysis of those changes.

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

## Quick Start

### Using Python Directly

1. **Install dependencies:**
   ```bash
   cd systemRecord
   pip install -r requirements.txt
   ```

2. **Create a basic configuration:**
   ```bash
   cp config/mode1.yaml config/my-config.yaml
   # Edit config/my-config.yaml as needed
   ```

3. **Record system state:**
   ```bash
   # Mode 1: Broad fingerprinting
   python src/main.py record before_install -c config/my-config.yaml -m 1 -o output/
   
   # Make your changes (install software, etc.)
   
   # Capture after state
   python src/main.py record after_install -c config/my-config.yaml -m 1 -o output/
   ```

### Using Docker (Recommended)

1. **Build the container:**
   ```bash
   cd systemRecord
   docker build -t systemrecord .
   ```

2. **Record system state using run.sh script:**
   ```bash
   # Mode 1: Broad fingerprinting
   ./run.sh record before_install -c config/mode1.yaml -m 1
   
   # Make your changes (install software, etc.)
   
   # Capture after state
   ./run.sh record after_install -c config/mode1.yaml -m 1
   ```

3. **Or run Docker manually:**
   ```bash
   # Mode 1: Broad fingerprinting
   docker run --user $(id -u):$(id -g) \
       -v /:/system:ro \
       -v $(pwd)/config:/config:ro \
       -v $(pwd)/output:/output \
       systemrecord record before_install -c /config/mode1.yaml -m 1
   ```

3. **Generate Mode 2 configuration (optional):**
   ```bash
   # Using run.sh script
   ./run.sh generate-config output/before_install.tar.gz output/after_install.tar.gz -o config/targeted.yaml
   
   # Or using Docker directly
   docker run --user $(id -u):$(id -g) \
       -v $(pwd)/output:/output \
       -v $(pwd)/config:/config \
       systemrecord generate-config /output/before_install.tar.gz /output/after_install.tar.gz -o /config/targeted.yaml
   
   # Python
   python src/main.py generate-config output/before_install.tar.gz output/after_install.tar.gz -o config/targeted.yaml
   ```

## Usage

### Command Line

```bash
# Recording system state
python src/main.py record PROJECT_NAME -c CONFIG_FILE [OPTIONS]

# Generating Mode 2 configuration
python src/main.py generate-config BEFORE_PROJECT AFTER_PROJECT -o OUTPUT_CONFIG [OPTIONS]
```

**Record Command Arguments:**
- `PROJECT_NAME`: Name for the project archive
- `-c, --config`: Path to configuration file (required)
- `-m, --mode`: Mode 1 (broad) or 2 (targeted) - default: 1
- `-o, --output`: Output directory (default: output)
- `-v, --verbose`: Enable verbose logging

**Generate-Config Command Arguments:**
- `BEFORE_PROJECT`: Path to before project tar file (Mode 1)
- `AFTER_PROJECT`: Path to after project tar file (Mode 1)
- `-o, --output`: Output path for generated config file (required)
- `-v, --verbose`: Enable verbose logging

**Examples:**

```bash
# Mode 1: Broad fingerprinting
python src/main.py record before_install -c config/mode1.yaml -m 1 -o /tmp/output

# Generate targeted config from Mode 1 comparison
python src/main.py generate-config before_install.tar.gz after_install.tar.gz -o config/targeted.yaml

# Mode 2: Targeted analysis with archiving
python src/main.py record before_detailed -c config/targeted.yaml -m 2 -o /tmp/output
```

### Convenience Script (run.sh)

The `run.sh` script provides a simplified interface for running systemRecord with Docker. It automatically handles Docker build, volume mounting, and user permissions.

**Basic usage:**
```bash
# Record system state
./run.sh record PROJECT_NAME -c CONFIG_FILE [OPTIONS]

# Generate Mode 2 configuration
./run.sh generate-config BEFORE_PROJECT AFTER_PROJECT -o OUTPUT_CONFIG [OPTIONS]
```

**Examples:**
```bash
# Mode 1: Broad fingerprinting
./run.sh record before_install -c config/mode1.yaml -m 1

# Mode 2: Targeted analysis
./run.sh record detailed_scan -c config/targeted.yaml -m 2

# Generate config from comparison
./run.sh generate-config output/before_install.tar.gz output/after_install.tar.gz -o config/targeted.yaml
```

The script automatically:
- Builds the Docker container if needed
- Mounts the root filesystem as read-only
- Mounts config and output directories
- Sets proper user permissions
- Passes all arguments to the systemRecord application

### Docker Usage

```bash
# Method 1: Run as current user (recommended)
docker run --user $(id -u):$(id -g) \
    -v /:/system:ro \
    -v $(pwd)/config:/config:ro \
    -v $(pwd)/output:/output \
    systemrecord PROJECT_NAME -c /config/default.yaml -o /output

# Method 2: Create output directory with proper permissions first
mkdir -p $(pwd)/output
sudo chown 1000:1000 $(pwd)/output
docker run -v /:/system:ro -v $(pwd)/config:/config:ro -v $(pwd)/output:/output \
    systemrecord PROJECT_NAME -c /config/default.yaml -o /output

# Method 3: Run as root (less secure but works)
docker run --user root \
    -v /:/system:ro \
    -v $(pwd)/config:/config:ro \
    -v $(pwd)/output:/output \
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

### Two-Phase Analysis Workflow

**Phase 1: Broad Change Detection (Mode 1)**

1. **Before changes:**
   ```bash
   python src/main.py record before_install -c config/mode1.yaml -m 1
   ```

2. **After changes:**
   ```bash
   python src/main.py record after_install -c config/mode1.yaml -m 1
   ```

3. **Generate targeted configuration:**
   ```bash
   python src/main.py generate-config before_install.tar.gz after_install.tar.gz -o config/targeted.yaml
   ```

**Phase 2: Detailed Analysis (Mode 2)**

4. **Before changes (reset system to original state):**
   ```bash
   python src/main.py record before_detailed -c config/targeted.yaml -m 2
   ```

5. **After changes (repeat the same changes):**
   ```bash
   python src/main.py record after_detailed -c config/targeted.yaml -m 2
   ```

6. **Compare with systemDiff tool** for detailed file content analysis

### Single-Phase Workflows

**Mode 1 Only - Change Identification:**
```bash
# Before
python src/main.py record baseline -c config/mode1.yaml -m 1

# After changes  
python src/main.py record modified -c config/mode1.yaml -m 1

# Compare in systemDiff to see what files changed
```

**Mode 2 Only - Detailed Monitoring:**
```bash
# Use pre-configured targeted config
python src/main.py record app_before -c config/app_specific.yaml -m 2
python src/main.py record app_after -c config/app_specific.yaml -m 2
```

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

2. **Docker Permission Denied on Output Directory**
   ```bash
   # Error: Permission denied: '/output/systemrecord.log'
   # Solution: Run with current user permissions
   docker run --user $(id -u):$(id -g) \
       -v /:/system:ro \
       -v $(pwd)/config:/config:ro \
       -v $(pwd)/output:/output \
       systemrecord PROJECT_NAME -c /config/default.yaml -o /output
   
   # Alternative: Create output directory with proper ownership
   mkdir -p output
   sudo chown 1000:1000 output
   ```

3. **Large Archives**
   - Adjust `max_file_size` setting
   - Refine `archive.patterns` to be more selective

4. **Memory Issues**
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
