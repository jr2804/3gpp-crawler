"""Tests for hybrid converter with unoserver support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from convert_lo.converter import HAS_UNOSERVER, Converter
from convert_lo.exceptions import ConversionError
from convert_lo.formats import LibreOfficeFormat


class TestConverterServerMode:
    """Tests for Converter server mode configuration."""

    def test_converter_init_cli_mode(self) -> None:
        """Initialize with CLI mode forced."""
        converter = Converter(server_mode="cli")

        assert converter.server_mode == "cli"
        assert converter.is_using_server is False

    def test_converter_init_auto_mode(self) -> None:
        """Initialize with auto mode (default)."""
        converter = Converter(server_mode="auto")

        assert converter.server_mode == "auto"

    def test_converter_init_server_mode_no_server(self) -> None:
        """Initialize with server mode but no server available."""
        with patch("convert_lo.converter.is_server_running", return_value=False):
            # Should not raise in auto mode, just use CLI
            converter = Converter(server_mode="auto")
            assert converter.is_using_server is False

    def test_converter_init_server_mode_required(self) -> None:
        """Raise error when server mode required but unavailable."""
        with patch("convert_lo.converter.is_server_running", return_value=False):
            with pytest.raises(ConversionError, match="Unoserver required but not available"):
                Converter(server_mode="server")

    def test_converter_init_with_auto_start(self) -> None:
        """Auto-start server when configured."""
        mock_manager = MagicMock()

        with (
            patch("convert_lo.converter.is_server_running", return_value=False),
            patch("convert_lo.converter.ServerManager", return_value=mock_manager),
        ):
            Converter(
                server_mode="auto",
                auto_start_server=True,
            )

            mock_manager.start.assert_called_once()

    def test_converter_init_auto_start_fallback_to_cli(self) -> None:
        """Fallback to CLI when auto-start fails."""
        mock_manager = MagicMock()
        mock_manager.start.side_effect = ConversionError("Failed to start")

        with (
            patch("convert_lo.converter.is_server_running", return_value=False),
            patch("convert_lo.converter.ServerManager", return_value=mock_manager),
        ):
            converter = Converter(
                server_mode="auto",
                auto_start_server=True,
            )

            # Should not raise, just use CLI
            assert converter.is_using_server is False


@pytest.mark.skipif(not HAS_UNOSERVER, reason="unoserver not installed")
class TestConverterWithServer:
    """Tests for Converter with unoserver client."""

    def test_convert_uses_server_when_available(self, tmp_path: Path) -> None:
        """Use server for conversion when available."""
        input_file = tmp_path / "test.docx"
        input_file.write_bytes(b"test content")
        output_dir = tmp_path / "output"

        mock_client = MagicMock()

        with patch("convert_lo.converter.is_server_running", return_value=True), patch("convert_lo.converter.UnoClient", return_value=mock_client):
            converter = Converter(server_mode="server")

            assert converter.is_using_server is True

            converter.convert(input_file, "pdf", output_dir)

            mock_client.convert.assert_called_once()

    def test_convert_server_fallback_to_cli(self, tmp_path: Path) -> None:
        """Fallback to CLI when server conversion fails."""
        input_file = tmp_path / "test.docx"
        input_file.write_bytes(b"test content")
        output_dir = tmp_path / "output"

        mock_client = MagicMock()
        mock_client.convert.side_effect = Exception("Server error")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with (
            patch("convert_lo.converter.is_server_running", return_value=True),
            patch("convert_lo.converter.UnoClient", return_value=mock_client),
            patch("convert_lo.converter.subprocess.run", return_value=mock_result),
        ):
            converter = Converter(server_mode="server")

            # Should not raise, falls back to CLI
            result = converter.convert(input_file, "pdf", output_dir)

            assert result.output_format == LibreOfficeFormat.PDF
            # Both server and CLI were attempted
            mock_client.convert.assert_called_once()

    def test_convert_batch_uses_server(self, tmp_path: Path) -> None:
        """Batch conversion uses server when available."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"

        test_files = [input_dir / f"test_{i}.docx" for i in range(3)]
        for f in test_files:
            f.write_bytes(b"test")

        mock_client = MagicMock()

        with (
            patch("convert_lo.converter.is_server_running", return_value=True),
            patch("convert_lo.converter.UnoClient", return_value=mock_client),
        ):
            converter = Converter(server_mode="server")

            results = converter.convert_batch(test_files, LibreOfficeFormat.PDF, output_dir)

            assert len(results) == 3
            assert mock_client.convert.call_count == 3


class TestConverterContextManager:
    """Tests for Converter context manager."""

    def test_converter_context_manager_auto_start(self, tmp_path: Path) -> None:
        """Start/stop server in context manager."""
        mock_manager = MagicMock()

        with (
            patch("convert_lo.converter.is_server_running", return_value=False),
            patch("convert_lo.converter.ServerManager", return_value=mock_manager),
        ):
            with Converter(
                server_mode="auto",
                auto_start_server=True,
            ):
                # Server should be started
                assert mock_manager.start.called

            # Server should be stopped after context exit
            mock_manager.stop.assert_called_once()

    def test_converter_context_manager_no_auto_start(self, tmp_path: Path) -> None:
        """Don't start server without auto_start."""
        with patch("convert_lo.converter.is_server_running", return_value=False), Converter(server_mode="auto", auto_start_server=False):
            pass

            # No manager should be created


class TestConverterServerDetection:
    """Tests for server detection logic."""

    def test_converter_detects_running_server(self) -> None:
        """Detect and use running server in auto mode."""
        with patch("convert_lo.converter.is_server_running", return_value=True), patch("convert_lo.converter.UnoClient") as mock_client_class:
            converter = Converter(server_mode="auto")

            assert converter.is_using_server is True
            mock_client_class.assert_called_once()

    def test_converter_falls_back_to_cli(self) -> None:
        """Fall back to CLI when server unavailable in auto mode."""
        with patch("convert_lo.converter.is_server_running", return_value=False):
            converter = Converter(server_mode="auto")

            assert converter.is_using_server is False

    def test_converter_unoserver_not_installed(self) -> None:
        """Handle case when unoserver is not installed."""
        try:
            with patch("convert_lo.converter.HAS_UNOSERVER", False):
                converter = Converter(server_mode="auto")

                # Should use CLI mode
                assert converter.is_using_server is False
        finally:
            # Restore original value
            pass
