"""
Tests for Hugo Configuration Module
====================================
Tests path resolution for both file-based and folder-based localization patterns.
"""
import os
import tempfile
import pytest
from unittest.mock import patch

from config.hugo_config import HugoConfig


class TestHugoConfigBasic:
    """Test basic HugoConfig functionality."""

    def test_default_values(self):
        """Test HugoConfig with minimal configuration."""
        config = HugoConfig(content_path="/test/path")
        assert config.content_path == "/test/path"
        assert config.file_localization_subdomains == []
        assert config.default_locale == "en"

    def test_custom_values(self):
        """Test HugoConfig with custom values."""
        config = HugoConfig(
            content_path="D:\\content",
            file_localization_subdomains=["blog.aspose.net", "news.aspose.net"],
            default_locale="fr"
        )
        assert config.content_path == "D:\\content"
        assert config.file_localization_subdomains == ["blog.aspose.net", "news.aspose.net"]
        assert config.default_locale == "fr"

    def test_repr(self):
        """Test string representation."""
        config = HugoConfig(
            content_path="/test",
            file_localization_subdomains=["blog.test.com"],
            default_locale="en"
        )
        repr_str = repr(config)
        assert "HugoConfig" in repr_str
        assert "/test" in repr_str
        assert "blog.test.com" in repr_str


class TestHugoConfigFromEnv:
    """Test HugoConfig.from_env() method."""

    def test_from_env_with_all_vars(self):
        """Test loading from environment with all variables set."""
        env = {
            "HUGO_CONTENT_PATH": "D:\\onedrive\\Documents\\GitHub\\aspose.net\\content",
            "HUGO_FILE_LOCALIZATION_SUBDOMAINS": "blog.aspose.net,news.aspose.net",
            "HUGO_DEFAULT_LOCALE": "es"
        }
        with patch.dict(os.environ, env, clear=False):
            config = HugoConfig.from_env()
            assert config.content_path == "D:\\onedrive\\Documents\\GitHub\\aspose.net\\content"
            assert config.file_localization_subdomains == ["blog.aspose.net", "news.aspose.net"]
            assert config.default_locale == "es"

    def test_from_env_with_empty_vars(self):
        """Test loading from environment with missing variables."""
        env = {}
        with patch.dict(os.environ, env, clear=True):
            config = HugoConfig.from_env()
            assert config.content_path == ""
            assert config.file_localization_subdomains == []
            assert config.default_locale == "en"

    def test_from_env_with_whitespace_subdomains(self):
        """Test handling of whitespace in subdomain list."""
        env = {
            "HUGO_CONTENT_PATH": "/content",
            "HUGO_FILE_LOCALIZATION_SUBDOMAINS": " blog.aspose.net , news.aspose.net , ",
            "HUGO_DEFAULT_LOCALE": "en"
        }
        with patch.dict(os.environ, env, clear=False):
            config = HugoConfig.from_env()
            assert config.file_localization_subdomains == ["blog.aspose.net", "news.aspose.net"]


class TestIsFileLocalized:
    """Test is_file_localized() method."""

    def test_file_localized_subdomain(self):
        """Test detection of file-localized subdomain."""
        config = HugoConfig(
            content_path="/test",
            file_localization_subdomains=["blog.aspose.net"]
        )
        assert config.is_file_localized("blog.aspose.net") is True
        assert config.is_file_localized("docs.aspose.net") is False

    def test_case_insensitive(self):
        """Test case-insensitive subdomain matching."""
        config = HugoConfig(
            content_path="/test",
            file_localization_subdomains=["Blog.Aspose.Net"]
        )
        assert config.is_file_localized("blog.aspose.net") is True
        assert config.is_file_localized("BLOG.ASPOSE.NET") is True

    def test_empty_subdomain(self):
        """Test handling of empty subdomain."""
        config = HugoConfig(
            content_path="/test",
            file_localization_subdomains=["blog.aspose.net"]
        )
        assert config.is_file_localized("") is False
        assert config.is_file_localized(None) is False


