#!/usr/bin/env python3
"""
Project Index for Claude Code
Provides spatial-architectural awareness to prevent code duplication and misplacement.

Features:
- Directory tree structure visualization
- Markdown documentation mapping with section headers
- Directory purpose inference
- Full function and class signatures with type annotations
- Multi-language support (parsed vs listed)

Usage: python project_index.py
Output: PROJECT_INDEX.json
"""

__version__ = "0.2.0-safe-backups"

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Import shared utilities
from index_utils import (
    IGNORE_DIRS, PARSEABLE_LANGUAGES, CODE_EXTENSIONS, MARKDOWN_EXTENSIONS,
    DIRECTORY_PURPOSES, extract_python_signatures, extract_javascript_signatures,
    extract_shell_signatures, extract_markdown_structure, infer_file_purpose, 
    infer_directory_purpose, get_language_name, should_index_file
)

# Limits to keep it fast and simple
MAX_FILES = 10000
MAX_INDEX_SIZE = 1024 * 1024  # 1MB
MAX_TREE_DEPTH = 5


def generate_tree_structure(root_path: Path, max_depth: int = MAX_TREE_DEPTH) -> List[str]:
    """Generate a compact ASCII tree representation of the directory structure."""
    tree_lines = []
    
    def should_include_dir(path: Path) -> bool:
        """Check if directory should be included in tree."""
        return (
            path.name not in IGNORE_DIRS and
            not path.name.startswith('.') and
            path.is_dir()
        )
    
    def add_tree_level(path: Path, prefix: str = "", depth: int = 0):
        """Recursively build tree structure."""
        if depth > max_depth:
            if any(should_include_dir(p) for p in path.iterdir() if p.is_dir()):
                tree_lines.append(prefix + "└── ...")
            return
        
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return
        
        # Filter items
        dirs = [item for item in items if should_include_dir(item)]
        
        # Important files to show in tree
        important_files = [
            item for item in items 
            if item.is_file() and (
                item.name in ['README.md', 'package.json', 'requirements.txt', 
                             'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle',
                             'setup.py', 'pyproject.toml', 'Makefile']
            )
        ]
        
        all_items = dirs + important_files
        
        for i, item in enumerate(all_items):
            is_last = i == len(all_items) - 1
            current_prefix = "└── " if is_last else "├── "
            
            name = item.name
            if item.is_dir():
                name += "/"
                # Add file count for directories
                try:
                    file_count = sum(1 for f in item.rglob('*') if f.is_file() and f.suffix in CODE_EXTENSIONS)
                    if file_count > 0:
                        name += f" ({file_count} files)"
                except:
                    pass
            
            tree_lines.append(prefix + current_prefix + name)
            
            if item.is_dir():
                next_prefix = prefix + ("    " if is_last else "│   ")
                add_tree_level(item, next_prefix, depth + 1)
    
    # Start with root
    tree_lines.append(".")
    add_tree_level(root_path, "")
    return tree_lines


# These functions are now imported from index_utils


