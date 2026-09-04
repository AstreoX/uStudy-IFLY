#!/usr/bin/env python
"""One-time script: reprocess all space_documents through the new plaintext pipeline.

Run after applying the plaintext_rag_v1 migration.

Usage:
    cd uStudy-backend
    python scripts/reprocess_documents.py
    python scripts/reprocess_documents.py --dry-run
    python scripts/reprocess_documents.py --space-id <uuid>
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

# Allow running from uStudy-backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import AsyncSessionLocal
from db.models import SpaceDocument, DocumentText
from rag.service import DocumentProcessingService
from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def reprocess_all(dry_run: bool = False, space_id: UUID | None = None) -> None:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(SpaceDocument)
            .outerjoin(DocumentText, DocumentText.document_id == SpaceDocument.id)
            .where(DocumentText.id.is_(None))
        )
        if space_id:
            stmt = stmt.where(SpaceDocument.space_id == space_id)

        result = await db.execute(stmt)
        docs = result.scalars().all()

    logger.info("Found %d documents to reprocess", len(docs))
    if dry_run:
        for doc in docs:
            logger.info("[DRY RUN] Would reprocess: %s (%s)", doc.title, doc.id)
        return

    success = 0
    failed = 0
    for doc in docs:
        logger.info("Reprocessing: %s (%s)", doc.title, doc.id)
        try:
            async with AsyncSessionLocal() as db:
                service = DocumentProcessingService(db)
                await service.process_document(doc.id)
            success += 1
        except Exception as exc:
            logger.error("Failed: %s - %s", doc.id, exc)
            failed += 1

    logger.info("Done. success=%d failed=%d", success, failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reprocess documents through plaintext pipeline")
    parser.add_argument("--dry-run", action="store_true", help="List documents without processing")
    parser.add_argument("--space-id", type=UUID, help="Limit to a specific space UUID")
    args = parser.parse_args()

    asyncio.run(reprocess_all(dry_run=args.dry_run, space_id=args.space_id))


if __name__ == "__main__":
    main()
