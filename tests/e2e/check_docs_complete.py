#!/usr/bin/env python3
"""Check documentation completeness."""

import sys
from pathlib import Path
from typing import List, Tuple


class DocumentationChecker:
    """Checks documentation completeness."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
    
    def check_file_exists(self, filepath: str, required: bool = True) -> bool:
        """Check if a documentation file exists."""
        path = Path(filepath)
        if path.exists():
            # Check if file is not empty
            if path.stat().st_size > 0:
                self.passed.append(f"✓ {filepath}")
                return True
            else:
                msg = f"✗ {filepath} is empty"
                if required:
                    self.issues.append(msg)
                else:
                    self.warnings.append(msg)
                return False
        else:
            msg = f"✗ {filepath} does not exist"
            if required:
                self.issues.append(msg)
            else:
                self.warnings.append(msg)
            return False
    
    def check_content_sections(self, filepath: str, required_sections: List[str]) -> bool:
        """Check if file contains required sections."""
        path = Path(filepath)
        if not path.exists():
            return False
        
        content = path.read_text()
        missing = []
        
        for section in required_sections:
            # Check for markdown headers
            if f"# {section}" not in content and f"## {section}" not in content:
                missing.append(section)
        
        if missing:
            msg = f"✗ {filepath} missing sections: {', '.join(missing)}"
            self.issues.append(msg)
            return False
        else:
            self.passed.append(f"✓ {filepath} has all required sections")
            return True
    
    def check_code_examples(self, filepath: str, min_examples: int = 1) -> bool:
        """Check if file contains code examples."""
        path = Path(filepath)
        if not path.exists():
            return False
        
        content = path.read_text()
        code_blocks = content.count("```")
        example_count = code_blocks // 2  # Each code block has start and end
        
        if example_count >= min_examples:
            self.passed.append(f"✓ {filepath} has {example_count} code examples")
            return True
        else:
            msg = f"⚠ {filepath} has only {example_count} code examples (expected {min_examples}+)"
            self.warnings.append(msg)
            return False
    
    def check_links_format(self, filepath: str) -> bool:
        """Check if internal links are properly formatted."""
        path = Path(filepath)
        if not path.exists():
            return False
        
        content = path.read_text()
        lines = content.split('\n')
        
        broken_links = []
        for i, line in enumerate(lines, 1):
            # Check for markdown links
            if '[' in line and '](' in line:
                # Extract link target
                start = line.find('](') + 2
                end = line.find(')', start)
                if start > 1 and end > start:
                    link = line[start:end]
                    
                    # Check if it's a relative file link
                    if not link.startswith('http') and not link.startswith('#'):
                        # Check if file exists
                        link_path = path.parent / link
                        if not link_path.exists():
                            broken_links.append(f"Line {i}: {link}")
        
        if broken_links:
            msg = f"⚠ {filepath} has broken links: {', '.join(broken_links[:3])}"
            if len(broken_links) > 3:
                msg += f" and {len(broken_links) - 3} more"
            self.warnings.append(msg)
            return False
        else:
            self.passed.append(f"✓ {filepath} has valid links")
            return True
    
    def validate_deployment_docs(self) -> bool:
        """Validate deployment documentation."""
        print("\n=== Deployment Documentation ===")
        
        # Check deployment guide
        deployment_guide = "docs/deployment/DEPLOYMENT_GUIDE.md"
        self.check_file_exists(deployment_guide, required=True)
        self.check_content_sections(deployment_guide, [
            "Overview",
            "Prerequisites",
            "Deployment Steps",
            "Validation",
            "Troubleshooting"
        ])
        self.check_code_examples(deployment_guide, min_examples=10)
        
        # Check production checklist
        checklist = "docs/deployment/PRODUCTION_CHECKLIST.md"
        self.check_file_exists(checklist, required=True)
        self.check_content_sections(checklist, [
            "Infrastructure",
            "Application Components",
            "Configuration",
            "Monitoring",
            "Testing",
            "Sign-Off"
        ])
        
        # Check troubleshooting guide
        troubleshooting = "docs/deployment/TROUBLESHOOTING.md"
        self.check_file_exists(troubleshooting, required=True)
        self.check_content_sections(troubleshooting, [
            "Quick Reference",
            "Common Issues",
            "Emergency Procedures"
        ])
        self.check_code_examples(troubleshooting, min_examples=15)
        
        return len(self.issues) == 0
    
    def validate_runbooks(self) -> bool:
        """Validate operational runbooks."""
        print("\n=== Operational Runbooks ===")
        
        # Check daily operations
        daily_ops = "docs/runbooks/DAILY_OPERATIONS.md"
        self.check_file_exists(daily_ops, required=True)
        self.check_content_sections(daily_ops, [
            "Daily Health Check",
            "Weekly Tasks",
            "Monthly Tasks",
            "Common Operations"
        ])
        self.check_code_examples(daily_ops, min_examples=10)
        
        # Check incident response
        incident_response = "docs/runbooks/INCIDENT_RESPONSE.md"
        self.check_file_exists(incident_response, required=True)
        self.check_content_sections(incident_response, [
            "Incident Severity Levels",
            "Incident Response Process",
            "Incident Playbooks",
            "Escalation Matrix"
        ])
        self.check_code_examples(incident_response, min_examples=10)
        
        return len(self.issues) == 0
    
    def validate_test_documentation(self) -> bool:
        """Validate test documentation."""
        print("\n=== Test Documentation ===")
        
        # Check test files exist
        test_files = [
            "tests/e2e/test_full_pipeline.py",
            "tests/e2e/test_agent_orchestration.py",
            "tests/e2e/test_data_flow.py",
            "tests/load/test_system_load.py"
        ]
        
        for test_file in test_files:
            self.check_file_exists(test_file, required=True)
            
            # Check test file has docstrings
            path = Path(test_file)
            if path.exists():
                content = path.read_text()
                if '"""' in content or "'''" in content:
                    self.passed.append(f"✓ {test_file} has docstrings")
                else:
                    self.warnings.append(f"⚠ {test_file} missing docstrings")
        
        return len(self.issues) == 0
    
    def validate_readme_files(self) -> bool:
        """Validate README files."""
        print("\n=== README Files ===")
        
        # Main README
        main_readme = "README.md"
        if Path(main_readme).exists():
            self.passed.append(f"✓ {main_readme} exists")
        else:
            self.warnings.append(f"⚠ {main_readme} not found")
        
        return True
    
    def print_summary(self) -> int:
        """Print summary and return exit code."""
        print("\n" + "=" * 80)
        print("DOCUMENTATION COMPLETENESS SUMMARY")
        print("=" * 80)
        
        total_checks = len(self.passed) + len(self.issues) + len(self.warnings)
        
        print(f"\nTotal Checks: {total_checks}")
        print(f"✓ Passed: {len(self.passed)}")
        print(f"✗ Issues: {len(self.issues)}")
        print(f"⚠ Warnings: {len(self.warnings)}")
        
        if self.issues:
            print("\n✗ CRITICAL ISSUES (Must Fix):")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print("\n⚠ WARNINGS (Should Fix):")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.passed and not self.issues and not self.warnings:
            print("\n✓ ALL DOCUMENTATION CHECKS PASSED:")
            for passed in self.passed[:10]:  # Show first 10
                print(f"  {passed}")
            if len(self.passed) > 10:
                print(f"  ... and {len(self.passed) - 10} more")
        
        print("\n" + "=" * 80)
        
        if len(self.issues) == 0:
            print("✓ DOCUMENTATION IS COMPLETE")
            print("=" * 80)
            return 0
        else:
            print("✗ DOCUMENTATION IS INCOMPLETE")
            print("Please fix the critical issues before deployment.")
            print("=" * 80)
            return 1


def main():
    """Main entry point."""
    print("=" * 80)
    print("DOCUMENTATION COMPLETENESS CHECK")
    print("=" * 80)
    
    checker = DocumentationChecker()
    
    # Run all validations
    checker.validate_deployment_docs()
    checker.validate_runbooks()
    checker.validate_test_documentation()
    checker.validate_readme_files()
    
    # Print summary and exit
    exit_code = checker.print_summary()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
