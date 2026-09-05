"""Renders one screenshot of the manual with its numbered marks.

The marks are data rather than markup (see `generic.manual`), so the templates carry
the prose and one tag per figure instead of a dozen absolutely positioned spans each.
"""

from django import template

from generic import manual

register = template.Library()

FIGURES = {**manual.EARTH_ENGINE, **manual.APPLICATION}


@register.inclusion_tag('manual/figure.html')
def figure(slug):
    """The figure registered under `slug`.

    Raises on an unknown slug on purpose: a manual that quietly renders nothing where a
    figure should be is worse than one that fails while it is being written.
    """
    return {'figure': FIGURES[slug]}
