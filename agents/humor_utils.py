def inconvenience_directive(level: int) -> str:
    """Return a prompt fragment that scales with the agent's inconvenience level."""
    if level <= 0:
        return ""
    if level <= 33:
        return (
            "INCONVENIENCE: Look beneath the obvious angle."
            " If a more uncomfortable truth exists, surface it."
        )
    if level <= 66:
        return (
            "INCONVENIENCE: Always find the truth the target would prefer to hide."
            " Don't let them off the hook with a comfortable angle."
        )
    return (
        "INCONVENIENCE: Force the most uncomfortable truth into every concept."
        " If it doesn't make the audience squirm, it isn't ready."
    )
