# Dependency Injection Package

"""Dependency injection infrastructure for tdoc-crawler.

This package provides the ServiceContainer for centralized service lifecycle management.
"""

from tdoc_crawler.di.container import ServiceContainer

__all__ = ["ServiceContainer"]