def build_index(root_dir: str) -> Tuple[Dict, int]:
    """Build the enhanced index with architectural awareness."""
    root = Path(root_dir)
    index = {
        'indexed_at': datetime.now().isoformat(),
        'root': str(root),
        'project_structure': {
            'type': 'tree',
            'root': '.',
            'tree': []
        },
        'documentation_map': {},
        'directory_purposes': {},
        'stats': {
            'total_files': 0,
            'total_directories': 0,
            'fully_parsed': {},
            'listed_only': {},
            'markdown_files': 0
        },
        'files': {},
        'dependency_graph': {}
    }
    
    # Generate directory tree
    print("📊 Building directory tree...")
    index['project_structure']['tree'] = generate_tree_structure(root)
    
    file_count = 0
    dir_count = 0
    skipped_count = 0
    directory_files = {}  # Track files per directory
    
    # Walk the directory tree
    print("🔍 Indexing files...")
    for file_path in root.rglob('*'):
        if file_count >= MAX_FILES:
            print(f"⚠️  Stopping at {MAX_FILES} files (project too large)")
            break
            
        if file_path.is_dir():
            # Track directories
            if not any(part in IGNORE_DIRS for part in file_path.parts):
                dir_count += 1
                directory_files[file_path] = []
            continue
            
        if not file_path.is_file():
            continue
            
        if not should_index_file(file_path, root):
            skipped_count += 1
            continue
        
        # Track files in their directories
        parent_dir = file_path.parent
        if parent_dir in directory_files:
            directory_files[parent_dir].append(file_path.name)
        
        # Get relative path and language
        rel_path = file_path.relative_to(root)
        
        # Handle markdown files specially
        if file_path.suffix in MARKDOWN_EXTENSIONS:
            doc_structure = extract_markdown_structure(file_path)
            if doc_structure['sections'] or doc_structure['architecture_hints']:
                index['documentation_map'][str(rel_path)] = doc_structure
                index['stats']['markdown_files'] += 1
            continue
        
        # Handle code files
        language = get_language_name(file_path.suffix)
        
        # Base info for all files
        file_info = {
            'language': language,
            'parsed': False
        }
        
        # Add file purpose if we can infer it
        file_purpose = infer_file_purpose(file_path)
        if file_purpose:
            file_info['purpose'] = file_purpose
        
        # Try to parse if we support this language
        if file_path.suffix in PARSEABLE_LANGUAGES:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                
                # Extract based on language
                if file_path.suffix == '.py':
                    extracted = extract_python_signatures(content)
                elif file_path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                    extracted = extract_javascript_signatures(content)
                elif file_path.suffix in {'.sh', '.bash'}:
                    extracted = extract_shell_signatures(content)
                else:
                    extracted = {'functions': {}, 'classes': {}}
                
                # Only add if we found something
                if extracted['functions'] or extracted['classes']:
                    file_info.update(extracted)
                    file_info['parsed'] = True
                    
                # Update stats
                lang_key = PARSEABLE_LANGUAGES[file_path.suffix]
                index['stats']['fully_parsed'][lang_key] = \
                    index['stats']['fully_parsed'].get(lang_key, 0) + 1
                    
            except Exception as e:
                # Parse error - just list the file
                index['stats']['listed_only'][language] = \
                    index['stats']['listed_only'].get(language, 0) + 1
        else:
            # Language not supported for parsing
            index['stats']['listed_only'][language] = \
                index['stats']['listed_only'].get(language, 0) + 1
        
        # Add to index
        index['files'][str(rel_path)] = file_info
        file_count += 1
        
        # Progress indicator every 100 files
        if file_count % 100 == 0:
            print(f"  Indexed {file_count} files...")
    
    # Infer directory purposes
    print("🏗️  Analyzing directory purposes...")
    for dir_path, files in directory_files.items():
        if files:  # Only process directories with files
            purpose = infer_directory_purpose(dir_path, files)
            if purpose:
                rel_dir = str(dir_path.relative_to(root))
                if rel_dir != '.':
                    index['directory_purposes'][rel_dir] = purpose
    
    index['stats']['total_files'] = file_count
    index['stats']['total_directories'] = dir_count
    
    # Build dependency graph
    print("🔗 Building dependency graph...")
    dependency_graph = {}
    
    for file_path, file_info in index['files'].items():
        if file_info.get('imports'):
            # Normalize imports to resolve relative paths
            file_dir = Path(file_path).parent
            dependencies = []
            
            for imp in file_info['imports']:
                # Handle relative imports
                if imp.startswith('.'):
                    # Resolve relative import
                    if imp.startswith('./'):
                        # Same directory
                        resolved = str(file_dir / imp[2:])
                    elif imp.startswith('../'):
                        # Parent directory
                        parts = imp.split('/')
                        up_levels = len([p for p in parts if p == '..'])
                        target_dir = file_dir
                        for _ in range(up_levels):
                            target_dir = target_dir.parent
                        remaining = '/'.join(p for p in parts if p != '..')
                        resolved = str(target_dir / remaining) if remaining else str(target_dir)
                    else:
                        # Module import like from . import X
                        resolved = str(file_dir)
                    
                    # Try to find actual file
                    for ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '']:
                        potential_file = resolved + ext
                        if potential_file in index['files'] or potential_file.replace('\\', '/') in index['files']:
                            dependencies.append(potential_file.replace('\\', '/'))
                            break
                else:
                    # External dependency or absolute import
                    dependencies.append(imp)
            
            if dependencies:
                dependency_graph[file_path] = dependencies
    
    # Only add if not empty
    if dependency_graph:
        index['dependency_graph'] = dependency_graph
    
    # Build bidirectional call graph
    print("📞 Building call graph...")
    call_graph = {}
    called_by_graph = {}
    
    # Process all files to build call relationships
    for file_path, file_info in index['files'].items():
        if not isinstance(file_info, dict):
            continue
            
        # Process functions in this file
        if 'functions' in file_info:
            for func_name, func_data in file_info['functions'].items():
                if isinstance(func_data, dict) and 'calls' in func_data:
                    # Track what this function calls
                    full_func_name = f"{file_path}:{func_name}"
                    call_graph[full_func_name] = func_data['calls']
                    
                    # Build reverse index (called_by)
                    for called in func_data['calls']:
                        if called not in called_by_graph:
                            called_by_graph[called] = []
                        called_by_graph[called].append(func_name)
        
        # Process methods in classes
        if 'classes' in file_info:
            for class_name, class_data in file_info['classes'].items():
                if isinstance(class_data, dict) and 'methods' in class_data:
                    for method_name, method_data in class_data['methods'].items():
                        if isinstance(method_data, dict) and 'calls' in method_data:
                            # Track what this method calls
                            full_method_name = f"{file_path}:{class_name}.{method_name}"
                            call_graph[full_method_name] = method_data['calls']
                            
                            # Build reverse index
                            for called in method_data['calls']:
                                if called not in called_by_graph:
                                    called_by_graph[called] = []
                                called_by_graph[called].append(f"{class_name}.{method_name}")
    
    # Add called_by information back to functions
    for file_path, file_info in index['files'].items():
        if not isinstance(file_info, dict):
            continue
            
        if 'functions' in file_info:
            for func_name, func_data in file_info['functions'].items():
                if func_name in called_by_graph:
                    if isinstance(func_data, dict):
                        func_data['called_by'] = called_by_graph[func_name]
                    else:
                        # Convert string signature to dict
                        index['files'][file_path]['functions'][func_name] = {
                            'signature': func_data,
                            'called_by': called_by_graph[func_name]
                        }
        
        if 'classes' in file_info:
            for class_name, class_data in file_info['classes'].items():
                if isinstance(class_data, dict) and 'methods' in class_data:
                    for method_name, method_data in class_data['methods'].items():
                        full_name = f"{class_name}.{method_name}"
                        if method_name in called_by_graph or full_name in called_by_graph:
                            callers = called_by_graph.get(method_name, []) + called_by_graph.get(full_name, [])
                            if callers:
                                if isinstance(method_data, dict):
                                    method_data['called_by'] = list(set(callers))
                                else:
                                    # Convert string signature to dict
                                    class_data['methods'][method_name] = {
                                        'signature': method_data,
                                        'called_by': list(set(callers))
                                    }
    
    # Add staleness check
    week_old = datetime.now().timestamp() - 7 * 24 * 60 * 60
    index['staleness_check'] = week_old
    
    return index, skipped_count


