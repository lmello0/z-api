def deep_merge_dicts(c1: dict, c2: dict) -> dict:
    if not c2:
        return c1

    result = c1.copy()

    for key, value in c2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result
