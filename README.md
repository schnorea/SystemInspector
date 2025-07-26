# System Inspector

A comprehensive toolkit for system fingerprinting and change analysis, consisting of two main tools:

1. **systemRecord** - System fingerprinting tool that captures system state
2. **systemDiff** - Web-based comparison tool for analyzing system changes

## Overview

System Inspector helps you track and analyze system changes by creating detailed fingerprints of your system before and after modifications (such as software installations, updates, or configuration changes). This is particularly useful for:

- Software installation impact analysis
- System compliance monitoring
- Security auditing
- Change management
- Backup verification
- Development environment tracking

## Tools

### systemRecord

A command-line tool that creates comprehensive system fingerprints by:

- Scanning specified directories and files
- Generating SHA256 hashes for file integrity checking
- Collecting file metadata (permissions, ownership, timestamps)
- Archiving selected files for detailed comparison
- Packaging everything into a portable tar project file

**Key Features:**
- Configuration-driven path selection
- Selective file archiving with size limits
- Comprehensive error handling and logging
- Docker support for consistent execution
- Recursive directory scanning with pattern matching

### systemDiff

A web-based application for comparing systemRecord projects:

- Interactive project upload interface
- Side-by-side system state comparison
- File-level diff visualization
- Change statistics and analytics
- Export capabilities (JSON, CSV)
- Modern responsive web interface

**Key Features:**
- Drag-and-drop project upload
- Real-time comparison results
- Detailed file diff viewer
- Change categorization (new, modified, deleted)
- Export and reporting capabilities

## Quick Start

### 1. Create System Fingerprints

First, use systemRecord to capture system state before making changes:

```bash
cd systemRecord
python src/main.py before_install -c config/default.yaml -o output/
```

After making your changes (installing software, etc.), capture the new state:

```bash
python src/main.py after_install -c config/default.yaml -o output/
```

### 2. Compare Changes

Start the systemDiff web application:

```bash
cd systemDiff
docker-compose up --build
```

Access the web interface at http://localhost:8080 and:

1. Upload your "before_install.tar.gz" project
2. Upload your "after_install.tar.gz" project  
3. Compare the projects to see what changed
4. Explore file differences and export results

## Installation

### Prerequisites

- Docker and Docker Compose (recommended)
- Or Python 3.11+ for local installation

### Using Docker (Recommended)

1. **systemRecord with Docker:**
   ```bash
   cd systemRecord
   docker build -t systemrecord .
   
   # Run with proper user permissions
   docker run --user $(id -u):$(id -g) \
       -v /:/system:ro \
       -v $(pwd)/config:/config:ro \
       -v $(pwd)/output:/output \
       systemrecord PROJECT_NAME -c /config/default.yaml -o /output
   ```

2. **systemDiff with Docker:**
   ```bash
   cd systemDiff
   docker-compose up --build
   ```

### Local Installation

1. **systemRecord:**
   ```bash
   cd systemRecord
   pip install -r requirements.txt
   python src/main.py --help
   ```

2. **systemDiff:**
   ```bash
   # Backend
   cd systemDiff/backend
   pip install -r requirements.txt
   python src/app.py
   
   # Frontend (serve static files)
   cd ../frontend/public
   python -m http.server 8080
   ```

## Configuration

### systemRecord Configuration

Edit `systemRecord/config/default.yaml` to customize:

- **Paths to scan**: Which directories to analyze
- **Include/exclude patterns**: File filtering rules
- **Archive settings**: What files to archive and size limits
- **Logging**: Verbosity and output options

Example minimal configuration:
```yaml
paths:
  scan:
    - "/etc"
    - "/usr/local"
  include:
    - "*.conf"
    - "*.config"
archive:
  max_file_size: 104857600  # 100MB
  patterns:
    - "*.conf"
    - "*.sh"
```

### systemDiff Configuration

systemDiff uses minimal configuration - mainly API endpoint settings in the frontend JavaScript.

## Usage Examples

