"""Collaborative space member color palette."""

COLLAB_COLORS = [
    "#0088FF",  # Blue (owner default)
    "#FF6B35",  # Orange
    "#22C55E",  # Green
    "#A855F7",  # Purple
    "#F43F5E",  # Rose
    "#06B6D4",  # Cyan
    "#EAB308",  # Yellow
    "#EC4899",  # Pink
]


def get_next_color(member_count: int) -> str:
    """Get the next color for a new member based on existing member count."""
    return COLLAB_COLORS[member_count % len(COLLAB_COLORS)]
