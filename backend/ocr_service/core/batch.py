"""
Batch Capture Processor — Queue-based concurrent scanner for bulk arrivals.

Optimized for:
  - Land Border Checkpoints: Full bus arrivals (30–60 passengers)
  - Sea Passenger Checkpoints: Ferry & Cruise disembarkation queues (50–200 passengers)

Processes scans concurrently with bounded semaphore to avoid memory exhaustion,
isolating individual document failures so the bulk line is never blocked.
"""

import asyncio
from typing import Sequence
from backend.logging_config import get_logger
from backend.ocr_service.core.classifier import classify_document
from backend.ocr_service.core.field_extractor import (
    extract_fields,
    extract_raw_ocr_lines,
)
from backend.ocr_service.core.llm_fallback import extract_fields_with_llm
from backend.ocr_service.core.mrz_parser import parse_mrz
from backend.ocr_service.schemas.extraction import (
    BatchExtractionResponse,
    BatchItemResult,
    CheckpointType,
    DocumentType,
    ExtractedField,
    ExtractionMethod,
    ExtractionResponse,
    MRZResult,
)

logger = get_logger("ocr_service.batch")


async def process_single_item(
    index: int,
    image_bytes: bytes,
    filename: str | None,
    document_type_hint: DocumentType | None,
    checkpoint_type: CheckpointType,
    provider: str,
    semaphore: asyncio.Semaphore,
) -> BatchItemResult:
    """Process a single document in a batch run under a concurrency semaphore."""
    async with semaphore:
        try:
            if not image_bytes or len(image_bytes) == 0:
                return BatchItemResult(
                    index=index,
                    filename=filename,
                    success=False,
                    error="Empty image bytes provided",
                )

            # 1. OCR text extraction
            raw_ocr_lines = []
            try:
                raw_ocr_lines = extract_raw_ocr_lines(image_bytes)
            except Exception as e:
                logger.warning("Batch OCR item text extraction failed", index=index, error=str(e))

            text_only_lines = [text for text, _ in raw_ocr_lines]

            # 2. Determine Document Type (Classification or Hint)
            if document_type_hint:
                doc_type = document_type_hint
            else:
                doc_type, conf, _ = classify_document(
                    image_bytes,
                    ocr_lines=raw_ocr_lines,
                    provider=provider,
                )

            warnings: list[str] = []
            extracted_fields: dict[str, ExtractedField] = {}
            primary_method = ExtractionMethod.OCR

            # 3. Parse MRZ
            mrz_res: MRZResult = parse_mrz(image_bytes, ocr_text_lines=text_only_lines)
            if mrz_res.mrz_present:
                primary_method = ExtractionMethod.MRZ
                for key, val in mrz_res.mrz_fields.items():
                    if val and key != "mrz_format":
                        extracted_fields[key] = ExtractedField(
                            field_name=key,
                            field_value=val,
                            confidence=1.0 if mrz_res.checksum_valid else 0.7,
                            extraction_method=ExtractionMethod.MRZ,
                        )
                if not mrz_res.checksum_valid:
                    warnings.append(
                        f"MRZ checksum verification failed on: {', '.join(mrz_res.checksum_failures)}"
                    )

            # 4. Extract Visual Zone Fields
            ocr_fields = extract_fields(image_bytes, doc_type, raw_lines=raw_ocr_lines)
            for field in ocr_fields:
                if field.field_name not in extracted_fields:
                    extracted_fields[field.field_name] = field

            # 5. Fallback check
            _sparse_non_mrz = (
                doc_type in [
                    DocumentType.DRIVING_LICENSE,
                    DocumentType.PERMIT,
                    DocumentType.FERRY_TICKET,
                    DocumentType.NATIONAL_ID,
                    DocumentType.PAN_CARD,
                    DocumentType.VOTER_ID,
                ]
                and len(extracted_fields) < 3
            )
            if (not extracted_fields and not mrz_res.mrz_present) or _sparse_non_mrz:
                llm_type, llm_fields = extract_fields_with_llm(
                    image_bytes=image_bytes,
                    document_type=doc_type,
                )
                if llm_fields:
                    if llm_type and not document_type_hint:
                        doc_type = llm_type
                    if not extracted_fields:
                        primary_method = ExtractionMethod.LLM
                    for f in llm_fields:
                        if f.field_name not in extracted_fields:
                            extracted_fields[f.field_name] = f

            if not extracted_fields and not mrz_res.mrz_present:
                return BatchItemResult(
                    index=index,
                    filename=filename,
                    success=False,
                    error="Unable to detect text or MRZ in document image",
                )

            res = ExtractionResponse(
                document_type=doc_type,
                checkpoint_type=checkpoint_type,
                provider_used=provider,
                extraction_method=primary_method,
                fields=list(extracted_fields.values()),
                mrz=mrz_res,
                warnings=warnings,
            )

            return BatchItemResult(
                index=index,
                filename=filename,
                success=True,
                result=res,
            )

        except Exception as exc:
            logger.error("Batch processing failed for item", index=index, error=str(exc))
            return BatchItemResult(
                index=index,
                filename=filename,
                success=False,
                error=str(exc),
            )


async def process_batch_queue(
    items: Sequence[tuple[bytes, str | None, DocumentType | None]],
    checkpoint_type: CheckpointType = CheckpointType.LAND_BORDER,
    provider: str = "local",
    max_concurrency: int = 4,
) -> BatchExtractionResponse:
    """
    Process a list of image items in parallel with a bounded concurrency pool.
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = [
        process_single_item(
            index=i,
            image_bytes=item[0],
            filename=item[1],
            document_type_hint=item[2],
            checkpoint_type=checkpoint_type,
            provider=provider,
            semaphore=semaphore,
        )
        for i, item in enumerate(items)
    ]

    results: list[BatchItemResult] = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    logger.info(
        "Batch queue processing finished",
        total=len(results),
        successful=successful,
        failed=failed,
        checkpoint=checkpoint_type.value,
    )

    return BatchExtractionResponse(
        total_processed=len(results),
        successful_count=successful,
        failed_count=failed,
        checkpoint_type=checkpoint_type,
        items=results,
    )
