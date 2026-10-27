# Durable recovery and bounded correction

View management now permits at most 50 distinct eviction IDs per response. Visible rows remain unless explicitly evicted; restoration selects only advertised stored rows outside the view. A rejected response makes no view/evidence/cursor changes and receives one corrective attempt within the existing model-call budget. Large eviction lists were reduced to avoid the truncation seen in the baseline.

Provider timeouts, connection failures, HTTP 429 and selected transient 5xx failures receive one retry after 20 seconds. Repeated failure saves an interruption record and exits. Calls with unknown provider usage retain conservative reservations. This is bounded recovery, not an unlimited retry loop or a guarantee that a provider quota will become available.

The chunk journal stores original evidence/frontier boundaries, batches, view-event offset, pending batch position and handoff reason. A page commit saves its receipt reference, cursor, evidence, working view and batch position atomically. Resuming skips committed pages and keeps the original chunk-start artifact. A saved response that has not been applied is reused after request matching; it is not sent to the provider again.

To resume a newly journaled case after inspecting its interruption, use `python3 chunk_case.py segment CASE_DIRECTORY` with the original database and model setup. Continue segments until the case reaches a frontier or resource boundary, then run review. All retries consume the existing case call allowance. Use a budget-aware harness when shared pilot token accounting is required; invoking the standalone command does not attach the pilot's shared budget ledger.

The auditor independently checks source rows, cursors, view transitions and rejected/transport-failure snapshots. It proves rejection from the saved schema, response and semantic rules; it does not trust a rejected flag by itself. An open paused chunk remains uncertifiable until resumed and closed. The original failed v1 cases predate the journal and must not be silently resumed as if they had complete histories.

Validation includes real saved invalid responses, interruption after page commit, unapplied saved responses, exhausted provider retries, rejected semantic actions and independent replay after recovery. These checks concern execution correctness, not laundering detection accuracy.
