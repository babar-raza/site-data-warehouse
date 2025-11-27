#!/usr/bin/env python3
"""
Execute Action CLI Tool
=======================
Command-line interface for executing content optimization actions.

Usage:
    # Execute a single action
    python scripts/execute_action.py <action_id>

    # Execute with dry-run
    python scripts/execute_action.py <action_id> --dry-run

    # Execute multiple actions
    python scripts/execute_action.py <action_id1> <action_id2> <action_id3>

    # List pending actions
    python scripts/execute_action.py --list

    # List pending actions with filters
    python scripts/execute_action.py --list --property https://blog.aspose.net --priority high

    # Check system readiness
    python scripts/execute_action.py --check

Environment Variables Required:
    WAREHOUSE_DSN: PostgreSQL connection string
    HUGO_CONTENT_PATH: Path to Hugo content directory
    HUGO_FILE_LOCALIZATION_SUBDOMAINS: Comma-separated list of file-localized subdomains
    OLLAMA_BASE_URL: Ollama API URL (default: http://localhost:11434)
    OLLAMA_MODEL: Ollama model name (default: llama3.1)
"""
import argparse
import os
import sys
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

from config.hugo_config import HugoConfig
from services.hugo_content_writer import HugoContentWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection from environment."""
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        logger.error("WAREHOUSE_DSN environment variable not set")
        sys.exit(1)
    return psycopg2.connect(dsn)


def check_system_ready() -> bool:
    """
    Check if all required components are ready.

    Returns:
        True if system is ready, False otherwise
    """
    print("\n=== System Readiness Check ===\n")
    all_ready = True

    # Check database
    print("1. Database Connection:")
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        print("   [OK] Database connected")
    except Exception as e:
        print(f"   [FAIL] {e}")
        all_ready = False

    # Check Hugo config
    print("\n2. Hugo Configuration:")
    try:
        config = HugoConfig.from_env()
        if config.is_configured():
            validation_error = config.validate_path()
            if validation_error:
                print(f"   [FAIL] {validation_error}")
                all_ready = False
            else:
                print(f"   [OK] Content path: {config.content_path}")
                print(f"   [OK] File-localized subdomains: {config.file_localization_subdomains}")
                print(f"   [OK] Default locale: {config.default_locale}")
        else:
            print("   [FAIL] HUGO_CONTENT_PATH not configured")
            all_ready = False
    except Exception as e:
        print(f"   [FAIL] {e}")
        all_ready = False

    # Check Ollama
    print("\n3. Ollama LLM Service:")
    try:
        import httpx
        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{ollama_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                print(f"   [OK] Ollama running at {ollama_url}")
                print(f"   [OK] Available models: {[m['name'] for m in models[:5]]}")
            else:
                print(f"   [WARN] Ollama returned status {response.status_code}")
    except Exception as e:
        print(f"   [WARN] Ollama not available: {e}")
        print("   [INFO] Actions will fail if they require LLM generation")

    print(f"\n{'='*40}")
    if all_ready:
        print("System is READY for action execution")
    else:
        print("System is NOT READY - fix errors above")
    print('='*40 + "\n")

    return all_ready


def list_pending_actions(
    property_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    List pending actions from the database.

    Args:
        property_filter: Filter by property URL
        priority_filter: Filter by priority (high/medium/low)
        limit: Maximum number of results

    Returns:
        List of pending actions
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    id, property, action_type, title, priority, effort,
                    estimated_impact, status, created_at, entity_id
                FROM gsc.actions
                WHERE status = 'pending'
            """
            params: List = []

            if property_filter:
                query += " AND property = %s"
                params.append(property_filter)

            if priority_filter:
                query += " AND priority = %s"
                params.append(priority_filter)

            query += """
                ORDER BY
                    CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    created_at DESC
                LIMIT %s
            """
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def print_pending_actions(actions: List[dict]) -> None:
    """Pretty print pending actions."""
    if not actions:
        print("\nNo pending actions found.\n")
        return

    print(f"\n{'='*80}")
    print(f"{'PENDING ACTIONS':^80}")
    print('='*80)

    for i, action in enumerate(actions, 1):
        print(f"\n{i}. [{action['priority'].upper()}] {action['title']}")
        print(f"   ID: {action['id']}")
        print(f"   Type: {action['action_type']}")
        print(f"   Property: {action['property']}")
        print(f"   Entity: {action.get('entity_id', 'N/A')}")
        print(f"   Effort: {action['effort']} | Impact: {action['estimated_impact']}")
        print(f"   Created: {action['created_at']}")

    print(f"\n{'='*80}")
    print(f"Total: {len(actions)} pending actions")
    print('='*80 + "\n")