# infer_file_purpose is now imported from index_utils


def compress_index_if_needed(index: Dict) -> Dict:
    """Compress index if it exceeds size limit."""
    index_json = json.dumps(index, indent=2)
    
    if len(index_json) <= MAX_INDEX_SIZE:
        return index
    
    print(f"⚠️  Index too large ({len(index_json)} bytes), compressing...")
    
    # First, reduce tree depth
    if len(index['project_structure']['tree']) > 100:
        index['project_structure']['tree'] = index['project_structure']['tree'][:100]
        index['project_structure']['tree'].append("... (truncated)")
    
    # If still too large, remove some listed-only files
    while len(json.dumps(index, indent=2)) > MAX_INDEX_SIZE and index['files']:
        # Find and remove a listed-only file
        for path, info in list(index['files'].items()):
            if not info.get('parsed', False):
                del index['files'][path]
                break
    
    return index


def print_summary(index: Dict, skipped_count: int):
    """Print a helpful summary of what was indexed."""
    stats = index['stats']
    
    # Add warning if no files were found
    if stats['total_files'] == 0:
        print("\n⚠️  WARNING: No files were indexed!")
        print("   This might mean:")
        print("   • You're in the wrong directory")
        print("   • All files are being ignored (check .gitignore)")
        print("   • The project has no supported file types")
        print(f"\n   Current directory: {os.getcwd()}")
        print("   Try running from your project root directory.")
        return
    
    print(f"\n📊 Project Analysis Complete:")
    print(f"   📁 {stats['total_directories']} directories indexed")
    print(f"   📄 {stats['total_files']} code files found")
    print(f"   📝 {stats['markdown_files']} documentation files analyzed")
    
    # Show fully parsed languages
    if stats['fully_parsed']:
        print("\n✅ Languages with full parsing:")
        for lang, count in sorted(stats['fully_parsed'].items()):
            print(f"   • {count} {lang.capitalize()} files (with signatures)")
    
    # Show listed-only languages
    if stats['listed_only']:
        print("\n📋 Languages listed only:")
        for lang, count in sorted(stats['listed_only'].items()):
            print(f"   • {count} {lang.capitalize()} files")
    
    # Show documentation insights
    if index['documentation_map']:
        print(f"\n📚 Documentation insights:")
        for doc_file, info in list(index['documentation_map'].items())[:3]:
            print(f"   • {doc_file}: {len(info['sections'])} sections")
    
    # Show directory purposes
    if index['directory_purposes']:
        print(f"\n🏗️  Directory structure:")
        for dir_path, purpose in list(index['directory_purposes'].items())[:5]:
            print(f"   • {dir_path}/: {purpose}")
    
    if skipped_count > 0:
        print(f"\n   (Skipped {skipped_count} files in ignored directories)")


