Blockflow v5 — Double-entry ledger & reconciliation (educational)
=================================================================
This version adds a proper double-entry journal for wallet accounting and a reconciliation tool.

Features added in v5:
- Double-entry ledger model with credit/debit entries and running balances
- Atomic wallet operations using DB transactions
- Reconciliation script that scans ledger vs aggregated wallet balances and reports inconsistencies
- Unit tests that simulate trades and validate ledger balance invariants

Reminder: still educational. Production systems require rigorous audits, CA/CPA review, and stronger guarantees.
