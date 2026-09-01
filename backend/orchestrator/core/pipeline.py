"""
Orchestration Pipeline — End-to-end execution of the document screening workflow.

Routes all document screening requests through the LangGraph StateGraph DAG engine.
"""

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import CheckpointType, DocumentType
from backend.orchestrator.core.langgraph_pipeline import run_langgraph_pipeline
from backend.orchestrator.schemas.pipeline import PipelineResult

logger = get_logger("orchestrator.pipeline")


async def run_pipeline(
    image_bytes: bytes,
    document_type: DocumentType = DocumentType.PASSPORT,
    checkpoint_type: CheckpointType = CheckpointType.AIRPORT,
    provider: str = "local",
    live_image_bytes: bytes | None = None,
    document_id: str | None = None,
    checkpoint_id: str | None = None,
) -> PipelineResult:
    """
    Execute the full end-to-end document screening pipeline using the LangGraph StateGraph.
    """
    return await run_langgraph_pipeline(
        image_bytes=image_bytes,
        document_type=document_type,
        checkpoint_type=checkpoint_type,
        provider=provider,
        live_image_bytes=live_image_bytes,
        document_id=document_id,
        checkpoint_id=checkpoint_id,
    )
