"""Built-in task definitions for the background worker system.

Registers all standard tasks that can be executed by workers.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_builtin_tasks():
    """Register all built-in background tasks."""
    from lab_manager.tasks.worker import get_task_manager

    tm = get_task_manager()

    # --- Search indexing tasks ---

    def reindex_entity(entity: str = "all", entity_id: int | None = None):
        """Re-index entities in Meilisearch."""
        try:
            from lab_manager.database import get_db_session

            with get_db_session() as db:
                from lab_manager.services.search import (
                    get_search_client,
                    index_documents,
                )

                client = get_search_client()
                if client is None:
                    return {"status": "skipped", "reason": "meilisearch unavailable"}

                # Import models for indexing
                indexed = 0
                entities_to_index = (
                    [entity] if entity != "all" else ["vendors", "products", "orders"]
                )

                for ent in entities_to_index:
                    try:
                        indexed += index_documents(client, db, ent, entity_id)
                    except Exception:
                        logger.warning("Failed to index %s", ent, exc_info=True)

                return {"status": "ok", "indexed": indexed}
        except Exception as exc:
            logger.error("Reindex failed: %s", exc)
            raise

    tm.register("reindex_search", reindex_entity, max_retries=2, priority=2)

    # --- Cache invalidation tasks ---

    def invalidate_cache(namespace: str = "all"):
        """Invalidate cache entries."""
        from lab_manager.cache import cache_invalidate_prefix

        if namespace == "all":
            for ns in ["vendors", "products", "orders", "inventory", "analytics"]:
                cache_invalidate_prefix(ns)
            return {"status": "ok", "namespaces": "all"}
        else:
            count = cache_invalidate_prefix(namespace)
            return {"status": "ok", "namespace": namespace, "deleted": count}

    tm.register("invalidate_cache", invalidate_cache, max_retries=1, priority=1)

    # --- Alert check tasks ---

    def check_alerts():
        """Run alert checks for low stock, expiring items, etc."""
        try:
            from lab_manager.database import get_db_session

            with get_db_session() as db:
                from lab_manager.services.alerts import check_all_alerts

                results = check_all_alerts(db)
                return {"status": "ok", "alerts": len(results)}
        except Exception as exc:
            logger.error("Alert check failed: %s", exc)
            raise

    tm.register("check_alerts", check_alerts, max_retries=2, priority=2)

    # --- Analytics aggregation ---

    def aggregate_analytics(period: str = "daily"):
        """Aggregate analytics data for dashboards."""
        try:
            from lab_manager.database import get_db_session

            with get_db_session() as db:
                from lab_manager.services.analytics import (
                    get_dashboard_stats,
                )

                stats = get_dashboard_stats(db)
                # Cache the results
                from lab_manager.cache import cache_set

                cache_set("analytics", f"dashboard_{period}", stats, ttl=900)
                return {"status": "ok", "period": period}
        except Exception as exc:
            logger.error("Analytics aggregation failed: %s", exc)
            raise

    tm.register("aggregate_analytics", aggregate_analytics, max_retries=1, priority=3)

    # --- Database maintenance ---

    def db_maintenance(action: str = "vacuum_analyze"):
        """Run database maintenance tasks."""
        try:
            from sqlalchemy import text

            from lab_manager.database import get_engine

            engine = get_engine()
            if action == "vacuum_analyze":
                # VACUUM ANALYZE requires autocommit
                with engine.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as conn:
                    conn.execute(text("VACUUM ANALYZE"))
                return {"status": "ok", "action": action}
            return {"status": "skipped", "reason": f"unknown action: {action}"}
        except Exception as exc:
            logger.error("DB maintenance failed: %s", exc)
            raise

    tm.register("db_maintenance", db_maintenance, max_retries=1, priority=3)

    logger.info("Registered %d built-in tasks", 5)
