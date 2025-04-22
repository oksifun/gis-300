
def get_choice_str(choices, choice, default=None):
    matches = [c[1] for c in choices if c[0] == choice]
    return matches[0] if matches else get_choice_str(
        choices, default) if default else None


def get_choice_reverse(choices, choice_str):
    matches = [c[0] for c in choices if c[1] == choice_str]
    return matches[0] if matches else None

