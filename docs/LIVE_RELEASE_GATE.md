# Live release gate
RC6 validates the current Metricool scheduling contract but deliberately performs no live scheduling.
First credential-bound publication test must:
1. use an explicitly approved MOLOTOV content item;
2. pass render QA;
3. query scheduled posts for duplicate protection;
4. use a future slot in America/Sao_Paulo;
5. start with autoPublish=false;
6. only enable automatic publication after the assisted test succeeds.
Metrics then enter the learning gate; protected rules always require human review.
