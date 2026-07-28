# Uniform Agri Collection Progress Logging

## Goal

Show useful progress while the Uniform Agri job fetches cow details or milk
recordings for a large herd.

## Design

The detail and milking collectors will accept an optional progress callback.
The command script will provide a callback that logs when a stage starts, after
every 50 processed cows, and when the stage completes. Progress messages include
the stage name, processed count, total count, collected records, skipped records,
and failures where relevant.

The default interval is 50 cows. Existing callers that do not provide a callback
retain their current behavior.

## Error Handling

Existing per-animal error handling remains unchanged. Failed animals are counted
in progress and completion messages, and are still reported individually by the
command script.

## Testing

Collector tests will verify that progress is reported at the configured interval
and at completion. Script tests will verify that it logs the stage milestones.