class TestGetContentFilePath:
    """Test get_content_file_path() method."""

    @pytest.fixture
    def config(self):
        """Create a standard test config."""
        return HugoConfig(
            content_path="D:\\content",
            file_localization_subdomains=["blog.aspose.net"],
            default_locale="en"
        )

    # File-based localization tests
    def test_file_based_default_locale(self, config):
        """Test file-based path with default locale."""
        path = config.get_content_file_path("blog.aspose.net", "/posts/article/", "en")
        # Windows path
        expected = os.path.join("D:\\content", "blog.aspose.net", "posts", "article", "index.md")
        assert path == expected

    def test_file_based_non_default_locale(self, config):
        """Test file-based path with non-default locale."""
        path = config.get_content_file_path("blog.aspose.net", "/posts/article/", "es")
        expected = os.path.join("D:\\content", "blog.aspose.net", "posts", "article", "index.es.md")
        assert path == expected

    def test_file_based_implicit_default_locale(self, config):
        """Test file-based path with implicit default locale."""
        path = config.get_content_file_path("blog.aspose.net", "/posts/article/")
        expected = os.path.join("D:\\content", "blog.aspose.net", "posts", "article", "index.md")
        assert path == expected

    # Folder-based localization tests
    def test_folder_based_default_locale(self, config):
        """Test folder-based path with default locale."""
        path = config.get_content_file_path("docs.aspose.net", "/getting-started/", "en")
        expected = os.path.join("D:\\content", "docs.aspose.net", "en", "getting-started.md")
        assert path == expected

    def test_folder_based_non_default_locale(self, config):
        """Test folder-based path with non-default locale."""
        path = config.get_content_file_path("docs.aspose.net", "/getting-started/", "es")
        expected = os.path.join("D:\\content", "docs.aspose.net", "es", "getting-started.md")
        assert path == expected

    def test_folder_based_implicit_default_locale(self, config):
        """Test folder-based path with implicit default locale."""
        path = config.get_content_file_path("docs.aspose.net", "/getting-started/")
        expected = os.path.join("D:\\content", "docs.aspose.net", "en", "getting-started.md")
        assert path == expected

    # Edge cases
    def test_empty_page_path_file_based(self, config):
        """Test empty page path for file-based subdomain."""
        path = config.get_content_file_path("blog.aspose.net", "", "en")
        expected = os.path.join("D:\\content", "blog.aspose.net", "index.md")
        assert path == expected

    def test_empty_page_path_folder_based(self, config):
        """Test empty page path for folder-based subdomain."""
        path = config.get_content_file_path("docs.aspose.net", "", "en")
        expected = os.path.join("D:\\content", "docs.aspose.net", "en", "_index.md")
        assert path == expected

    def test_trailing_slashes_stripped(self, config):
        """Test that trailing slashes are stripped correctly."""
        path1 = config.get_content_file_path("docs.aspose.net", "getting-started", "en")
        path2 = config.get_content_file_path("docs.aspose.net", "/getting-started/", "en")
        path3 = config.get_content_file_path("docs.aspose.net", "//getting-started//", "en")
        assert path1 == path2 == path3

    def test_nested_path(self, config):
        """Test nested page paths."""
        path = config.get_content_file_path(
            "docs.aspose.net",
            "/developer-guide/advanced/api-reference/",
            "fr"
        )
        expected = os.path.join(
            "D:\\content", "docs.aspose.net", "fr",
            "developer-guide", "advanced", "api-reference.md"
        )
        assert path == expected

    def test_path_with_md_extension(self, config):
        """Test page path that already has .md extension."""
        path = config.get_content_file_path("docs.aspose.net", "/page.md", "en")
        expected = os.path.join("D:\\content", "docs.aspose.net", "en", "page.md")
        assert path == expected


