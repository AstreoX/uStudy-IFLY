"""回填 document_chunks.content_tsv 列（使用 jieba 分词）

部署后运行一次：
    docker compose exec backend python scripts/backfill_tsvector.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from db.database import get_scoped_session
from rag.retrieval.text_segmentation import segment_for_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def backfill() -> None:
    """分批回填 content_tsv 列，使用 jieba 分词。"""
    total_updated = 0

    while True:
        async with get_scoped_session() as db:
            # 查询一批未回填（或需要用 jieba 重新分词）的 chunks
            result = await db.execute(
                text(
                    """
                    SELECT id, content FROM document_chunks
                    ORDER BY id
                    LIMIT :batch_size
                    OFFSET :offset
                    """
                ),
                {"batch_size": BATCH_SIZE, "offset": total_updated},
            )
            rows = result.fetchall()

            if not rows:
                break

            for row in rows:
                segmented = segment_for_search(row.content)
                await db.execute(
                    text(
                        """
                        UPDATE document_chunks
                        SET content_tsv = to_tsvector('simple', :segmented)
                        WHERE id = :chunk_id
                        """
                    ),
                    {"segmented": segmented, "chunk_id": row.id},
                )

            await db.commit()
            total_updated += len(rows)
            logger.info("已回填 %d 条 chunks", total_updated)

    logger.info("回填完成，共处理 %d 条 chunks", total_updated)


if __name__ == "__main__":
    asyncio.run(backfill())
