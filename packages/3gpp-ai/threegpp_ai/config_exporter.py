"""Export configuration for 3gpp-ai including crawler and AI settings."""

from __future__ import annotations

import json
from typing import Any, Literal

import yaml
from tdoc_crawler.config.export import ConfigExporter as BaseConfigExporter
from tdoc_crawler.config.settings import ThreeGPPConfig

from threegpp_ai.config import AiConfig

FormatType = Literal["toml", "yaml", "json"]


class ConfigExporter(BaseConfigExporter):
    """Export configuration including AI-specific settings.

    Extends the base ConfigExporter to include AiConfig extraction/runtime
    settings alongside TDocCrawler configuration in a unified flat layout.
    """

    def __init__(
        self,
        crawler_config: ThreeGPPConfig | None = None,
        ai_config: AiConfig | None = None,
        show_secrets: bool = False,
    ):
        """Initialize with crawler and AI config instances.

        Args:
            crawler_config: ThreeGPPConfig instance (uses defaults if None)
            ai_config: AiConfig instance (uses defaults if None)
            show_secrets: If True, show actual API keys instead of placeholders
        """
        super().__init__(config=crawler_config)
        self.ai_config = ai_config or AiConfig()
        self.show_secrets = show_secrets

    def export(self, format: FormatType = "toml", show_secrets: bool | None = None) -> str:
        """Export config to string in specified format with comments.

        Args:
            format: Output format (toml, yaml, json)
            show_secrets: Override instance setting for showing API keys

        Returns:
            Formatted configuration string
        """
        if show_secrets is not None:
            self.show_secrets = show_secrets

        if format == "toml":
            return self._export_toml()
        elif format == "yaml":
            return self._export_yaml()
        elif format == "json":
            return self._export_json()
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _get_all_fields(self) -> dict[str, Any]:
        """Get all fields including AI config sections."""
        fields: dict[str, Any] = {}

        # Get crawler fields with masking for sensitive values
        crawler_fields = self._get_crawler_fields()
        fields.update(crawler_fields)

        # Add AI fields
        ai_config = self.ai_config

        # LLM config
        fields["llm.model"] = {
            "value": self._mask_if_needed("TDC_AI_LLM_API_KEY", ai_config.llm_model),
            "default": ai_config.model_fields["llm_model"].default,
            "description": "LLM model name in <provider>/<model> format",
            "section": "llm",
            "env_var": "TDC_AI_LLM_MODEL",
        }
        fields["llm.api_base"] = {
            "value": ai_config.llm_api_base,
            "default": None,
            "description": "LLM API base URL",
            "section": "llm",
            "env_var": "TDC_AI_LLM_API_BASE",
        }
        fields["llm.api_key"] = {
            "value": self._mask_sensitive("TDC_AI_LLM_API_KEY", ai_config.llm_api_key),
            "default": None,
            "description": "API key for LLM provider",
            "section": "llm",
            "env_var": "TDC_AI_LLM_API_KEY",
            "sensitive": True,
        }

        # Extraction settings
        fields["extraction.tables"] = {
            "value": ai_config.extract_tables,
            "default": True,
            "description": "Enable extraction of table elements",
            "section": "extraction",
            "env_var": "TDC_AI_EXTRACT_TABLES",
        }
        fields["extraction.figures"] = {
            "value": ai_config.extract_figures,
            "default": True,
            "description": "Enable extraction of figure elements",
            "section": "extraction",
            "env_var": "TDC_AI_EXTRACT_FIGURES",
        }
        fields["extraction.equations"] = {
            "value": ai_config.extract_equations,
            "default": True,
            "description": "Enable extraction of equation elements",
            "section": "extraction",
            "env_var": "TDC_AI_EXTRACT_EQUATIONS",
        }
        fields["extraction.figure_description"] = {
            "value": ai_config.figure_description_enabled,
            "default": True,
            "description": "Enable figure description generation with vision-capable models",
            "section": "extraction",
            "env_var": "TDC_AI_FIGURE_DESCRIPTION_ENABLED",
        }

        # Runtime settings
        fields["runtime.convert_pdf"] = {
            "value": ai_config.convert_pdf,
            "default": False,
            "description": "Convert office documents to PDF during processing",
            "section": "runtime",
            "env_var": "TDC_AI_CONVERT_PDF",
        }
        fields["runtime.convert_md"] = {
            "value": ai_config.convert_md,
            "default": False,
            "description": "Extract markdown artifacts during processing",
            "section": "runtime",
            "env_var": "TDC_AI_CONVERT_MD",
        }
        fields["runtime.vlm"] = {
            "value": ai_config.vlm,
            "default": False,
            "description": "Enable VLM picture and formula enrichment",
            "section": "runtime",
            "env_var": "TDC_AI_VLM",
        }
        fields["runtime.device"] = {
            "value": ai_config.device,
            "default": "auto",
            "description": "Device to use for extraction workloads",
            "section": "runtime",
            "env_var": "TDC_AI_DEVICE",
        }
        fields["runtime.num_threads"] = {
            "value": ai_config.num_threads,
            "default": None,
            "description": "Thread count for extraction workloads",
            "section": "runtime",
            "env_var": "TDC_AI_NUM_THREADS",
        }
        fields["runtime.batch_size"] = {
            "value": ai_config.batch_size,
            "default": None,
            "description": "Batch size for OCR/layout/table extraction",
            "section": "runtime",
            "env_var": "TDC_AI_BATCH_SIZE",
        }

        return fields

    def _get_crawler_fields(self) -> dict[str, Any]:
        """Get crawler configuration fields with proper masking of sensitive values."""
        fields: dict[str, Any] = {}
        crawler_config = self.config if hasattr(self, "config") else ThreeGPPConfig()
        crawler_data = crawler_config.model_dump()

        # Path config
        for field_name in ["cache_dir", "db_filename", "checkout_dirname", "ai_cache_dirname"]:
            field_info = type(crawler_config.path).model_fields.get(field_name)
            if field_info:
                value = crawler_data.get("path", {}).get(field_name)
                fields[f"path.{field_name}"] = {
                    "value": value,
                    "default": field_info.default,
                    "description": field_info.description or "",
                    "section": "path",
                }

        # HTTP config
        for field_name in ["cache_ttl", "cache_enabled", "cache_refresh_on_access", "verify_ssl", "max_retries", "timeout"]:
            field_info = type(crawler_config.http).model_fields.get(field_name)
            if field_info:
                value = crawler_data.get("http", {}).get(field_name)
                fields[f"http.{field_name}"] = {
                    "value": value,
                    "default": field_info.default,
                    "description": field_info.description or "",
                    "section": "http",
                }

        # Credentials config (mask sensitive values)
        for field_name in ["username", "password", "prompt"]:
            field_info = type(crawler_config.credentials).model_fields.get(field_name)
            if field_info:
                value = crawler_data.get("credentials", {}).get(field_name)
                # Mask credentials with env var references
                if field_name in ("username", "password") and not self.show_secrets:
                    env_var = f"TDC_EOL_{field_name.upper()}"
                    value = f"${{{env_var}}}" if value else None
                fields[f"credentials.{field_name}"] = {
                    "value": value,
                    "default": field_info.default,
                    "description": field_info.description or "",
                    "section": "credentials",
                    "sensitive": field_name in ("username", "password"),
                }

        # Crawl config
        for field_name in ["working_group", "sub_group", "date_start", "date_end", "source_like", "agenda_like", "title_like", "limit", "workers"]:
            field_info = type(crawler_config.crawl).model_fields.get(field_name)
            if field_info:
                value = crawler_data.get("crawl", {}).get(field_name)
                fields[f"crawl.{field_name}"] = {
                    "value": value,
                    "default": field_info.default,
                    "description": field_info.description or "",
                    "section": "crawl",
                }

        return fields

    def _mask_sensitive(self, env_var: str, value: str | None) -> str | None:
        """Mask sensitive values with environment variable reference.

        Args:
            env_var: Environment variable name
            value: Current value

        Returns:
            ${ENV_VAR} placeholder if show_secrets is False, otherwise actual value
        """
        if value is None:
            return None

        if self.show_secrets:
            return value

        # Return environment variable reference
        return f"${{{env_var}}}"

    def _mask_if_needed(self, env_var: str, value: str) -> str:
        """Mask value if it's sensitive (for non-optional fields)."""
        if self.show_secrets:
            return value
        return value

    def _export_toml(self) -> str:
        """Export to TOML with comments from field descriptions."""
        lines = ["# 3GPP AI Configuration", ""]
        lines.append("# Generated by: 3gpp-ai config init")
        lines.append("#")
        lines.append("# Configuration precedence (highest to lowest):")
        lines.append("# 1. CLI arguments")
        lines.append("# 2. This config file")
        lines.append("# 3. Environment variables (TDC_*)")
        lines.append("# 4. Hard-coded defaults")
        lines.append("#")
        lines.append("# Sensitive values use ${ENV_VAR} syntax for security.")
        lines.append("# Environment variables are interpolated at runtime.")
        lines.append("")

        current_section = None
        fields = self._get_all_fields()

        # Define section order
        section_order = [
            "path",
            "http",
            "credentials",
            "crawl",
            "llm",
            "extraction",
            "runtime",
        ]

        for section in section_order:
            section_fields = [(k, v) for k, v in fields.items() if v["section"] == section]
            if not section_fields:
                continue

            if current_section is not None:
                lines.append("")

            lines.append(f"[{section}]")
            lines.append("")

            for key, meta in section_fields:
                field_name = key.split(".", 1)[1] if "." in key else key
                description = meta["description"]
                value = meta["value"]
                default = meta["default"]
                env_var = meta.get("env_var")

                if description:
                    lines.append(f"# {description}")
                if default is not None:
                    lines.append(f"# Default: {default}")
                if env_var and value is not None and isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    lines.append(f"# Environment: {env_var}")

                formatted_value = self._format_toml_value(value)
                lines.append(f"{field_name} = {formatted_value}")
                lines.append("")

        return "\n".join(lines)

    def _export_yaml(self) -> str:
        """Export to YAML with comments from field descriptions."""
        # Build config dict
        config_data: dict[str, dict[str, Any]] = {}
        fields = self._get_all_fields()

        for key, meta in fields.items():
            section = meta["section"]
            field_name = key.split(".", 1)[1] if "." in key else key

            if section not in config_data:
                config_data[section] = {}

            config_data[section][field_name] = meta["value"]

        # Add header
        lines = [
            "# 3GPP AI Configuration",
            "# Generated by: 3gpp-ai config init",
            "#",
            "# Configuration precedence (highest to lowest):",
            "# 1. CLI arguments",
            "# 2. This config file",
            "# 3. Environment variables (TDC_*)",
            "# 4. Hard-coded defaults",
            "",
        ]

        # Add section comments
        section_comments = {
            "path": "File system paths",
            "http": "HTTP client and caching configuration",
            "credentials": "ETSI Online (EOL) portal credentials",
            "crawl": "Crawling behavior and filter configuration",
            "llm": "LLM configuration",
            "extraction": "Document extraction settings",
            "runtime": "Processing runtime settings",
        }

        yaml_str = yaml.dump(config_data, default_flow_style=False, sort_keys=False)

        result_lines = []
        for line in yaml_str.splitlines():
            stripped = line.rstrip()
            if stripped.endswith(":") and not stripped.startswith("#"):
                section_name = stripped[:-1]
                if section_name in section_comments:
                    result_lines.append(f"# {section_comments[section_name]}")
            result_lines.append(line)

        return "\n".join(lines + result_lines)

    def _export_json(self) -> str:
        """Export to JSON (comments not supported, so just data)."""
        fields = self._get_all_fields()
        config_data: dict[str, dict[str, Any]] = {}

        for key, meta in fields.items():
            section = meta["section"]
            field_name = key.split(".", 1)[1] if "." in key else key

            if section not in config_data:
                config_data[section] = {}

            config_data[section][field_name] = meta["value"]

        # Resolve Path objects to strings
        config_data = self._resolve_paths_for_json(config_data)

        return json.dumps(config_data, indent=2)