def load_backup_log(backup_dir: Path) -> Dict[str, Any]:
    """Load existing backup log or create new one."""
    log_file = backup_dir / "PROJECT_INDEX_backups_log.json"
    
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load backup log: {e}, creating new one")
    
    # Create new log structure
    return {
        "log_version": "1.0",
        "created_at": datetime.now().isoformat(),
        "project_path": str(Path.cwd().absolute()),
        "description": "Backup log for PROJECT_INDEX.json - tracks changes made by /index command",
        "max_backups": 10,
        "entries": []
    }

def save_backup_log(backup_dir: Path, log_data: Dict[str, Any]):
    """Save updated backup log."""
    log_file = backup_dir / "PROJECT_INDEX_backups_log.json"
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  Could not save backup log: {e}")

def manage_backup_rotation(backup_dir: Path, max_backups: int = 10):
    """Manage backup file rotation, keeping only the most recent backups."""
    try:
        # Find all PROJECT_INDEX backup files
        backup_pattern = "PROJECT_INDEX_*.json"
        backup_files = list(backup_dir.glob(backup_pattern))
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove excess backups
        if len(backup_files) > max_backups:
            files_to_remove = backup_files[max_backups:]
            for old_backup in files_to_remove:
                try:
                    old_backup.unlink()
                    print(f"🗑️  Removed old backup: {old_backup.name}")
                except Exception as e:
                    print(f"⚠️  Could not remove {old_backup.name}: {e}")
    
    except Exception as e:
        print(f"⚠️  Backup rotation failed: {e}")

