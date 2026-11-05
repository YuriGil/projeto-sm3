# Vision provider binding
The OS does not require ChatGPT. At deployment, bind VISION_PRIMARY in n8n Credentials to any provider capable of image/video semantic analysis and structured JSON output.
Provider transport is converted by `vision/provider_adapter.py` into the canonical contract. Invalid outputs fail closed.
Use proxies/contact sheets by default to control bandwidth/cost. Cache analysis by content hash + analysis version.
