def format_choices_error(prefix: str, allowed: set[str] | frozenset[str]) -> str:
    return f"{prefix}: {', '.join(sorted(allowed))}."