def get_file_level_changes(old_index: Optional[Dict], new_index: Dict) -> Dict[str, List[str]]:
    """Analyze file-level changes between indexes."""
    if not old_index:
        return {
            "files_added": list(new_index.get("files", {}).keys()),
            "files_removed": [],
            "files_modified": []
        }
    
    old_files = set(old_index.get("files", {}).keys())
    new_files = set(new_index.get("files", {}).keys())
    
    files_added = list(new_files - old_files)
    files_removed = list(old_files - new_files)
    files_modified = []
    
    # Check for modifications (simplified - could be enhanced with deeper analysis)
    for file_path in old_files & new_files:
        old_file = old_index["files"][file_path]
        new_file = new_index["files"][file_path]
        
        old_func_count = len(old_file.get("functions", {}))
        new_func_count = len(new_file.get("functions", {}))
        old_class_count = len(old_file.get("classes", {}))
        new_class_count = len(new_file.get("classes", {}))
        
        if old_func_count != new_func_count or old_class_count != new_class_count:
            files_modified.append(file_path)
    
    return {
        "files_added": files_added,
        "files_removed": files_removed,
        "files_modified": files_modified
    }

def log_backup_creation(log_data: Dict[str, Any], backup_info: Dict[str, Any]):
    """Add backup creation entry to log."""
    log_data["entries"].append(backup_info)
    # Keep only last 100 log entries to prevent log bloat
    if len(log_data["entries"]) > 100:
        log_data["entries"] = log_data["entries"][-100:]

def create_backup(index_path: Path, max_backups: int = 10) -> Optional[Path]:
    """Create timestamped backup with enhanced management."""
    backup_dir = Path('.claude-index-backups')
    backup_dir.mkdir(exist_ok=True)
    
    # Load existing log
    log_data = load_backup_log(backup_dir)
    
    if not index_path.exists():
        print("ℹ️  No existing PROJECT_INDEX.json to backup")
        return None
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"PROJECT_INDEX_{timestamp}.json"
    backup_path = backup_dir / backup_name
    
    try:
        # Create backup
        shutil.copy2(index_path, backup_path)
        backup_size = backup_path.stat().st_size
        
        # Create log entry (will be completed after analysis)
        backup_info = {
            "timestamp": datetime.now().isoformat(),
            "backup_filename": backup_name,
            "backup_size_bytes": backup_size,
            "previous_stats": None,  # Will be filled in later
            "new_stats": None,      # Will be filled in later
            "changes": None,        # Will be filled in later
            "file_changes": None,   # Will be filled in later
            "significance_level": "pending",
            "notes": "Backup created successfully"
        }
        
        print(f"💾 Backup created: {backup_path.name} ({backup_size:,} bytes)")
        
        # Manage rotation
        manage_backup_rotation(backup_dir, max_backups)
        
        # Store backup info for later completion (using a simple class to hold data)
        class BackupInfo:
            def __init__(self, path, info, log, dir):
                self.path = path
                self._backup_info = info
                self._log_data = log
                self._backup_dir = dir
                
        return BackupInfo(backup_path, backup_info, log_data, backup_dir)
        
    except Exception as e:
        print(f"⚠️  Backup failed: {e}")
        return None

