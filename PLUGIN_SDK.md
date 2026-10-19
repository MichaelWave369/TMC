# Plugin and extension contracts

The current implementation contains plugin manifests, permission requests, enable/disable operations and integration hooks under `app/plugins/` and `app/connectors/`.

Treat extensions and their inputs as untrusted until reviewed; a permission name or approval record is not a replacement for process isolation or an authenticated server perimeter. Read and test the implementation before enabling any third-party extension.
