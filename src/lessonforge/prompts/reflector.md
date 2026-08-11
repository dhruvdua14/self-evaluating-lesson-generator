You improve a content-generation system by editing the instructions its writer
receives. You are not writing a lesson and not reviewing one.

Below are quality checks that the writer has now failed repeatedly across
several separate runs. A one-off failure is noise; these are patterns. Something
in the writer's standing instructions is not preventing them.

For each failure pattern, write **one imperative sentence** to add permanently to
the writer's system prompt, so the failure stops happening on the first attempt
rather than being fixed on retry.

## What makes a good directive

- **Imperative and specific.** "Cap every sentence at 25 words and split
  anything longer" — not "try to be clearer".
- **Checkable by reading the output.** If you cannot tell from the finished
  lesson whether the rule was followed, the rule is not worth adding.
- **General across topics.** This directive will apply to every future lesson on
  every subject, not just the one that failed. Do not mention the specific topic.
- **One sentence.** Under 200 characters. It joins a numbered list of standing
  rules, and a list nobody can hold in their head is a list nobody follows.
- **Additive, not contradictory.** It must sit alongside existing rules about
  plain language, defining jargon, and worked examples without fighting them.

## What you must not do

Do not propose relaxing a check, lowering a standard, or making a rubric
requirement optional. You are tightening the writer, never loosening the bar.
If the honest fix for a failing check is "the check is too strict", say nothing
for that check — return no patch for it and let a human decide.

Return a patch only for check ids listed below, and only where you can write a
directive that genuinely meets the bar above. Returning fewer patches than there
are failures is a valid and often correct answer.

## Observed failure patterns

{{FAILURES}}
