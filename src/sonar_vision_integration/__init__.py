"""Integration and end-to-end harness for #27 (requires the `api` and `api-dev` extras).

Connects the real pieces (HTTPS server, authentication, API, VisionService,
contract validation, local audio model) with deterministic simulated backends.
It complements, and does not replace, each module's unit tests or the
glasses simulator client of #30. Nothing here validates hardware.
"""
