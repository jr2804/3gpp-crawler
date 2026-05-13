"""Docling pipeline options — profile-driven accelerator and model config."""

from __future__ import annotations

from typing import Literal

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions, PipelineOptions

from tdoc_crawler.extraction.profiles import ExtractionProfile


def _build_pipeline_options(
    profile: ExtractionProfile,
    *,
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto",
    docx_direct: bool = False,
) -> PdfPipelineOptions | PipelineOptions:
    """Build Docling pipeline options for the given extraction profile.

    Args:
        profile: Extraction profile level.
        device: Accelerator device (auto, cpu, cuda, mps).
        docx_direct: If True, return simpler ``PipelineOptions`` (no ML models)
            for direct DOCX-to-Docling conversion.

    Returns:
        ``PdfPipelineOptions`` (ML pipeline) or ``PipelineOptions`` (docx-direct).
    """
    if docx_direct:
        return PipelineOptions()

    pipeline_opts = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device),
    )

    if profile in [ExtractionProfile.ADVANCED, ExtractionProfile.DEFAULT]:
        # Optimise for limited VRAM (8 GB): smaller images, reduced batching, no OCR
        pipeline_opts.images_scale = 1.5
        pipeline_opts.layout_batch_size = 2
        pipeline_opts.table_batch_size = 2
        pipeline_opts.ocr_batch_size = 2
        pipeline_opts.do_ocr = False
        # Extract figure images so they can be referenced in markdown output.
        pipeline_opts.generate_picture_images = True

    if profile == ExtractionProfile.ADVANCED:
        pipeline_opts.do_picture_description = True
        pipeline_opts.do_code_enrichment = True
        pipeline_opts.do_formula_enrichment = True

    return pipeline_opts