class TestExtractSubdomain:
    """Test extract_subdomain() method."""

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return HugoConfig(content_path="/test")

    def test_https_url(self, config):
        """Test extraction from HTTPS URL."""
        assert config.extract_subdomain("https://blog.aspose.net") == "blog.aspose.net"
        assert config.extract_subdomain("https://docs.aspose.net/") == "docs.aspose.net"

    def test_http_url(self, config):
        """Test extraction from HTTP URL."""
        assert config.extract_subdomain("http://blog.aspose.net") == "blog.aspose.net"

    def test_sc_domain_format(self, config):
        """Test extraction from GSC sc-domain format."""
        assert config.extract_subdomain("sc-domain:aspose.net") == "aspose.net"
        assert config.extract_subdomain("sc-domain:blog.aspose.net") == "blog.aspose.net"

    def test_bare_domain(self, config):
        """Test extraction from bare domain (no protocol)."""
        assert config.extract_subdomain("blog.aspose.net") == "blog.aspose.net"
        assert config.extract_subdomain("docs.aspose.net") == "docs.aspose.net"

    def test_url_with_path(self, config):
        """Test extraction from URL with path."""
        assert config.extract_subdomain("https://blog.aspose.net/posts/article") == "blog.aspose.net"

    def test_empty_input(self, config):
        """Test handling of empty input."""
        assert config.extract_subdomain("") == ""
        assert config.extract_subdomain(None) == ""

    def test_case_normalization(self, config):
        """Test that subdomain is normalized to lowercase."""
        assert config.extract_subdomain("https://BLOG.Aspose.NET") == "blog.aspose.net"


class TestIsConfigured:
    """Test is_configured() method."""

    def test_configured(self):
        """Test with valid configuration."""
        config = HugoConfig(content_path="/valid/path")
        assert config.is_configured() is True

    def test_not_configured_empty(self):
        """Test with empty content path."""
        config = HugoConfig(content_path="")
        assert config.is_configured() is False

    def test_not_configured_whitespace(self):
        """Test with whitespace-only content path."""
        config = HugoConfig(content_path="   ")
        assert config.is_configured() is False


class TestValidatePath:
    """Test validate_path() method."""

    def test_valid_path(self):
        """Test with valid existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = HugoConfig(content_path=tmpdir)
            assert config.validate_path() is None

    def test_not_configured(self):
        """Test with empty path."""
        config = HugoConfig(content_path="")
        error = config.validate_path()
        assert error is not None
        assert "not configured" in error

    def test_nonexistent_path(self):
        """Test with non-existent path."""
        config = HugoConfig(content_path="/this/path/does/not/exist/12345")
        error = config.validate_path()
        assert error is not None
        assert "does not exist" in error

    def test_file_instead_of_directory(self):
        """Test with file path instead of directory."""
        # Create temp file and close it before testing (Windows requires this)
        f = tempfile.NamedTemporaryFile(delete=False)
        temp_path = f.name
        f.close()
        try:
            config = HugoConfig(content_path=temp_path)
            error = config.validate_path()
            assert error is not None
            assert "not a directory" in error
        finally:
            os.unlink(temp_path)


class TestWindowsPaths:
    """Test Windows-specific path handling."""

    def test_windows_path_with_backslashes(self):
        """Test that Windows paths with backslashes work correctly."""
        config = HugoConfig(
            content_path="D:\\onedrive\\Documents\\GitHub\\aspose.net\\content",
            file_localization_subdomains=["blog.aspose.net"],
            default_locale="en"
        )

        path = config.get_content_file_path("blog.aspose.net", "/posts/article/", "es")

        # Should contain the content path
        assert "D:" in path or "onedrive" in path
        assert "blog.aspose.net" in path
        assert "index.es.md" in path

    def test_mixed_separators(self):
        """Test handling of mixed path separators."""
        config = HugoConfig(
            content_path="D:/content",
            file_localization_subdomains=["blog.test.com"],
            default_locale="en"
        )

        # Should work regardless of input separator style
        path = config.get_content_file_path("blog.test.com", "posts/article", "en")
        assert "blog.test.com" in path
        assert "index.md" in path
