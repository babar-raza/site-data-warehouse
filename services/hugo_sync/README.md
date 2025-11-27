# Hugo Content Sync Service

Tracks Hugo CMS content changes and correlates them with SEO performance metrics from Google Search Console.

## Features

- **Content Scanning**: Automatically scans Hugo content directory for markdown and HTML files
- **Change Detection**: Uses SHA256 hashing to detect content changes
- **Git Integration**: Leverages git history for accurate modification timestamps
- **Performance Correlation**: Correlates content changes with GSC metrics (clicks, impressions, position)
- **Word Count Tracking**: Monitors content length changes over time
- **Soft Deletes**: Tracks deleted pages without removing historical data

## Quick Start

### 1. Setup Database Schema

```bash
psql $WAREHOUSE_DSN -f sql/29_hugo_content_schema.sql
```

### 2. Basic Usage

```python
from services.hugo_sync import HugoContentTracker

# Initialize tracker
tracker = HugoContentTracker(
    hugo_path='/path/to/hugo/site',
    db_dsn='postgresql://user:pass@localhost/warehouse',
    property_name='https://example.com'
)

# Sync all content
stats = tracker.sync()
print(f"Created: {stats['created']}, Updated: {stats['updated']}")
```

### 3. Environment Variables

Set these in your `.env` file:

```bash
WAREHOUSE_DSN=postgresql://user:pass@localhost/warehouse
GSC_PROPERTY=https://example.com
```

## API Reference

### `HugoContentTracker`

#### `__init__(hugo_path, db_dsn=None, property_name=None)`

Initialize the content tracker.

**Parameters:**
- `hugo_path` (str): Path to Hugo site root (contains 'content' directory)
- `db_dsn` (str, optional): Database connection string (defaults to `WAREHOUSE_DSN`)
- `property_name` (str, optional): GSC property identifier (defaults to `GSC_PROPERTY`)

#### `sync() -> Dict`

Scan content directory and sync all changes to database.

**Returns:** Dictionary with sync statistics:
```python
{
    'created': 5,      # New pages
    'updated': 3,      # Modified pages
    'unchanged': 12,   # No changes
    'deleted': 1,      # Removed pages
    'errors': 0,       # Processing errors
    'synced_at': '2024-01-20T10:30:00'
}
```

#### `track_change(file_path, change_type)`

Track a specific content change.

**Parameters:**
- `file_path` (str): Relative path to changed file
- `change_type` (str): Type of change ('created', 'updated', 'deleted')

**Example:**
```python
tracker.track_change('blog/new-post.md', 'created')
```

#### `get_content_history(page_path) -> List[Dict]`

Get change history for a specific page.

**Parameters:**
- `page_path` (str): URL path of the page (e.g., '/blog/article')

**Returns:** List of changes ordered by date (newest first):
```python
[
    {
        'change_type': 'updated',
        'old_hash': 'abc123',
        'new_hash': 'def456',
        'changed_at': datetime(2024, 1, 20),
        'word_count_change': 150,
        'title': 'Article Title'
    },
    ...
]
```

#### `correlate_with_performance(page_path, days_before=7, days_after=30) -> Dict`

Analyze how content changes affected search performance.

**Parameters:**
- `page_path` (str): URL path of the page
- `days_before` (int): Days before change to analyze (default: 7)
- `days_after` (int): Days after change to analyze (default: 30)

**Returns:** Performance correlation analysis:
```python
{
    'page_path': '/blog/article',
    'overall_trend': 'improving',  # or 'declining', 'stable', 'no_changes'
    'changes': [
        {
            'date': '2024-01-15',
            'change_type': 'updated',
            'word_count_change': 200,
            'performance_before': {
                'avg_clicks': 10.0,
                'avg_impressions': 100.0,
                'avg_position': 15.0
            },
            'performance_after': {
                'avg_clicks': 15.0,
                'avg_impressions': 150.0,
                'avg_position': 12.0
            },
            'clicks_change_pct': 50.0,
            'position_change': 3.0
        }
    ]
}
```

#### `get_recent_changes(days=7, limit=50) -> List[Dict]`

Get recent content changes across all pages.

**Parameters:**
- `days` (int): Number of days to look back (default: 7)
- `limit` (int): Maximum number of changes (default: 50)

**Returns:** List of recent changes:
```python
[
    {
        'page_path': '/blog/article1',
        'title': 'Article Title',
        'change_type': 'updated',
        'changed_at': datetime(2024, 1, 20),
        'word_count_change': 75
    },
    ...
]
```

## Database Schema

### Tables

#### `content.hugo_pages`

Stores current state of all Hugo content pages.

**Columns:**
- `id`: Primary key
- `property`: GSC property identifier
- `page_path`: URL path (e.g., '/blog/article')
- `title`: Page title from front matter
- `content_hash`: SHA256 hash (first 16 chars)
- `word_count`: Word count excluding front matter
- `last_modified`: Last modification timestamp
- `created_at`: First sync timestamp
- `synced_at`: Last sync timestamp
- `deleted_at`: Soft delete timestamp (NULL if active)

#### `content.hugo_changes`

Audit log of all content changes.

