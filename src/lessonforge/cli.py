"""Command-line interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Settings, load_settings
from .graph import build_graph, describe_graph
from .inject import ALL_MODES, describe_modes
from .llm import build_provider
from .llm.base import ProviderError
from .memory import MemoryStore
from .report import rubric_markdown, write_outputs
from .rubric.registry import RUBRIC
from .state import new_state

app = typer.Typer(
    add_completion=False,
    help="Self-evaluating lesson generator: generate → evaluate → regenerate.",
    no_args_is_help=True,
)
console = Console()

DEFAULT_TOPIC = "Introduction to RAG (Retrieval-Augmented Generation)"


def _settings(provider: str | None, generator: str | None, judge: str | None,
              max_retries: int | None, no_evolve: bool) -> Settings:
    from dataclasses import replace

    settings = load_settings(
        provider=provider,
        generator_model=generator,
        judge_model=judge,
    )
    if max_retries is not None:
        settings = replace(settings, loop=replace(settings.loop, max_retries=max_retries))
    if no_evolve:
        settings = replace(settings, evolution=replace(settings.evolution, enabled=False))
    return settings


def _render_event(event: dict) -> None:
    node = event.get("node", "?")
    status = event.get("status", "")

    if node == "plan" and status == "ok":
        console.print(
            f"  [cyan]plan[/cyan]      blueprint ready · "
            f"{event['objectives']} objectives, {event['concepts']} concepts · "
            f"analogy: [italic]{event['analogy']}[/italic]"
        )
        if event.get("patches_applied"):
            console.print(
                f"            [magenta]{event['patches_applied']} learned "
                f"directive(s) loaded from memory[/magenta]"
            )
    elif node == "generate" and status == "ok":
        tag = "with revision brief" if event.get("had_feedback") else "first draft"
        console.print(
            f"  [cyan]generate[/cyan]  attempt {event['attempt']} · "
            f"{event['chars']:,} chars · {tag}"
        )
    elif node == "inject":
        console.print(
            f"  [yellow]inject[/yellow]    deliberate error `{event['mode']}` planted "
            f"· expecting failure of: {', '.join(event['expected_failures'])}"
        )
    elif node == "evaluate":
        if status == "pass":
            console.print(
                f"  [green]evaluate[/green]  attempt {event['attempt']} · "
                f"[bold green]PASS[/bold green] · {event['summary']} · "
                f"grade {event['grade_level']}, {event['word_count']} words"
            )
        else:
            console.print(
                f"  [red]evaluate[/red]  attempt {event['attempt']} · "
                f"[bold red]FAIL[/bold red] · {event['summary']} · "
                f"grade {event['grade_level']}, {event['word_count']} words"
            )
            for check_id in event.get("failed", []):
                console.print(f"            [red]✗[/red] {check_id}")
    elif node == "gate":
        colour = "green" if status == "shipped" else "red"
        console.print(
            f"  [{colour}]gate[/{colour}]      {status} after "
            f"{event['attempts_used']}/{event['max_attempts']} attempts"
        )
    elif node == "reflect":
        if status == "evolved":
            console.print("  [magenta]reflect[/magenta]   new standing directives learned:")
            for patch in event.get("new_patches", []):
                console.print(f"            [magenta]+[/magenta] ({patch['check_id']}) {patch['directive']}")
        elif status == "error":
            console.print(f"  [yellow]reflect[/yellow]   skipped: {event.get('detail')}")
        else:
            console.print("  [dim]reflect   no new directives (nothing crossed threshold)[/dim]")
        if event.get("non_discriminating"):
            console.print(
                f"            [yellow]rubric warning:[/yellow] never-failing checks: "
                f"{', '.join(event['non_discriminating'])}"
            )
    elif node == "persist" and status == "ok":
        console.print(f"  [dim]persist   run #{event['run_id']} recorded[/dim]")


@app.command()
def run(
    topic: str = typer.Option(DEFAULT_TOPIC, "--topic", "-t", help="Lesson topic."),
    provider: str = typer.Option(None, "--provider", "-p", help="gemini | mock"),
    generator: str = typer.Option(None, "--generator-model"),
    judge: str = typer.Option(None, "--judge-model"),
    max_retries: int = typer.Option(None, "--max-retries", help="Regenerations after attempt 1."),
    inject_error: str = typer.Option(
        None, "--inject-error",
        help=f"Plant a deliberate error to test the evaluator: {', '.join(ALL_MODES)}",
    ),
    no_evolve: bool = typer.Option(False, "--no-evolve", help="Disable the self-evolving layer."),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
) -> None:
    """Generate a lesson, evaluate it, and regenerate until it clears the rubric."""
    if inject_error and inject_error not in ALL_MODES:
        console.print(f"[red]Unknown injection mode:[/red] {inject_error}")
        console.print(describe_modes())
        raise typer.Exit(2)

    settings = _settings(provider, generator, judge, max_retries, no_evolve)

    try:
        llm = build_provider(settings)
    except ProviderError as exc:
        console.print(Panel(str(exc), title="[red]Provider error", border_style="red"))
        raise typer.Exit(1)

    store = MemoryStore(settings.memory_db)

    if not quiet:
        console.print()
        console.print(Panel.fit(
            f"[bold]{topic}[/bold]\n\n"
            f"provider  {settings.provider}\n"
            f"generator {settings.generator_model}\n"
            f"judge     {settings.judge_model}\n"
            f"budget    {settings.loop.max_retries} retries "
            f"({settings.loop.max_retries + 1} attempts max)\n"
            f"rubric    {len(RUBRIC)} checks "
            f"({sum(1 for c in RUBRIC if c.blocking)} blocking)"
            + (f"\ninject    {inject_error}" if inject_error else ""),
            title="lessonforge", border_style="cyan",
        ))
        console.print()

    from .memory import build_patch_block
    patch_text, patch_ids = build_patch_block(store, settings)

    run_id = store.start_run(
        topic=topic,
        provider=settings.provider,
        generator_model=settings.generator_model,
        judge_model=settings.judge_model,
        injected_error=inject_error,
        patches_applied=len(patch_ids),
    )

    state = new_state(topic, inject_error=inject_error)
    state["run_id"] = run_id

    graph = build_graph(provider=llm, settings=settings, store=store)

    seen = 0
    final = state
    # Recursion limit must exceed the worst-case node count: plan + N*(gen+eval)
    # + finalise + reflect + persist, with headroom.
    limit = 6 + settings.loop.hard_cap_attempts * 2 + 4
    for chunk in graph.stream(state, stream_mode="values", config={"recursion_limit": limit}):
        final = chunk
        events = chunk.get("events") or []
        if not quiet:
            for event in events[seen:]:
                _render_event(event)
        seen = len(events)

    if final.get("error"):
        console.print(Panel(str(final["error"]), title="[red]Run error", border_style="red"))

    written = write_outputs(final, settings)

    if not quiet:
        console.print()
        table = Table(show_header=False, box=None, padding=(0, 2))
        for name, path in written.items():
            table.add_row(f"[dim]{name}[/dim]", str(path))
        console.print(table)

        usage = final.get("usage")
        if usage and getattr(usage, "calls", 0):
            console.print(
                f"\n[dim]{usage.calls} API calls · "
                f"{usage.input_tokens:,} in / {usage.output_tokens:,} out tokens[/dim]"
            )

        shipped = final.get("shipped")
        console.print()
        console.print(Panel.fit(
            "[bold green]SHIPPED[/bold green] — cleared every blocking check"
            if shipped else
            "[bold red]REJECTED[/bold red] — retry budget exhausted, nothing shipped",
            border_style="green" if shipped else "red",
        ))
        console.print()

    raise typer.Exit(0 if final.get("shipped") else 1)


@app.command()
def rubric(as_json: bool = typer.Option(False, "--json")) -> None:
    """Print the rubric."""
    if as_json:
        console.print_json(json.dumps([c.model_dump(mode="json") for c in RUBRIC]))
        return

    table = Table(title=f"Rubric — {len(RUBRIC)} checks", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("check id", style="cyan")
    table.add_column("dimension")
    table.add_column("engine")
    table.add_column("blocking", justify="center")
    table.add_column("tests")

    for i, spec in enumerate(RUBRIC, start=1):
        table.add_row(
            str(i), spec.id, spec.dimension.value, spec.kind.value,
            "[red]yes[/red]" if spec.blocking else "[dim]advisory[/dim]",
            spec.title,
        )
    console.print(table)


@app.command()
def memory(
    as_json: bool = typer.Option(False, "--json"),
    reset: bool = typer.Option(False, "--reset", help="Delete the memory database."),
) -> None:
    """Inspect what the system has learned across runs."""
    settings = load_settings()

    if reset:
        if settings.memory_db.exists():
            settings.memory_db.unlink()
            console.print(f"[yellow]Deleted[/yellow] {settings.memory_db}")
        else:
            console.print("[dim]No memory database to delete.[/dim]")
        return

    store = MemoryStore(settings.memory_db)
    stats = store.stats()

    if as_json:
        console.print_json(store.export())
        return

    console.print()
    console.print(Panel.fit(
        f"runs                     {stats['total_runs']}\n"
        f"shipped                  {stats['shipped']}\n"
        f"first-attempt passes     {stats['first_attempt_passes']}\n"
        f"first-attempt pass rate  "
        f"{stats['first_attempt_pass_rate'] if stats['first_attempt_pass_rate'] is not None else '—'}\n"
        f"avg attempts per run     {stats['avg_attempts'] or '—'}\n"
        f"active directives        {stats['active_patches']}\n"
        f"total API calls          {stats['api_calls']}",
        title="memory", border_style="magenta",
    ))

    patterns = store.failure_patterns(min_failures=1)
    if patterns:
        table = Table(title="Failure patterns (all runs)")
        table.add_column("check id", style="cyan")
        table.add_column("fails", justify="right")
        table.add_column("runs seen", justify="right")
        table.add_column("most recent reason", max_width=60)
        for p in patterns[:15]:
            table.add_row(p.check_id, str(p.fail_count), str(p.runs_seen), p.last_reason[:200])
        console.print(table)

    patches = store.active_patches(limit=20)
    if patches:
        table = Table(title="Learned directives injected into every future run")
        table.add_column("from check", style="cyan")
        table.add_column("directive")
        table.add_column("used", justify="right")
        for p in patches:
            table.add_row(p.check_id, p.directive, str(p.times_applied))
        console.print(table)
    else:
        console.print("[dim]No directives learned yet.[/dim]")

    history = stats.get("history") or []
    if len(history) > 1:
        table = Table(title="Run history — does first-attempt quality improve?")
        table.add_column("run", justify="right")
        table.add_column("attempts", justify="right")
        table.add_column("1st attempt", justify="center")
        table.add_column("directives active", justify="right")
        table.add_column("shipped", justify="center")
        for row in history[-15:]:
            table.add_row(
                str(row["id"]), str(row["attempts"]),
                "[green]pass[/green]" if row["first_attempt_ok"] else "[red]fail[/red]",
                str(row["patches_applied"]),
                "yes" if row["shipped"] else "no",
            )
        console.print(table)
    console.print()


@app.command()
def graph() -> None:
    """Print the graph topology."""
    console.print()
    console.print(Panel(describe_graph(), title="agent graph", border_style="cyan"))
    console.print()


@app.command()
def injections() -> None:
    """List the deliberate-error modes used to test the evaluator."""
    console.print()
    console.print(Panel(describe_modes(), title="injection modes", border_style="yellow"))
    console.print()


@app.command()
def verify(
    provider: str = typer.Option(None, "--provider", "-p", help="gemini | mock"),
    judge: str = typer.Option(None, "--judge-model"),
    baseline: Path = typer.Option(
        None, "--baseline", "-b",
        help="Lesson to corrupt. Defaults to the bundled known-good lesson.",
    ),
    mode: list[str] = typer.Option(
        None, "--mode", "-m", help="Injection modes to test. Repeatable. Default: all."
    ),
) -> None:
    """Prove the evaluator catches deliberate errors.

    Takes a lesson that passes every check, corrupts it in known ways, and
    reports whether the checks predicted to fail actually failed.
    """
    from .verify import verify_evaluator

    settings = _settings(provider, None, judge, None, True)

    try:
        llm = build_provider(settings)
    except ProviderError as exc:
        console.print(Panel(str(exc), title="[red]Provider error", border_style="red"))
        raise typer.Exit(1)

    text = baseline.read_text(encoding="utf-8") if baseline else None
    modes = list(mode) if mode else None

    console.print()
    console.print(Panel.fit(
        f"judge     {settings.judge_model}\n"
        f"provider  {settings.provider}\n"
        f"baseline  {baseline or 'bundled known-good lesson'}",
        title="evaluator verification", border_style="cyan",
    ))
    console.print()

    def progress(stage: str, detail: str) -> None:
        if stage == "baseline":
            console.print("  [dim]evaluating clean baseline…[/dim]")
        else:
            console.print(f"  [dim]injecting `{detail}`…[/dim]")

    report = verify_evaluator(
        provider=llm, settings=settings, baseline=text, modes=modes, on_progress=progress
    )

    console.print()
    if report.baseline_passed:
        console.print("[green]Baseline passes every blocking check.[/green] "
                      "The experiment is valid.\n")
    else:
        console.print(Panel(
            "The baseline lesson does not pass every blocking check "
            f"(failing: {', '.join(report.baseline_failures)}).\n\n"
            "Injection results below are inconclusive — you cannot show a check "
            "catching a planted error if it was already failing beforehand.",
            title="[yellow]Inconclusive", border_style="yellow",
        ))
        console.print()

    table = Table(title="Did the evaluator catch each planted error?")
    table.add_column("injection", style="cyan")
    table.add_column("predicted to fail")
    table.add_column("caught", justify="center")
    table.add_column("missed", style="red")
    table.add_column("also failed", style="dim")

    for outcome in report.outcomes:
        table.add_row(
            outcome.mode,
            ", ".join(outcome.expected),
            "[green]yes[/green]" if outcome.passed else "[red]NO[/red]",
            ", ".join(outcome.missed) or "—",
            ", ".join(outcome.collateral) or "—",
        )
    console.print(table)
    console.print()

    if report.all_caught:
        console.print(Panel.fit(
            "[bold green]Every planted error was caught[/bold green] by the check "
            "predicted to catch it.", border_style="green",
        ))
        console.print()
        raise typer.Exit(0)

    misses = [f"{o.mode} → {', '.join(o.missed)}" for o in report.outcomes if o.missed]
    console.print(Panel(
        "[bold red]The rubric has gaps.[/bold red] These planted errors were not "
        "caught by their predicted checks:\n\n" + "\n".join(f"  · {m}" for m in misses)
        + "\n\nThis is a real finding about the evaluator, not a crash.",
        border_style="red",
    ))
    console.print()
    raise typer.Exit(1)


@app.command()
def models() -> None:
    """List models available on the configured API key."""
    settings = load_settings()
    if settings.provider != "gemini":
        console.print(f"[yellow]Model listing is only supported for gemini "
                      f"(provider is {settings.provider}).[/yellow]")
        raise typer.Exit(1)
    try:
        provider = build_provider(settings)
        names = provider.list_models()
    except ProviderError as exc:
        console.print(Panel(str(exc), title="[red]Provider error", border_style="red"))
        raise typer.Exit(1)

    table = Table(title=f"{len(names)} models available on this key")
    table.add_column("model id", style="cyan")
    for name in names:
        table.add_row(name)
    console.print(table)


@app.command("export-rubric")
def export_rubric(
    out: Path = typer.Option(Path("RUBRIC.md"), "--out", "-o")
) -> None:
    """Write the rubric to a markdown file."""
    body = [
        "# Rubric",
        "",
        "Every check is hard pass/fail. There is no partial credit and no",
        "weighted score. A lesson ships only if **every blocking check passes**.",
        "",
        rubric_markdown(),
        "",
        "## Check definitions",
        "",
    ]
    for spec in RUBRIC:
        body += [
            f"### `{spec.id}`",
            "",
            f"- **Dimension:** {spec.dimension.value}",
            f"- **Engine:** {spec.kind.value}",
            f"- **Blocking:** {'yes' if spec.blocking else 'no (advisory)'}",
            f"- **Tests:** {spec.title}",
            f"- **Question put to the evaluator:** {spec.question}",
            f"- **Remediation hint fed back on retry:** {spec.remediation_hint}",
            "",
        ]
    out.write_text("\n".join(body), encoding="utf-8")
    console.print(f"[green]Wrote[/green] {out}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