def validate_action_id(action_id: str) -> bool:
    """Validate that action_id is a valid UUID."""
    try:
        UUID(action_id)
        return True
    except ValueError:
        return False


def execute_single_action(
    action_id: str,
    dry_run: bool = False
) -> dict:
    """
    Execute a single action.

    Args:
        action_id: UUID of the action to execute
        dry_run: If True, validate but don't execute

    Returns:
        Execution result dict
    """
    if not validate_action_id(action_id):
        return {
            "success": False,
            "action_id": action_id,
            "error": "Invalid action ID format (must be UUID)"
        }

    conn = get_db_connection()
    try:
        config = HugoConfig.from_env()

        if not config.is_configured():
            return {
                "success": False,
                "action_id": action_id,
                "error": "Hugo content path not configured"
            }

        validation_error = config.validate_path()
        if validation_error:
            return {
                "success": False,
                "action_id": action_id,
                "error": validation_error
            }

        if dry_run:
            # Just validate the action exists and file is resolvable
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, status, property, metadata, entity_id
                    FROM gsc.actions WHERE id = %s
                """, (action_id,))
                row = cur.fetchone()

                if not row:
                    return {
                        "success": False,
                        "action_id": action_id,
                        "error": "Action not found"
                    }

                metadata = row.get('metadata') or {}
                subdomain = config.extract_subdomain(row['property'])
                page_path = metadata.get('page_path') or row.get('entity_id', '')

                if not subdomain or not page_path:
                    return {
                        "success": False,
                        "action_id": action_id,
                        "error": "Cannot resolve file path"
                    }

                file_path = config.get_content_file_path(subdomain, page_path)
                file_exists = os.path.exists(file_path)

                return {
                    "success": file_exists,
                    "action_id": action_id,
                    "status": "validated",
                    "file_path": file_path,
                    "file_exists": file_exists,
                    "dry_run": True
                }

        # Execute the action
        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.environ.get('OLLAMA_MODEL', 'llama3.1')

        writer = HugoContentWriter(
            config=config,
            db_connection=conn,
            ollama_base_url=ollama_url,
            ollama_model=ollama_model
        )

        result = writer.execute_action(action_id)
        return result

    except Exception as e:
        logger.exception(f"Error executing action {action_id}")
        return {
            "success": False,
            "action_id": action_id,
            "error": str(e)
        }
    finally:
        conn.close()


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Execute content optimization actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'action_ids',
        nargs='*',
        help='Action ID(s) to execute'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Validate without executing'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List pending actions'
    )
    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='Check system readiness'
    )
    parser.add_argument(
        '--property', '-p',
        help='Filter by property URL (for --list)'
    )
    parser.add_argument(
        '--priority',
        choices=['high', 'medium', 'low'],
        help='Filter by priority (for --list)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum results (for --list, default: 50)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle --check
    if args.check:
        ready = check_system_ready()
        sys.exit(0 if ready else 1)

    # Handle --list
    if args.list:
        actions = list_pending_actions(
            property_filter=args.property,
            priority_filter=args.priority,
            limit=args.limit
        )
        print_pending_actions(actions)
        sys.exit(0)

    # Handle action execution
    if not args.action_ids:
        parser.print_help()
        print("\nError: No action IDs provided")
        print("\nExamples:")
        print("  python scripts/execute_action.py <action_id>")
        print("  python scripts/execute_action.py --list")
        print("  python scripts/execute_action.py --check")
        sys.exit(1)

    # Execute actions
    success_count = 0
    fail_count = 0
    results = []

    print(f"\n{'='*60}")
    if args.dry_run:
        print("DRY RUN MODE - Validating without executing")
    else:
        print("EXECUTING ACTIONS")
    print('='*60)

    for action_id in args.action_ids:
        print(f"\nProcessing: {action_id}")

        result = execute_single_action(action_id, dry_run=args.dry_run)
        results.append(result)

        if result.get('success'):
            success_count += 1
            print(f"  [SUCCESS] {result.get('file_path', 'No file path')}")
            if result.get('changes_made'):
                for change in result['changes_made']:
                    print(f"    - {change}")
        else:
            fail_count += 1
            print(f"  [FAILED] {result.get('error', 'Unknown error')}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Total: {len(args.action_ids)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print('='*60 + "\n")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
