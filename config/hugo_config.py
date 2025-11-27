"""
Hugo Configuration Module
=========================
Configuration for Hugo site content path resolution with support for
both file-based and folder-based localization patterns.

File-based localization (e.g., blog.aspose.net):
    index.md, index.es.md, index.fr.md

Folder-based localization (all others):
    /en/page.md, /es/page.md, /fr/page.md
"""
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class HugoConfig:
    """
    Configuration for Hugo content path resolution.

    Attributes:
        content_path: Base path to Hugo content directory
        file_localization_subdomains: List of subdomains using file-based localization
        default_locale: Default locale when not specified (default: "en")
    """
    content_path: str
    file_localization_subdomains: List[str] = field(default_factory=list)
    default_locale: str = "en"

    @classmethod
    def from_env(cls) -> "HugoConfig":
        """
        Create HugoConfig from environment variables.

        Environment Variables:
            HUGO_CONTENT_PATH: Path to Hugo content directory
            HUGO_FILE_LOCALIZATION_SUBDOMAINS: Comma-separated list of subdomains
            HUGO_DEFAULT_LOCALE: Default locale (default: "en")

        Returns:
            HugoConfig instance
        """
        content_path = os.environ.get("HUGO_CONTENT_PATH", "")
        subdomains_str = os.environ.get("HUGO_FILE_LOCALIZATION_SUBDOMAINS", "")

        # Parse comma-separated subdomains, filtering empty strings
        subdomains = [
            s.strip() for s in subdomains_str.split(",")
            if s.strip()
        ]

        default_locale = os.environ.get("HUGO_DEFAULT_LOCALE", "en")

        return cls(
            content_path=content_path,
            file_localization_subdomains=subdomains,
            default_locale=default_locale
        )

    def is_file_localized(self, subdomain: str) -> bool:
        """
        Check if subdomain uses file-based localization.

        File-based localization stores translations as:
            index.md (default), index.es.md, index.fr.md

        Args:
            subdomain: The subdomain to check (e.g., "blog.aspose.net")

        Returns:
            True if subdomain uses file-based localization
        """
        if not subdomain:
            return False
        return subdomain.lower() in [s.lower() for s in self.file_localization_subdomains]

    def get_content_file_path(
        self,
        subdomain: str,
        page_path: str,
        locale: Optional[str] = None
    ) -> str:
        """
        Resolve full filesystem path for a Hugo content file.

        Handles both localization patterns:
        - File-based: blog.aspose.net/posts/article/ -> blog.aspose.net/posts/article/index.es.md
        - Folder-based: docs.aspose.net/getting-started/ -> docs.aspose.net/es/getting-started.md

        Args:
            subdomain: The site subdomain (e.g., "blog.aspose.net")
            page_path: The page path (e.g., "/posts/article/" or "/getting-started/")
            locale: Optional locale code (default: self.default_locale)

        Returns:
            Full filesystem path to the markdown file
        """
        locale = locale or self.default_locale

        # Normalize subdomain
        subdomain = subdomain.strip().lower() if subdomain else ""

        # Clean page_path: remove leading/trailing slashes and normalize separators
        page_path = page_path.strip("/") if page_path else ""
        # Normalize forward slashes to OS path separator
        page_path = page_path.replace("/", os.sep)

        # Build base path
        base = os.path.join(self.content_path, subdomain)

        if self.is_file_localized(subdomain):
            # File-based localization: index.md, index.es.md, index.fr.md
            # Default locale has no suffix, others have .{locale} suffix
            if locale.lower() == self.default_locale.lower():
                filename = "index.md"
            else:
                filename = f"index.{locale}.md"

            # Handle empty page_path (root)
            if page_path:
                return os.path.join(base, page_path, filename)
            else:
                return os.path.join(base, filename)
        else:
            # Folder-based localization: /en/page.md, /es/page.md
            # Handle empty page_path (likely index)
            if page_path:
                # Check if page_path already ends with .md
                if page_path.endswith('.md'):
                    return os.path.join(base, locale, page_path)
                else:
                    return os.path.join(base, locale, f"{page_path}.md")
            else:
                # Root path -> _index.md
                return os.path.join(base, locale, "_index.md")

    def extract_subdomain(self, property_url: str) -> str:
        """
        Extract subdomain from property URL.

        Args:
            property_url: Full URL (e.g., "https://blog.aspose.net" or "sc-domain:aspose.net")

        Returns:
            The subdomain/domain portion (e.g., "blog.aspose.net")
        """
        if not property_url:
            return ""

        property_url = property_url.strip()

        # Handle sc-domain: prefix (GSC domain property format)
        if property_url.startswith("sc-domain:"):
            return property_url[10:].strip()

        # Try to parse as URL
        if property_url.startswith(('http://', 'https://')):
            parsed = urlparse(property_url)
            return parsed.netloc.lower() if parsed.netloc else ""

        # Handle bare domain (no protocol)
        # Use regex to extract domain-like pattern
        match = re.match(r'^([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}', property_url)
        if match:
            return match.group(0).lower()

        return property_url.lower()

    def is_configured(self) -> bool:
        """
        Check if Hugo integration is properly configured.

        Returns:
            True if content_path is set and non-empty
        """
        return bool(self.content_path and self.content_path.strip())

    def validate_path(self) -> Optional[str]:
        """
        Validate that the configured content path exists.

        Returns:
            None if valid, error message string if invalid
        """
        if not self.is_configured():
            return "HUGO_CONTENT_PATH is not configured"

        if not os.path.exists(self.content_path):
            return f"Hugo content path does not exist: {self.content_path}"

        if not os.path.isdir(self.content_path):
            return f"Hugo content path is not a directory: {self.content_path}"

        return None

    def __repr__(self) -> str:
        return (
            f"HugoConfig(content_path={self.content_path!r}, "
            f"file_localization_subdomains={self.file_localization_subdomains!r}, "
            f"default_locale={self.default_locale!r})"
        )