def analyze_changes(backup_info: Optional[Any], new_index: Dict) -> Tuple[bool, Dict[str, Any]]:
    """Analyze changes between old and new index. Returns (is_significant, change_data)."""
    change_data = {
        "old_stats": {},
        "new_stats": {},
        "file_changes": {},
        "significance_level": "auto_approved",
        "notes": ""
    }
    
    # Extract the actual backup path
    old_path = None
    if backup_info and hasattr(backup_info, 'path'):
        old_path = backup_info.path
    elif backup_info:
        old_path = backup_info
    
    if not old_path or not old_path.exists():
        print("📝 Creating new PROJECT_INDEX.json (no previous version)")
        change_data["new_stats"] = new_index.get("stats", {})
        change_data["file_changes"] = get_file_level_changes(None, new_index)
        change_data["notes"] = "Initial index creation"
        return False, change_data
    
    try:
        with open(old_path, 'r', encoding='utf-8') as f:
            old_index = json.load(f)
    except Exception as e:
        print(f"⚠️  Could not read previous index: {e}")
        change_data["notes"] = f"Could not read previous index: {e}"
        return False, change_data
    
    print("\n🔍 Analyzing changes...")
    
    # Compare key statistics
    old_stats = old_index.get("stats", {})
    new_stats = new_index.get("stats", {})
    
    old_files = old_stats.get("total_files", 0)
    new_files = new_stats.get("total_files", 0)
    old_dirs = old_stats.get("total_directories", 0)
    new_dirs = new_stats.get("total_directories", 0)
    
    file_change = new_files - old_files
    dir_change = new_dirs - old_dirs
    
    print(f"📊 Statistics Comparison:")
    print(f"   Files: {old_files} → {new_files} ({file_change:+d})")
    print(f"   Directories: {old_dirs} → {new_dirs} ({dir_change:+d})")
    
    # Get file-level changes
    file_changes = get_file_level_changes(old_index, new_index)
    
    # Show file-level changes if any
    if file_changes["files_added"]:
        print(f"   📄 Files added: {len(file_changes['files_added'])}")
        if len(file_changes["files_added"]) <= 5:
            for file in file_changes["files_added"]:
                print(f"      + {file}")
        else:
            for file in file_changes["files_added"][:3]:
                print(f"      + {file}")
            print(f"      ... and {len(file_changes['files_added']) - 3} more")
    
    if file_changes["files_removed"]:
        print(f"   📄 Files removed: {len(file_changes['files_removed'])}")
        if len(file_changes["files_removed"]) <= 5:
            for file in file_changes["files_removed"]:
                print(f"      - {file}")
        else:
            for file in file_changes["files_removed"][:3]:
                print(f"      - {file}")
            print(f"      ... and {len(file_changes['files_removed']) - 3} more")
    
    if file_changes["files_modified"]:
        print(f"   📄 Files modified: {len(file_changes['files_modified'])}")
        if len(file_changes["files_modified"]) <= 5:
            for file in file_changes["files_modified"]:
                print(f"      ~ {file}")
        else:
            for file in file_changes["files_modified"][:3]:
                print(f"      ~ {file}")
            print(f"      ... and {len(file_changes['files_modified']) - 3} more")
    
    # Check for significant changes
    significant_changes = False
    significance_reasons = []
    
    if abs(file_change) > 10:
        significant_changes = True
        significance_reasons.append(f"Large file count change: {abs(file_change)} files")
        print(f"⚠️  Large file count change: {abs(file_change)} files")
    
    if abs(dir_change) > 5:
        significant_changes = True
        significance_reasons.append(f"Large directory count change: {abs(dir_change)} directories")
        print(f"⚠️  Large directory count change: {abs(dir_change)} directories")
    
    if len(file_changes["files_removed"]) > 5:
        significant_changes = True
        significance_reasons.append(f"Many files removed: {len(file_changes['files_removed'])}")
        print(f"⚠️  Many files removed: {len(file_changes['files_removed'])}")
    
    # Check for parsing ratio changes
    old_parsed = sum(old_stats.get("fully_parsed", {}).values())
    new_parsed = sum(new_stats.get("fully_parsed", {}).values())
    
    if old_files > 0 and new_files > 0:
        old_ratio = old_parsed / old_files
        new_ratio = new_parsed / new_files
        ratio_change = abs(new_ratio - old_ratio)
        
        if ratio_change > 0.2:  # 20% change in parsing ratio
            significant_changes = True
            significance_reasons.append(f"Parsing ratio changed: {old_ratio:.1%} → {new_ratio:.1%}")
            print(f"⚠️  Parsing ratio changed significantly: {old_ratio:.1%} → {new_ratio:.1%}")
    
    # Populate change data
    change_data["old_stats"] = old_stats
    change_data["new_stats"] = new_stats
    change_data["file_changes"] = file_changes
    
    if significant_changes:
        change_data["significance_level"] = "requires_confirmation"
        change_data["notes"] = "; ".join(significance_reasons)
    else:
        change_data["significance_level"] = "auto_approved"
        change_data["notes"] = f"Routine update: {file_change:+d} files, {dir_change:+d} directories"
        print("✅ Changes look reasonable")
    
    return significant_changes, change_data

