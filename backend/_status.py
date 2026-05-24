from app.services import search_indexer
s = search_indexer.status()
lr = s.get("last_result", {}) or {}
print(f"status={s.get('status')}")
print(f"last_status={lr.get('status')} items={lr.get('itemsProcessed')} failed={lr.get('itemsFailed')} warnings={len(lr.get('warnings',[]) or [])}")
print(f"start={lr.get('startTime')} end={lr.get('endTime')}")
print(f"history_count={s.get('execution_history_count')}")
