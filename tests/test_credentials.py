"""Tests for credentials resolution with TDocCrawlerConfig integration."""

from __future__ import annotations

import pytest

from tdoc_crawler.config.settings import CredentialsConfig
from tdoc_crawler.credentials import resolve_credentials


class TestCredentialsWithConfig:
    """Test credentials resolution with CredentialsConfig."""

    def test_resolve_uses_config_credentials(self) -> None:
        """resolve_credentials uses credentials_config when no CLI params."""
        config: CredentialsConfig = CredentialsConfig(username="config_user", password="config_pass")

        result = resolve_credentials(credentials_config=config)

        assert result is not None
        assert result.username == "config_user"
        assert result.password == "config_pass"  # noqa: S105

    def test_resolve_cli_overrides_config(self) -> None:
        """CLI parameters take precedence over credentials_config."""
        config: CredentialsConfig = CredentialsConfig(username="config_user", password="config_pass")

        result = resolve_credentials(
            username="cli_user",
            password="cli_pass",
            credentials_config=config,
        )

        assert result.username == "cli_user"
        assert result.password == "cli_pass"  # noqa: S105

    def test_resolve_config_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """credentials_config takes precedence over env vars."""
        monkeypatch.setenv("TDC_EOL_USERNAME", "env_user")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "env_pass")
        config = CredentialsConfig(username="config_user", password="config_pass")

        result = resolve_credentials(credentials_config=config)

        # Config should win over env
        assert result.username == "config_user"
        assert result.password == "config_pass"  # noqa: S105

    def test_resolve_env_when_no_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without credentials_config, falls back to env vars."""
        monkeypatch.setenv("TDC_EOL_USERNAME", "env_user")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "env_pass")

        result = resolve_credentials()

        assert result.username == "env_user"
        assert result.password == "env_pass"  # noqa: S105

    def test_resolve_returns_none_when_no_creds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns None when no credentials found anywhere."""
        # Clear any existing env vars that might interfere
        monkeypatch.delenv("TDC_EOL_USERNAME", raising=False)
        monkeypatch.delenv("TDC_EOL_PASSWORD", raising=False)

        result = resolve_credentials()

        assert result is None

    def test_resolve_config_prompt_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """credentials_config.prompt controls prompting."""
        # Clear env vars that might provide credentials before prompting
        monkeypatch.delenv("TDC_EOL_USERNAME", raising=False)
        monkeypatch.delenv("TDC_EOL_PASSWORD", raising=False)

        config = CredentialsConfig(prompt="true")

        # Should attempt to prompt (but won't in test due to non-TTY)
        result = resolve_credentials(credentials_config=config)

        # Result is None because stdin is not a TTY in tests
        assert result is None


class TestCredentialsResolutionOrder:
    """Test resolution order: CLI > Config > Env > Prompt."""

    def test_full_resolution_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify complete precedence chain."""
        monkeypatch.setenv("TDC_EOL_USERNAME", "env_user")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "env_pass")
        config = CredentialsConfig(username="config_user", password="config_pass")

        result = resolve_credentials(
            credentials_config=config,
            username="cli_user",
            password="cli_pass",
        )

        # CLI should win
        assert result.username == "cli_user"
        assert result.password == "cli_pass"  # noqa: S105

    def test_config_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config values should override env vars."""
        monkeypatch.setenv("TDC_EOL_USERNAME", "env_user")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "env_pass")
        config = CredentialsConfig(username="config_user", password="config_pass")

        result = resolve_credentials(credentials_config=config)

        assert result.username == "config_user"
        assert result.password == "config_pass"  # noqa: S105

    def test_env_beats_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env vars should prevent prompting."""
        monkeypatch.setenv("TDC_EOL_USERNAME", "env_user")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "env_pass")

        # Even with prompt=true, env vars should be used
        result = resolve_credentials(
            credentials_config=CredentialsConfig(prompt="true"),
        )

        assert result is not None
        assert result.username == "env_user"


class TestCredentialsBackwardCompatibility:
    """Test backward compatibility without credentials_config."""

    def test_resolve_with_no_config_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_credentials works without credentials_config parameter."""
        monkeypatch.setenv("TDC_EOL_USERNAME", "legacy_user")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "legacy_pass")

        # Call without credentials_config (old API)
        result = resolve_credentials()

        assert result is not None
        assert result.username == "legacy_user"
        assert result.password == "legacy_pass"  # noqa: S105

    def test_resolve_with_cli_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI-only credentials still work."""
        # Clear any existing env vars
        monkeypatch.delenv("TDC_EOL_USERNAME", raising=False)
        monkeypatch.delenv("TDC_EOL_PASSWORD", raising=False)

        result = resolve_credentials(username="direct_user", password="direct_pass")

        assert result is not None
        assert result.username == "direct_user"
        assert result.password == "direct_pass"  # noqa: S105
