# Claude Code Project Index - Enhanced Fork

This is an enhanced fork of Eric Buess's claude-code-project-index with enterprise-grade safety features.

## Enhanced Features

This fork adds comprehensive backup management and safety features:
- Automatic backup rotation (configurable, default: 10 backups)
- Comprehensive change logging with file-level detail tracking
- Smart significance detection for automated vs manual approval
- Professional audit trails for debugging and compliance
- Atomic operations with rollback capability

## Quick Commands

### Enhanced Project Index Commands
```bash
# Standard index creation (same as original)
/index

# View backup history and change logs
python3 ~/.claude-code-project-index/scripts/project_index.py --show-backup-log

# Configure backup retention
python3 ~/.claude-code-project-index/scripts/project_index.py --max-backups 15
```

## Usage Philosophy

This enhanced fork follows Eric's "fork and customize" philosophy:
- Maintains full compatibility with the original
- Adds enterprise-grade safety without changing core functionality
- Provides professional logging and audit capabilities

Use this enhanced version when you need data safety, change visibility, audit trails, and professional logging for enterprise workflows.