def confirm_update(significant_changes: bool) -> bool:
    """Ask for user confirmation if changes are significant."""
    if not significant_changes:
        print("✅ Auto-approving safe changes")
        return True
    
    print(f"\n🤔 Significant changes detected")
    print("Review the analysis above.")
    
    try:
        response = input("Proceed with index update? [y/N]: ").lower().strip()
        return response in ['y', 'yes']
    except (EOFError, KeyboardInterrupt):
        print("\n🚫 Operation cancelled")
        return False

def safe_save_index(index: Dict, output_path: Path, backup_path: Optional[Path]) -> bool:
    """Safely save the index with rollback capability."""
    try:
        # Write to temporary file first
        temp_path = output_path.with_suffix('.json.tmp')
        temp_path.write_text(json.dumps(index, indent=2), encoding='utf-8')
        
        # Atomic replace
        temp_path.replace(output_path)
        print(f"✅ Index saved successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save index: {e}")
        
        # Attempt rollback
        if backup_path and backup_path.exists():
            try:
                import shutil
                shutil.copy2(backup_path, output_path)
                print("🔄 Restored previous version from backup")
            except Exception as restore_error:
                print(f"❌ Rollback also failed: {restore_error}")
        
        return False

def complete_backup_log(backup_info: Optional[Any], change_data: Dict[str, Any], success: bool):
    """Complete the backup log entry with analysis results."""
    if not backup_info or not hasattr(backup_info, '_backup_info'):
        return
    
    try:
        backup_data = backup_info._backup_info
        log_data = backup_info._log_data
        backup_dir = backup_info._backup_dir
        
        # Complete the backup info
        backup_data.update({
            "previous_stats": change_data.get("old_stats", {}),
            "new_stats": change_data.get("new_stats", {}),
            "changes": {
                "files_added": len(change_data.get("file_changes", {}).get("files_added", [])),
                "files_removed": len(change_data.get("file_changes", {}).get("files_removed", [])),
                "files_modified": len(change_data.get("file_changes", {}).get("files_modified", [])),
                "directories_added": change_data.get("new_stats", {}).get("total_directories", 0) - 
                                   change_data.get("old_stats", {}).get("total_directories", 0)
            },
            "file_changes": change_data.get("file_changes", {}),
            "significance_level": change_data.get("significance_level", "unknown"),
            "notes": change_data.get("notes", "") + (f" | Success: {success}" if not success else ""),
            "operation_success": success
        })
        
        # Add to log and save
        log_backup_creation(log_data, backup_data)
        save_backup_log(backup_dir, log_data)
        
    except Exception as e:
        print(f"⚠️  Could not complete backup log: {e}")

