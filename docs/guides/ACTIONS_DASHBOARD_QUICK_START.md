# Actions Command Center - Quick Start Guide

## 5-Minute Setup

### Prerequisites
- PostgreSQL database with `gsc.actions` table
- Grafana 9.0+ running
- PostgreSQL data source configured in Grafana

### Setup Steps

#### 1. Create Database Views (2 minutes)
```bash
# Connect to your database
psql -U postgres -d your_database

# Run the views script
\i sql/28_actions_metrics_views.sql

# Verify views were created
\dv gsc.vw_actions*

# Expected output: 9 views listed
```

#### 2. Restart Grafana (1 minute)
```bash
# Docker
docker-compose restart grafana

# Linux service
sudo systemctl restart grafana-server

# Wait for Grafana to start
```

#### 3. Access Dashboard (1 minute)
```
URL: http://localhost:3000/d/actions-center/actions-command-center

1. Open browser
2. Navigate to URL above
3. Select a property from dropdown at top
4. Dashboard loads automatically
```

#### 4. Verify Data (1 minute)
Check that all panels show data:
- Top row: 4 stat panels with numbers
- Row 2: 3 charts with data
- Row 3: Time series graph
- Row 4: 2 tables with actions
- Row 5: Completion rate graph and effort chart

## Daily Usage

### For SEO Managers
**Morning Routine** (5 minutes):
1. Open dashboard
2. Check "Pending Actions" table
3. Note critical priority items (red)
4. Review "Completed This Week" stat
5. Plan day based on top priorities

**Weekly Review** (10 minutes):
1. Review "Weekly Completion Rate"
2. Check "Actions by Type" for patterns
3. Identify bottlenecks
4. Adjust team priorities

### For Team Leads
**Daily Check** (2 minutes):
1. Monitor "Pending Actions" count
2. Check completion rate trend
3. Review "Actions by Priority"

**Weekly Planning** (15 minutes):
1. Analyze "Actions by Type" distribution
2. Review completion rates
3. Identify automation opportunities
4. Resource allocation planning

### For Executives
**Weekly KPI Review** (5 minutes):
1. Top 4 stats: Total, Pending, Completed, Avg Time
2. Completion rate trend: Above 70%?
3. Status pie chart: Balanced?
4. Action type distribution: Concentrated or diverse?

## Key Metrics

### Green = Good
- Completion rate: >85%
- Avg completion time: <7 days
- Pending actions: <20

### Yellow = Warning
- Completion rate: 70-85%
- Avg completion time: 7-14 days
- Pending actions: 20-50

### Red = Action Needed
- Completion rate: <50%
- Avg completion time: >14 days
- Pending actions: >50

## Common Queries

### Find All Critical Actions
```sql
SELECT title, action_type, created_at
FROM gsc.actions
WHERE priority = 'critical'
  AND status = 'pending'
ORDER BY created_at;
```

### Check Completion Rate This Month
```sql
SELECT
  COUNT(*) FILTER (WHERE status = 'completed') as completed,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'completed') / COUNT(*), 1) as rate_pct
FROM gsc.actions
WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE);
```

### Low Effort, High Priority Actions
```sql
SELECT title, action_type, priority
FROM gsc.actions
WHERE effort = 'low'
  AND priority IN ('critical', 'high')
  AND status = 'pending'
ORDER BY
  CASE priority WHEN 'critical' THEN 1 ELSE 2 END,
  created_at;
```

## Troubleshooting

### Dashboard Shows "No Data"
**Fix 1**: Select a property from dropdown
**Fix 2**: Check if actions exist:
```sql
SELECT COUNT(*), property FROM gsc.actions GROUP BY property;
```

### Property Dropdown Empty
**Fix**: Ensure actions have property values:
```sql
UPDATE gsc.actions SET property = 'your-site.com' WHERE property IS NULL;
```

### Slow Loading
**Fix**: Run view creation script (includes indexes):
```bash
psql -U postgres -d your_database -f sql/28_actions_metrics_views.sql
```

### Panel Shows Error
**Fix 1**: Check PostgreSQL connection in Grafana
**Fix 2**: Verify data source named "postgres" exists
**Fix 3**: Check database user has SELECT permission on `gsc` schema

## Tips & Tricks

### Filtering
- Use property dropdown to switch between sites
- Adjust time range picker for different periods
- Click legend items to hide/show series

### Exporting
- Click panel title → More → Export CSV
- Use for reports or external analysis
- Works on all table and chart panels

### Sharing
- Click share icon → Copy link
- Send to team members
- Set time range before sharing

### Custom Time Ranges
- Click time picker (top right)
- Select: Last 7d, 30d, 90d
- Or use custom date range

### Refreshing
- Auto-refresh: Every 5 minutes
- Manual refresh: Click refresh icon
- Or press Ctrl+R (Cmd+R on Mac)

## Integration Examples

### Slack Notification
```python
# When action count exceeds threshold
import requests

def check_actions():
    result = db.execute("""
        SELECT COUNT(*) FROM gsc.actions
        WHERE status = 'pending' AND priority = 'critical'
    """)
    if result[0] > 10:
        requests.post(SLACK_WEBHOOK, json={
            "text": f"⚠️ {result[0]} critical actions pending!"
        })
```

### Email Report
```python
# Weekly summary email
import smtplib

def weekly_summary():
    stats = db.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'pending') as pending
        FROM gsc.actions
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    """)
    send_email(f"Weekly: {stats['completed']} completed, {stats['pending']} pending")
```

## Panel Reference

| Panel | Type | Purpose |
|-------|------|---------|
| Total Actions | Stat | Overall action count |
| Pending Actions | Stat | Open items needing attention |
| Completed This Week | Stat | Recent activity |
| Avg Completion Time | Stat | Performance metric |
| Actions by Status | Pie | Status distribution |
| Actions by Priority | Bar | Priority breakdown |
| Actions by Type | Bar | Type distribution |
| Actions Over Time | Time Series | Creation vs completion trend |
| Pending Actions | Table | Top priority items |
| Recently Completed | Table | Recent completions |
| Weekly Completion Rate | Time Series | Performance trend |
| Pending by Effort | Donut | Effort distribution |
| Action Types Summary | Table | Comprehensive breakdown |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + R` | Refresh dashboard |
| `Ctrl/Cmd + S` | Save dashboard (if editing) |
| `d + k` | Show keyboard shortcuts |
| `f` | Toggle fullscreen |
| `Esc` | Exit panel fullscreen |

## Mobile Access

Dashboard is mobile-responsive:
- Stack panels vertically on small screens
- Touch-friendly controls
- Swipe to navigate
- Access via: `http://your-server:3000/d/actions-center`

## Support & Resources

- **Full Documentation**: `docs/guides/ACTIONS_COMMAND_CENTER.md`
- **Implementation Details**: `TASKCARD-036-IMPLEMENTATION.md`
- **SQL Views**: `sql/28_actions_metrics_views.sql`
- **Tests**: `tests/test_actions_dashboard_setup.py`

## Next Steps

After basic setup:
1. Set up Grafana alerting rules
2. Create user accounts and permissions
3. Configure SMTP for email alerts
4. Set up Slack integration
5. Create custom panels for your needs

## Quick Links

- Grafana Docs: https://grafana.com/docs/
- PostgreSQL Views: https://postgresql.org/docs/current/sql-createview.html
- Dashboard JSON: `grafana/provisioning/dashboards/actions-command-center.json`

---

**Last Updated**: 2025-11-26
**Version**: 1.0
**Status**: Production Ready