**Columns:**
- `id`: Primary key
- `page_id`: Foreign key to `hugo_pages`
- `change_type`: 'created', 'updated', or 'deleted'
- `old_hash`: Content hash before change
- `new_hash`: Content hash after change
- `word_count_change`: Delta in word count
- `changed_at`: Change timestamp

### Views

#### `content.recent_hugo_changes`

Recent changes (last 30 days) with page details.

#### `content.content_performance_correlation`

Correlates content changes with GSC performance metrics.

#### `content.active_content_summary`

Summary statistics for active content by property.

### Functions

#### `content.get_content_impact_score(page_path, property)`

Calculates impact score for content changes.

**Returns:**
- `impact_score`: Weighted score (clicks 70%, position 30%)
- `impact_level`: 'high_positive', 'moderate_positive', 'neutral', etc.
- `total_changes`: Total number of changes
- `positive_changes`: Changes with positive impact
- `avg_clicks_change`: Average percentage change in clicks
- `avg_position_change`: Average position improvement

#### `content.get_pages_needing_update(property, days_since_update=90, performance_threshold=-10.0)`

Identifies pages that haven't been updated recently and have declining performance.

**Parameters:**
- `property`: GSC property identifier
- `days_since_update`: Minimum days since last update (default: 90)
- `performance_threshold`: Performance decline threshold (default: -10.0%)

## Usage Examples

### Monitor Content Impact

```python
from services.hugo_sync import HugoContentTracker

tracker = HugoContentTracker('/path/to/hugo')

# Sync all content
tracker.sync()

# Check impact of recent changes
changes = tracker.get_recent_changes(days=30)
for change in changes:
    if change['change_type'] == 'updated':
        correlation = tracker.correlate_with_performance(
            change['page_path']
        )
        if correlation['overall_trend'] == 'improving':
            print(f"✓ {change['page_path']}: Performance improved!")
```

### Track Single File Change

```python
from services.hugo_sync import HugoContentTracker

tracker = HugoContentTracker('/path/to/hugo')

# Track a specific change (e.g., from file watcher)
tracker.track_change('blog/new-article.md', 'created')
```

### Analyze Page History

```python
from services.hugo_sync import HugoContentTracker

tracker = HugoContentTracker('/path/to/hugo')

# Get full history for a page
history = tracker.get_content_history('/blog/seo-guide')

print(f"Total changes: {len(history)}")
for change in history:
    print(f"{change['changed_at']}: {change['change_type']}")
    print(f"  Word count change: {change['word_count_change']}")
```

### Find Pages Needing Updates

```python
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(os.getenv('WAREHOUSE_DSN'))
cursor = conn.cursor(cursor_factory=RealDictCursor)

cursor.execute("""
    SELECT * FROM content.get_pages_needing_update(
        %s,  -- property
        90,  -- days_since_update
        -10.0  -- performance_threshold
    )
    ORDER BY performance_trend ASC
    LIMIT 10
""", (os.getenv('GSC_PROPERTY'),))

pages = cursor.fetchall()
for page in pages:
    print(f"{page['page_path']}: {page['days_since_update']} days old")
    print(f"  Performance trend: {page['performance_trend']}%")
```

## Integration with File Watchers

Use with watchdog or similar tools to track real-time changes:

```python
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from services.hugo_sync import HugoContentTracker

class HugoChangeHandler(FileSystemEventHandler):
    def __init__(self, tracker):
        self.tracker = tracker

    def on_created(self, event):
        if event.src_path.endswith(('.md', '.markdown', '.html')):
            rel_path = os.path.relpath(event.src_path, tracker.content_path)
            tracker.track_change(rel_path, 'created')

    def on_modified(self, event):
        if event.src_path.endswith(('.md', '.markdown', '.html')):
            rel_path = os.path.relpath(event.src_path, tracker.content_path)
            tracker.track_change(rel_path, 'updated')

    def on_deleted(self, event):
        if event.src_path.endswith(('.md', '.markdown', '.html')):
            rel_path = os.path.relpath(event.src_path, tracker.content_path)
            tracker.track_change(rel_path, 'deleted')

# Setup watcher
tracker = HugoContentTracker('/path/to/hugo')
handler = HugoChangeHandler(tracker)
observer = Observer()
observer.schedule(handler, str(tracker.content_path), recursive=True)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
```

## Testing

Run the test suite:

```bash
pytest tests/services/test_hugo_sync.py -v
```

## Notes

- **Git Integration**: If git is available, file modification times are sourced from git history for accuracy
- **Windows Support**: Handles both forward and backward slashes in file paths
- **Front Matter**: Supports both YAML (`---`) and TOML (`+++`) front matter formats
- **Performance**: Uses content hashing to efficiently detect changes without comparing full content
- **Soft Deletes**: Deleted pages remain in database with `deleted_at` timestamp for historical analysis

## Troubleshooting

### "Content path not found" Error

Ensure the Hugo site path contains a `content` directory:
```
/path/to/hugo/
  ├── content/
  │   ├── _index.md
  │   └── blog/
  ├── layouts/
  └── config.toml
```

### Git Timestamps Not Working

Check git is available and the Hugo directory is a git repository:
```bash
cd /path/to/hugo
git status
```

### Database Connection Issues

Verify database DSN is correct:
```python
import psycopg2
conn = psycopg2.connect(os.getenv('WAREHOUSE_DSN'))
print("Connected successfully!")
```
