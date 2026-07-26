"""Per-session transcripts — an append-only JSONL record of each session.

Where the audit ledger records *data changes*, the transcript records the
*interaction*: the human's request, questions and answers, tool calls, proposed
and approved deltas, and outcomes. One file per session under the transcript
directory.
"""
