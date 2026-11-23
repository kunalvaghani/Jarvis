"""Explicit metadata for the existing Google file tools. No new Google executor."""
READ_TOOLS = frozenset({'google_drive_search', 'google_drive_read'})
CONTRACTS = {
    # local_or_network retains local-private provenance in the existing registry, including cached file results.
    'google_drive_search': (('query:Query',), ('files:Report',), 'read_only', 'local_or_network'),
    'google_drive_read': (('file_id:Text',), ('content:Report',), 'read_only', 'local_or_network'),
    'google_docs_create': (('plan:Plan',), ('document:Document',), 'external_write', 'local_or_network'),
    'google_sheets_create': (('plan:Plan',), ('sheet:Spreadsheet',), 'external_write', 'local_or_network'),
    'google_drive_save_file': (('plan:Plan',), ('artifact:Report',), 'external_write', 'local_or_network'),
    'google_drive_upload': (('path:FilePath',), ('artifact:Report',), 'external_write', 'local_or_network'),
}
