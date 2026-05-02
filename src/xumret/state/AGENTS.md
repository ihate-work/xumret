# state

Command lifecycle tracking and result collection.

## manager.py

`StateManager` — holds an `Executor` (via protocol, not concrete type). Tracks all submitted commands, their current state, and results. Provides the data layer that `api/` queries.

Responsibilities:
- Assign command IDs
- Delegate to `Executor.submit` / `cancel` / `query_daemon` / `end_daemon`
- Cache results for API queries
- Emit events for SSE subscribers (new command, status change, completion)
