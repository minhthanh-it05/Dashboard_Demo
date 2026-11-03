"""Which sidebar section the current URL belongs to.

Order matters: the first matching prefix wins, so the handover pages (which
live in the projects namespace) are checked before the projects section.
"""

NAV_SECTIONS = (
    ("handovers", ("projects:handover",)),
    ("projects", ("projects:", "procurement:", "payments:")),
    ("pm_dashboard", ("dashboard:pm",)),
    ("my_work", ("dashboard:my_work",)),
    ("opportunities", ("sales:",)),
    ("finance", ("finance:",)),
    ("integrations", ("integrations:",)),
)


def current_section(request):
    match = getattr(request, "resolver_match", None)
    if match is None:
        return ""
    view_name = f"{match.namespace}:{match.url_name}"
    for section, prefixes in NAV_SECTIONS:
        if view_name.startswith(prefixes):
            return section
    return ""
