# Install
1. Copy `.env.example` to `.env` and change secrets.
2. `docker compose up -d`.
3. Open n8n, create Google Drive / Metricool / AI credentials.
4. Import `00_RC1_E2E_DRY_RUN.json`.
5. Run DRY RUN first; expected stop: `AWAITING_APPROVAL`.
6. Bind real connectors only after the dry run passes.
7. First live publication should use assisted/draft mode before auto-publish.
