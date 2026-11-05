# Semantic Media Analysis v1
Analyze only the supplied proxy/contact-sheet and metadata. Return JSON matching media_analysis.schema.json.
Score 0–100: technical_quality, visual_strength, editorial_novelty, process_value, portfolio_value, anatomy_context.
For video also score hook_retention.
Detect near-duplicates. A near-duplicate must not be SELECIONADA when it adds no new visual information.
DESCARTAR is editorial only and never means deleting the original.
Do not infer that Japanese-themed brand identity restricts the tattoo style.
