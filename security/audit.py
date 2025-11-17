#!/usr/bin/env python3
"""
Security Audit Script (OPTIONAL)
Scans for common security vulnerabilities and misconfigurations
Use for production hardening assessment
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Any
import re


class SecurityAuditor:
    """Performs security audit of GSC Warehouse"""
    
    CRITICAL = 'CRITICAL'
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    INFO = 'INFO'
    
    def __init__(self, dsn: str):
        """Initialize auditor"""
        self.dsn = dsn
        self.conn = psycopg2.connect(dsn)
        self.findings = []
        self.score = 100
        self.security_mode = os.environ.get('SECURITY_MODE', 'development')
    
    def run_audit(self) -> Dict[str, Any]:
        """Run complete security audit"""
        print("=" * 60)
        print("GSC WAREHOUSE SECURITY AUDIT")
        print("=" * 60)
        print()
        print(f"Security Mode: {self.security_mode}")
        print()
        
        if self.security_mode == 'development':
            print("Running in DEVELOPMENT mode")
            print("  - Relaxed security checks")
            print("  - Some findings may be expected")
            print()
        
        self.check_database_users()
        self.check_password_security()
        self.check_ssl_configuration()
        self.check_file_permissions()
        self.check_secrets_exposure()
        self.check_audit_logging()
        self.check_network_security()
        
        self._calculate_score()
        self._print_report()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'security_mode': self.security_mode,
            'score': self.score,
            'findings': self.findings,
            'summary': self._get_summary()
        }
    
    def check_database_users(self):
        """Check database user configuration"""
        print("Checking database users...")
        
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT usename, usesuper, usecreatedb
            FROM pg_user
            WHERE usename NOT IN ('postgres')
            ORDER BY usename;
        """)
        
        users = cur.fetchall()
        
        for user in users:
            if user['usesuper'] and self.security_mode == 'production':
                self.add_finding(
                    self.HIGH,
                    "Unnecessary Superuser Privilege",
                    f"User '{user['usename']}' has superuser privileges",
                    f"REVOKE superuser from {user['usename']} if not needed"
                )
            
            weak_names = ['admin', 'root', 'test', 'guest']
            if user['usename'].lower() in weak_names:
                severity = self.MEDIUM if self.security_mode == 'production' else self.LOW
                self.add_finding(
                    severity,
                    "Weak Username",
                    f"User '{user['usename']}' uses common/weak username",
                    "Rename user to something less guessable"
                )
        
        readonly_exists = any(u['usename'] == 'gsc_readonly' for u in users)
        if readonly_exists:
            print("  ✓ Read-only user exists")
        elif self.security_mode == 'production':
            self.add_finding(
                self.MEDIUM,
                "No Read-Only User",
                "No dedicated read-only user found",
                "CREATE USER gsc_readonly and grant SELECT only"
            )
        
        cur.close()
    
    def check_password_security(self):
        """Check password configuration"""
        print("Checking password security...")
        
        if self.security_mode == 'development':
            print("  ⊘ Skipped (development mode)")
            return
        
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT usename, valuntil
            FROM pg_user
            WHERE usename NOT IN ('postgres')
            AND valuntil IS NOT NULL
            ORDER BY usename;
        """)
        
        users_with_expiry = cur.fetchall()
        
        for user in users_with_expiry:
            if user['valuntil']:
                days_until_expiry = (user['valuntil'].date() - datetime.now().date()).days
                
                if days_until_expiry < 0:
                    self.add_finding(
                        self.HIGH,
                        "Expired Password",
                        f"Password for user '{user['usename']}' expired {abs(days_until_expiry)} days ago",
                        f"ALTER USER {user['usename']} VALID UNTIL 'new_date'"
                    )
                elif days_until_expiry < 7:
                    self.add_finding(
                        self.MEDIUM,
                        "Password Expiring Soon",
                        f"Password for user '{user['usename']}' expires in {days_until_expiry} days",
                        "Schedule password rotation"
                    )
        
        cur.close()
    
    def check_ssl_configuration(self):
        """Check SSL/TLS configuration"""
        print("Checking SSL configuration...")
        
        cur = self.conn.cursor()
        
        cur.execute("SHOW ssl;")
        ssl_enabled = cur.fetchone()[0]
        
        if ssl_enabled == 'on':
            print("  ✓ SSL enabled")
        else:
            if self.security_mode == 'production':
                self.add_finding(
                    self.HIGH,
                    "SSL Not Enabled",
                    "Database connections are not encrypted",
                    "Enable SSL in postgresql.conf for production"
                )
            else:
                print("  ⊘ SSL not enabled (OK for localhost development)")
        
        cur.close()
    
    def check_file_permissions(self):
        """Check file and directory permissions"""
        print("Checking file permissions...")
        
        sensitive_paths = [
            'secrets/',
            '.env',
            'secrets/gsc_sa.json',
            'secrets/ga4_sa.json'
        ]
        
        for path in sensitive_paths:
            if os.path.exists(path):
                stat_info = os.stat(path)
                mode = stat_info.st_mode
                
                if mode & 0o004:
                    severity = self.HIGH if self.security_mode == 'production' else self.MEDIUM
                    self.add_finding(
                        severity,
                        "World-Readable Secrets",
                        f"'{path}' is readable by all users",
                        f"chmod 600 {path}"
                    )
                elif mode & 0o040:
                    severity = self.MEDIUM if self.security_mode == 'production' else self.LOW
                    self.add_finding(
                        severity,
                        "Group-Readable Secrets",
                        f"'{path}' is readable by group",
                        f"chmod 600 {path}"
                    )
                else:
                    print(f"  ✓ {path} permissions OK")
    
    def check_secrets_exposure(self):
        """Check for exposed secrets"""
        print("Checking for exposed secrets...")
        
        env_vars = os.environ
        
        secret_patterns = [
            r'password',
            r'token',
            r'api[_-]?key',
            r'secret',
            r'credential'
        ]
        
        exposed_secrets = []
        
        for var, value in env_vars.items():
            for pattern in secret_patterns:
                if re.search(pattern, var.lower()) and value and not value.startswith('/run/secrets'):
                    exposed_secrets.append(var)
        
        if exposed_secrets:
            severity = self.HIGH if self.security_mode == 'production' else self.INFO
            self.add_finding(
                severity,
                "Secrets in Environment Variables",
                f"Found {len(exposed_secrets)} potential secrets in environment",
                "Use Docker secrets for production instead of environment variables"
            )
        
        if os.path.exists('.env') and self.security_mode == 'production':
            with open('.env', 'r') as f:
                content = f.read()
                
                if re.search(r'PASSWORD=.{8,}', content):
                    self.add_finding(
                        self.HIGH,
                        "Secrets in .env File",
                        ".env file contains actual passwords",
                        "Use .env for development only. Production should use Docker secrets"
                    )
    
    def check_audit_logging(self):
        """Check audit logging configuration"""
        print("Checking audit logging...")
        
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'gsc'
                AND tablename = 'audit_log'
            );
        """)
        
        audit_exists = cur.fetchone()[0]
        
        if audit_exists:
            print("  ✓ Audit log table exists")
            
            if self.security_mode == 'production':
                cur.execute("""
                    SELECT COUNT(*) as recent_events
                    FROM gsc.audit_log
                    WHERE event_time > CURRENT_TIMESTAMP - INTERVAL '24 hours';
                """)
                
                recent_count = cur.fetchone()['recent_events']
                
                if recent_count == 0:
                    self.add_finding(
                        self.MEDIUM,
                        "No Recent Audit Events",
                        "No audit log entries in last 24 hours",
                        "Verify audit triggers are working"
                    )
        elif self.security_mode == 'production':
            self.add_finding(
                self.HIGH,
                "Audit Logging Disabled",
                "No audit_log table found",
                "Run sql/00_security.sql to enable audit logging"
            )
        
        cur.close()
    
    def check_network_security(self):
        """Check network security configuration"""
        print("Checking network security...")
        
        if os.path.exists('docker-compose.yml'):
            with open('docker-compose.yml', 'r') as f:
                content = f.read()
                
                if re.search(r'ports:\s*\n\s*-\s*["\']?\d+:\d+', content) and self.security_mode == 'production':
                    self.add_finding(
                        self.MEDIUM,
                        "Services May Be Exposed",
                        "Services may be accessible from outside localhost",
                        "Bind ports to localhost: '127.0.0.1:5432:5432'"
                    )
    
    def add_finding(self, severity: str, title: str, description: str, remediation: str):
        """Add security finding"""
        self.findings.append({
            'severity': severity,
            'title': title,
            'description': description,
            'remediation': remediation
        })
        
        deductions = {
            self.CRITICAL: 25,
            self.HIGH: 15,
            self.MEDIUM: 10,
            self.LOW: 5,
            self.INFO: 0
        }
        
        # In development mode, reduce deductions
        if self.security_mode == 'development':
            deductions = {k: v // 2 for k, v in deductions.items()}
        
        self.score -= deductions.get(severity, 0)
    
    def _calculate_score(self):
        """Ensure score is between 0-100"""
        self.score = max(0, min(100, self.score))
    
    def _get_summary(self) -> Dict[str, int]:
        """Get summary of findings by severity"""
        summary = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }
        
        for finding in self.findings:
            summary[finding['severity'].lower()] += 1
        
        return summary
    
    def _print_report(self):
        """Print human-readable audit report"""
        print()
        print("=" * 60)
        print("AUDIT RESULTS")
        print("=" * 60)
        print()
        
        if self.score >= 90:
            grade = "A (Excellent)"
            color = "\033[0;32m"
        elif self.score >= 80:
            grade = "B (Good)"
            color = "\033[0;32m"
        elif self.score >= 70:
            grade = "C (Fair)"
            color = "\033[1;33m"
        elif self.score >= 60:
            grade = "D (Poor)"
            color = "\033[1;33m"
        else:
            grade = "F (Critical)"
            color = "\033[0;31m"
        
        print(f"Security Score: {color}{self.score}/100 - Grade {grade}\033[0m")
        print()
        
        summary = self._get_summary()
        print("Findings Summary:")
        print(f"  🚨 Critical: {summary['critical']}")
        print(f"  ⚠️  High:     {summary['high']}")
        print(f"  ⚡ Medium:   {summary['medium']}")
        print(f"  ℹ️  Low:      {summary['low']}")
        print()
        
        if self.findings:
            print("=" * 60)
            print("DETAILED FINDINGS")
            print("=" * 60)
            print()
            
            severity_order = {
                self.CRITICAL: 0,
                self.HIGH: 1,
                self.MEDIUM: 2,
                self.LOW: 3,
                self.INFO: 4
            }
            
            sorted_findings = sorted(
                self.findings,
                key=lambda f: severity_order.get(f['severity'], 99)
            )
            
            for i, finding in enumerate(sorted_findings, 1):
                icon = {
                    self.CRITICAL: '🚨',
                    self.HIGH: '⚠️',
                    self.MEDIUM: '⚡',
                    self.LOW: 'ℹ️',
                    self.INFO: '💡'
                }.get(finding['severity'], '•')
                
                print(f"{i}. {icon} [{finding['severity']}] {finding['title']}")
                print(f"   Issue: {finding['description']}")
                print(f"   Fix: {finding['remediation']}")
                print()
        else:
            print("✓ No security issues found!")
            print()
    
    def save_json(self, filepath: str):
        """Save audit results to JSON"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'security_mode': self.security_mode,
            'score': self.score,
            'findings': self.findings,
            'summary': self._get_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Audit results saved to: {filepath}")
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main audit routine"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Security audit for GSC Warehouse')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--fail-threshold', type=int, default=70,
                       help='Fail if score below this threshold')
    args = parser.parse_args()
    
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        print("Error: WAREHOUSE_DSN environment variable not set")
        sys.exit(1)
    
    auditor = SecurityAuditor(dsn)
    
    try:
        results = auditor.run_audit()
        
        if args.output:
            auditor.save_json(args.output)
        
        if results['score'] < args.fail_threshold:
            print()
            print(f"Security score {results['score']} is below threshold {args.fail_threshold}")
            sys.exit(1)
        
    finally:
        auditor.close()


if __name__ == '__main__':
    main()
