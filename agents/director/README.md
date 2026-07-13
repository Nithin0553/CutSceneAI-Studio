# Director Agent

Director v0.1 turns a natural-language scene brief into CIR 0.1. The backend owns orchestration
and domain validation; the OpenAI adapter owns provider-specific structured generation.

Normal tests use deterministic fakes and never call a live model. A live smoke test is a manual
release gate after `OPENAI_API_KEY` is configured locally.
