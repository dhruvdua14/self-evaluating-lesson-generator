# Live evaluator verification — real Gemini judge

Command:

```
lessonforge verify --judge-model gemini-3.1-flash-lite
```

Run against a live Gemini judge. The baseline passed every blocking check,
so the experiment is valid; all seven planted errors were caught by exactly
the checks predicted for them in `inject.py` before any result was seen.

```
  injecting `coverage`…
  injecting `gutted`…

Baseline passes every blocking check. The experiment is valid.

                  Did the evaluator catch each planted error?                   
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ injection   ┃ predicted to fail     ┃ caught ┃ missed ┃ also failed          ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ factual     │ no_weight_update_myt… │  yes   │ —      │ —                    │
│             │ accuracy_grounded     │        │        │                      │
│ fabrication │ no_unsupported_claims │  yes   │ —      │ accuracy_grounded    │
│ jargon      │ jargon_defined_on_fi… │  yes   │ —      │ —                    │
│             │ jargon_density,       │        │        │                      │
│             │ no_runaway_sentence   │        │        │                      │
│ idiom       │ no_idioms_or_cultura… │  yes   │ —      │ —                    │
│ dependency  │ standalone_completen… │  yes   │ —      │ jargon_density       │
│             │ no_forward_references │        │        │                      │
│ coverage    │ has_worked_example    │  yes   │ —      │ jargon_defined_on_f… │
│ gutted      │ covers_what_why_how,  │  yes   │ —      │ example_density,     │
│             │ has_worked_example,   │        │        │ has_concrete_analogy │
│             │ covers_three_steps    │        │        │                      │
└─────────────┴───────────────────────┴────────┴────────┴──────────────────────┘

╭────────────────────────────────────────────────────────────────────╮
│ Every planted error was caught by the check predicted to catch it. │
╰────────────────────────────────────────────────────────────────────╯

```
