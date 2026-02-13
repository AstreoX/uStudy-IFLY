"""Clean up orphan attachments (not attached to any message) older than 24 hours"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import MessageAttachment
from upload.storage import get_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_orphan_attachments() -> None:
    """
    Clean up orphan attachments older than 24 hours.

    Orphan attachments are attachments that were uploaded but never
    associated with a message (message_id is NULL).

    This can happen if:
    - User uploads attachment but never sends the message
    - User closes the app before sending
    - Network error during message sending
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    storage = get_storage()

    async with AsyncSessionLocal() as db:
        # Find orphan attachments older than 24 hours
        result = await db.execute(
            select(MessageAttachment).where(
                MessageAttachment.message_id.is_(None),
                MessageAttachment.created_at < cutoff_time,
            )
        )
        orphans = result.scalars().all()

        if not orphans:
            logger.info("No orphan attachments found")
            return

        logger.info(f"Found {len(orphans)} orphan attachments to clean up")

        deleted_count = 0
        failed_count = 0

        for attachment in orphans:
            try:
                # Delete files from storage
                await storage.delete(attachment.file_url)
                if attachment.thumbnail_url:
                    await storage.delete(attachment.thumbnail_url)

                # Delete database record
                await db.delete(attachment)

                deleted_count += 1
                logger.debug(
                    f"Deleted orphan attachment {attachment.id} "
                    f"(created at {attachment.created_at})"
                )

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to delete orphan attachment {attachment.id}: {e}",
                    exc_info=True,
                )

        # Commit all deletions
        await db.commit()

        logger.info(
            f"Cleanup completed: {deleted_count} deleted, {failed_count} failed"
        )


async def main() -> None:
    """Main entry point"""
    logger.info("Starting orphan attachment cleanup")
    try:
        await cleanup_orphan_attachments()
        logger.info("Cleanup finished successfully")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
