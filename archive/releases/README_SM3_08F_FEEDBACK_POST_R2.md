# SM3 08F — Feedback POST R2

Fix: explicit UTF-8 JSON body for Windows PowerShell 5.1.

The original script produced valid JSON text but sent the .NET string using a
Windows legacy encoding. The body contains non-ASCII brand text, so FastAPI
could reject the request before Pydantic validation with:

`{"detail":"There was an error parsing the body"}`

R2 serializes the payload, validates it locally, converts it to UTF-8 bytes and
sends `Content-Type: application/json; charset=utf-8`.

SHA-256:
`54acd19ea7f149e979f8ed9fb25427ade5392e5b7cdd2b7ff4e5b9087fcc6937`
