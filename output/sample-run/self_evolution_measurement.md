# Live self-evolution measurement

The claim was stated up front so it could be checked: *first-attempt pass rate
should rise as learned directives accumulate.* It was checked. It did not hold.

## Run history

```
┏━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ run ┃ attempts ┃ 1st attempt ┃ directives active ┃ shipped ┃
┡━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│   1 │        3 │    fail     │                 0 │   yes   │
│   2 │        0 │     n/a     │                 1 │ errored │
│   3 │        0 │     n/a     │                 1 │ errored │
│   4 │        3 │    fail     │                 1 │   no    │
│   5 │        1 │    pass     │                 2 │   yes   │
│   6 │        1 │    pass     │                 2 │   yes   │
│   7 │        1 │    pass     │                 2 │   yes   │
│   8 │        1 │    pass     │                 0 │   yes   │
│   9 │        0 │     n/a     │                 0 │ errored │
└─────┴──────────┴─────────────┴───────────────────┴─────────┘

```

## The confound

Runs 1 and 4 failed substantially on `jargon_density` false positives — the
check was rejecting definitions that were correct. Those bugs were fixed
between run 4 and run 5, so the 0/1 -> 3/3 jump had two candidate causes:
the directives, or the rubric no longer being wrong.

## The control

Same code, same models, directives disabled with `--no-evolve`:

```
=== CONTROL RUN A — same code, directives DISABLED ===
  evaluate  attempt 1 · PASS · 18/18 checks passed · grade 7.05, 1805 words
  gate      shipped after 1/3 attempts
  reflect   no new directives (nothing crossed threshold)
=== CONTROL RUN B — same code, directives DISABLED ===
  evaluate  attempt 1 · ERROR · Nothing to evaluate: the generator produced an 
  gate      rejected after 1/3 attempts
  reflect   no new directives (nothing crossed threshold)
```

Control A passed on the first attempt with no directives at all. Control B was
lost to the generator's daily quota, so the control is a single data point.

## Conclusion

One control run cannot show the directives are inert. It is enough to break the
attribution: the improvement is equally well explained by the rubric fixes, so
it is no longer evidence for the directives.

- **Mechanism: verified.** Failures aggregate, a directive is synthesised at
  threshold, and it is injected before attempt 1 of every later run.
- **Quality benefit: unproven.** Establishing it needs an interleaved A/B across
  many runs, on a frozen rubric, over varied topics.