### Example 1: Software Installation Analysis

```bash
# 1. Capture baseline
systemRecord/run.sh -c systemRecord/config/default.yaml before_install

# 2. Install your software
sudo apt install nginx

# 3. Capture changes  
systemRecord/run.sh -c systemRecord/config/default.yaml after_install

# 4. Compare in systemDiff web interface
cd systemDiff && docker-compose up
# Open http://localhost:8080 and upload both project files
```

### Example 2: Configuration Change Tracking

```bash
# Focus on configuration directories
cat > config/configs_only.yaml << EOF
paths:
  scan: ["/etc", "/usr/local/etc"]
  include: ["*.conf", "*.config", "*.cfg", "*.ini"]
archive:
  patterns: ["*.conf", "*.config", "*.cfg", "*.ini"]
EOF

# Before configuration changes
python systemRecord/src/main.py config_before -c config/configs_only.yaml

# After making configuration changes  
python systemRecord/src/main.py config_after -c config/configs_only.yaml

# Compare in systemDiff
```

### Example 3: System Compliance Monitoring

```bash
# Create compliance-focused configuration
cat > config/compliance.yaml << EOF
paths:
  scan: ["/etc", "/usr", "/var/log"]
  exclude: ["*/tmp/*", "*/cache/*"]
archive:
  max_file_size: 10485760  # 10MB
  patterns: ["*.conf", "*.log", "*.policy"]
EOF

# Regular compliance snapshots
python systemRecord/src/main.py compliance_$(date +%Y%m%d) -c config/compliance.yaml
```

## Project Structure

```
systemInspector/
├── SystemInspReq.txt           # Requirements document
├── systemRecord/               # Fingerprinting tool
│   ├── src/main.py            # Main application
│   ├── config/default.yaml   # Configuration
│   ├── tests/                 # Unit tests
│   ├── docs/README.md         # Documentation
│   ├── Dockerfile             # Container definition
│   └── run.sh                 # Convenience script
└── systemDiff/                # Comparison web app
    ├── backend/               # Flask API server
    │   ├── src/app.py        # Main API application
    │   ├── tests/            # Backend tests
    │   └── Dockerfile        # Backend container
    ├── frontend/             # Web interface
    │   ├── public/           # Static files
    │   └── Dockerfile        # Frontend container
    ├── docker-compose.yml    # Multi-service deployment
    └── docs/README.md        # Documentation
```

## Security Considerations

- **Sensitive Files**: Configure exclusions for passwords, keys, and secrets
- **File Permissions**: systemRecord preserves permission information
- **Archive Security**: Project archives may contain sensitive configuration files
- **Access Control**: Ensure proper access controls on output files
- **Network Security**: systemDiff runs on localhost by default

## Performance Guidelines

- **Large Filesystems**: Use inclusion/exclusion patterns to limit scope
- **Memory Usage**: Tools process files individually to minimize memory usage
- **Archive Size**: Control with `max_file_size` and `patterns` settings
- **Network**: systemDiff handles file uploads up to configured limits

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Update documentation as needed
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Testing

Run tests for both tools:

```bash
# systemRecord tests
cd systemRecord && python -m pytest tests/

# systemDiff backend tests  
cd systemDiff/backend && python -m pytest tests/
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Run systemRecord with appropriate privileges for target directories
2. **Large Archives**: Adjust `max_file_size` or refine `include` patterns
3. **Upload Failures**: Check systemDiff file size limits and network connectivity
4. **Memory Issues**: Use more selective scanning patterns

### Getting Help

1. Check individual tool documentation in their respective `docs/` directories
2. Review configuration examples
3. Enable debug logging for detailed troubleshooting
4. Check Docker logs: `docker-compose logs`

## License

[Specify your license here]

## Support

For questions, issues, or contributions:
- Review the documentation in each tool's `docs/` directory
- Check the troubleshooting sections
- Submit issues with detailed reproduction steps
- Include relevant log files and configuration when reporting problems