def main():
    """Run the enhanced indexer with comprehensive backup management."""
    import sys
    
    # Parse command line arguments
    max_backups = 10
    show_log = False
    cleanup_only = False
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--max-backups' and i + 1 < len(sys.argv):
            try:
                max_backups = int(sys.argv[i + 1])
                if max_backups < 1:
                    max_backups = 10
                i += 2
            except ValueError:
                print("⚠️  Invalid --max-backups value, using default: 10")
                i += 2
        elif sys.argv[i] == '--show-backup-log':
            show_log = True
            i += 1
        elif sys.argv[i] == '--cleanup-backups':
            cleanup_only = True
            i += 1
        elif sys.argv[i] == '--version':
            print(f"Safe PROJECT_INDEX v{__version__}")
            return
        else:
            i += 1
    
    print(f"🛡️  Safe Project Index Generator v{__version__}")
    print("==================================================")
    
    # Handle special commands
    if show_log:
        backup_dir = Path('.claude-index-backups')
        if backup_dir.exists():
            log_data = load_backup_log(backup_dir)
            print(f"\n📋 Backup Log for: {log_data.get('project_path', 'Unknown')}")
            print(f"📊 Total entries: {len(log_data.get('entries', []))}")
            print(f"📁 Max backups: {log_data.get('max_backups', 10)}")
            
            entries = log_data.get('entries', [])
            if entries:
                print(f"\n📄 Recent entries:")
                for entry in entries[-5:]:  # Show last 5
                    print(f"   {entry.get('timestamp', 'Unknown')} - {entry.get('backup_filename', 'Unknown')}")
                    print(f"      {entry.get('notes', 'No notes')}")
            else:
                print("\n📭 No backup entries found")
        else:
            print("📭 No backup directory found")
        return
    
    if cleanup_only:
        backup_dir = Path('.claude-index-backups')
        if backup_dir.exists():
            print(f"🗑️  Cleaning up backups (keeping {max_backups} most recent)...")
            manage_backup_rotation(backup_dir, max_backups)
            print("✅ Cleanup complete")
        else:
            print("📭 No backup directory found")
        return
    
    print("🚀 Building Project Index...")
    print("   Analyzing project structure and documentation...")
    
    output_path = Path('PROJECT_INDEX.json')
    backup_path = None
    change_data = {}
    
    try:
        # Step 1: Create backup with rotation
        backup_path = create_backup(output_path, max_backups)
        
        # Step 2: Build new index
        try:
            index, skipped_count = build_index('.')
            index = compress_index_if_needed(index)
        except Exception as e:
            print(f"❌ Failed to build index: {e}")
            complete_backup_log(backup_path, {}, False)
            return
        
        # Step 3: Analyze changes
        significant_changes, change_data = analyze_changes(backup_path, index)
        
        # Step 4: Get confirmation if needed
        if not confirm_update(significant_changes):
            print("🚫 Index update cancelled")
            complete_backup_log(backup_path, change_data, False)
            return
        
        # Step 5: Save safely
        if not safe_save_index(index, output_path, backup_path):
            complete_backup_log(backup_path, change_data, False)
            return
        
        # Step 6: Complete logging
        complete_backup_log(backup_path, change_data, True)
        
        # Step 7: Print summary
        print_summary(index, skipped_count)
        
        print(f"\n💾 Saved to: {output_path}")
        if backup_path:
            backup_name = backup_path.path.name if hasattr(backup_path, 'path') else str(backup_path)
            print(f"💾 Backup stored: {backup_name}")
            print(f"📋 Log updated: .claude-index-backups/PROJECT_INDEX_backups_log.json")
        
        print("\n✨ Claude now has architectural awareness of your project!")
        print("   • Knows WHERE to place new code")
        print("   • Understands project structure")
        print("   • Can navigate documentation")
        print("\n📌 Benefits:")
        print("   • Prevents code duplication")
        print("   • Ensures proper file placement")
        print("   • Maintains architectural consistency")
        print("\n🛡️  Enhanced safety features:")
        print(f"   • Automatic backup rotation (max {max_backups} backups)")
        print("   • Comprehensive change logging with file-level details")
        print("   • Smart significance detection and confirmation")
        print("   • Atomic operations with rollback capability")
        print(f"\n💡 Use --show-backup-log to view change history")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        complete_backup_log(backup_path, change_data, False)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--version':
        print(f"PROJECT_INDEX v{__version__}")
        sys.exit(0)
    main()