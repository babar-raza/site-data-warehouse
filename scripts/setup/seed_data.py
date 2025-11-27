"""
Data Seeding Script
Seeds initial data for the SEO Intelligence Platform
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from notifications.alert_manager import AlertManager
from notifications.channels.slack_notifier import SlackNotifier
from notifications.channels.email_notifier import EmailNotifier

load_dotenv()

# Configuration
TEST_MODE = os.getenv('SEED_TEST_MODE', 'false').lower() == 'true'
PROPERTY_URL = os.getenv('GSC_PROPERTIES', 'https://yourdomain.com').split(',')[0]

class DataSeeder:
    def __init__(self, db_dsn: str = None):
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')

    async def seed_all(self):
        """Seed all initial data"""
        print("========================================")
        print("SEO Intelligence Platform")
        print("Data Seeding")
        print("========================================\n")

        conn = await asyncpg.connect(self.db_dsn)

        try:
            # 1. Seed properties
            print("1. Seeding properties...")
            await self.seed_properties(conn)
            print("   ✓ Properties seeded\n")

            # 2. Seed SERP queries
            print("2. Seeding SERP tracking queries...")
            await self.seed_serp_queries(conn)
            print("   ✓ SERP queries seeded\n")

            # 3. Seed alert rules
            print("3. Seeding alert rules...")
            await self.seed_alert_rules()
            print("   ✓ Alert rules seeded\n")

            # 4. Seed channel configurations
            print("4. Seeding notification channels...")
            await self.seed_notification_channels(conn)
            print("   ✓ Notification channels configured\n")

            print("========================================")
            print("Data Seeding Complete!")
            print("========================================\n")

            # Summary
            property_count = await conn.fetchval("SELECT COUNT(*) FROM base.properties")
            query_count = await conn.fetchval("SELECT COUNT(*) FROM serp.queries")
            rule_count = await conn.fetchval("SELECT COUNT(*) FROM notifications.alert_rules")
            channel_count = await conn.fetchval("SELECT COUNT(*) FROM notifications.channel_configs")

            print(f"Properties:     {property_count}")
            print(f"SERP Queries:   {query_count}")
            print(f"Alert Rules:    {rule_count}")
            print(f"Channels:       {channel_count}")
            print("")

        finally:
            await conn.close()

    async def seed_properties(self, conn):
        """Seed initial properties"""
        properties = [
            {
                'url': PROPERTY_URL,
                'name': 'Main Website',
                'type': 'website'
            }
        ]

        if TEST_MODE:
            properties.append({
                'url': 'https://blog.yourdomain.com',
                'name': 'Blog',
                'type': 'blog'
            })

        for prop in properties:
            await conn.execute("""
                INSERT INTO base.properties (property_url, display_name, property_type, is_active)
                VALUES ($1, $2, $3, true)
                ON CONFLICT (property_url) DO UPDATE
                SET display_name = EXCLUDED.display_name
            """, prop['url'], prop['name'], prop['type'])

            print(f"   Added property: {prop['name']} ({prop['url']})")

    async def seed_serp_queries(self, conn):
        """Seed initial SERP tracking queries"""
        # Example queries - user should customize these
        queries = [
            {
                'text': 'your brand name',
                'path': '/',
                'location': 'United States',
                'device': 'desktop',
                'priority': 'high'
            },
            {
                'text': 'your main keyword',
                'path': '/main-page',
                'location': 'United States',
                'device': 'mobile',
                'priority': 'high'
            },
        ]

        if TEST_MODE:
            queries.extend([
                {'text': 'test keyword 1', 'path': '/test-1', 'location': 'United States', 'device': 'desktop', 'priority': 'medium'},
                {'text': 'test keyword 2', 'path': '/test-2', 'location': 'United States', 'device': 'mobile', 'priority': 'low'},
            ])

        for query in queries:
            await conn.execute("""
                INSERT INTO serp.queries
                (query_text, property, target_page_path, location, device, is_active)
                VALUES ($1, $2, $3, $4, $5, true)
                ON CONFLICT DO NOTHING
            """, query['text'], PROPERTY_URL, query['path'], query['location'], query['device'])

            print(f"   Added query: {query['text']} -> {query['path']}")

    async def seed_alert_rules(self):
        """Seed initial alert rules"""
        manager = AlertManager(db_dsn=self.db_dsn)

        # Register notifiers
        manager.register_notifier('slack', SlackNotifier())
        manager.register_notifier('email', EmailNotifier())

        alert_rules = [
            {
                'name': 'SERP Position Drop - High Priority',
                'type': 'serp_drop',
                'conditions': {'position_drop': 3, 'min_impressions': 100},
                'severity': 'high',
                'channels': ['slack', 'email'],
                'suppression_window': 360,
                'max_per_day': 5
            },
            {
                'name': 'SERP Position Drop - Critical',
                'type': 'serp_drop',
                'conditions': {'position_drop': 5, 'min_impressions': 500},
                'severity': 'critical',
                'channels': ['slack', 'email'],
                'suppression_window': 180,
                'max_per_day': 10
            },
            {
                'name': 'Poor Core Web Vitals',
                'type': 'cwv_poor',
                'conditions': {'lcp_threshold': 2500, 'cls_threshold': 0.1},
                'severity': 'high',
                'channels': ['slack'],
                'suppression_window': 1440,
                'max_per_day': 3
            },
            {
                'name': 'Traffic Drop',
                'type': 'traffic_drop',
                'conditions': {'clicks_drop_pct': 30, 'min_baseline_clicks': 100},
                'severity': 'high',
                'channels': ['slack', 'email'],
                'suppression_window': 360,
                'max_per_day': 3
            },
        ]

        for rule in alert_rules:
            try:
                rule_id = await manager.create_alert_rule(
                    rule_name=rule['name'],
                    rule_type=rule['type'],
                    conditions=rule['conditions'],
                    severity=rule['severity'],
                    channels=rule['channels'],
                    property=PROPERTY_URL,
                    suppression_window_minutes=rule['suppression_window'],
                    max_alerts_per_day=rule['max_per_day']
                )
                print(f"   Added rule: {rule['name']} (severity: {rule['severity']})")
            except Exception as e:
                print(f"   Warning: Could not create rule '{rule['name']}': {e}")

    async def seed_notification_channels(self, conn):
        """Seed notification channel configurations"""
        channels = []

        # Slack channel
        if os.getenv('SLACK_WEBHOOK_URL'):
            channels.append({
                'name': 'slack_default',
                'type': 'slack',
                'config': {
                    'webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
                    'channel': os.getenv('SLACK_DEFAULT_CHANNEL', '#seo-alerts'),
                    'username': os.getenv('SLACK_USERNAME', 'SEO Intelligence Bot')
                }
            })

        # Email channel
        if os.getenv('SMTP_HOST') or os.getenv('SENDGRID_API_KEY'):
            email_config = {}
            if os.getenv('SENDGRID_API_KEY'):
                email_config = {
                    'method': 'sendgrid',
                    'api_key': os.getenv('SENDGRID_API_KEY'),
                    'from_email': os.getenv('SENDGRID_FROM_EMAIL'),
                    'to_email': os.getenv('EMAIL_TO')
                }
            else:
                email_config = {
                    'method': 'smtp',
                    'smtp_host': os.getenv('SMTP_HOST'),
                    'smtp_port': int(os.getenv('SMTP_PORT', 587)),
                    'smtp_user': os.getenv('SMTP_USER'),
                    'smtp_pass': os.getenv('SMTP_PASS'),
                    'from_email': os.getenv('EMAIL_FROM'),
                    'to_email': os.getenv('EMAIL_TO')
                }

            channels.append({
                'name': 'email_default',
                'type': 'email',
                'config': email_config
            })

        # Save channels
        for channel in channels:
            await conn.execute("""
                INSERT INTO notifications.channel_configs
                (channel_name, channel_type, config, is_active)
                VALUES ($1, $2, $3, true)
                ON CONFLICT (channel_name) DO UPDATE
                SET config = EXCLUDED.config
            """, channel['name'], channel['type'], channel['config'])

            print(f"   Configured {channel['type']} channel: {channel['name']}")


async def main():
    """Main entry point"""
    seeder = DataSeeder()

    try:
        await seeder.seed_all()

        print("\nNext steps:")
        print("1. Verify data in database")
        print("2. Customize SERP queries for your keywords")
        print("3. Test alert rules: python scripts/test_alert.py")
        print("4. Start data collection: celery -A services.tasks call collect_gsc_data")
        print("")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
