def format_bytes(bytes_size: int) -> str:
    """
    Returns the size (int) formatted in B, KB, MB, GB, TB or PB

    Args:
        bytes_size (int): The size in bytes to be formatted

    Returns:
        The size in the correct  unit
    """
    if bytes_size < 0:
        raise ValueError("Bytes size must be non-negative")

    units = ["B", "KB", "MB", "GB", "TB"]

    for unit in units:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"

        bytes_size /= 1024.0  # type: ignore[arg-type]

    return f"{bytes_size:.2f} PB"
