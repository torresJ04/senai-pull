from scraper import _parse_open_modal_turmas


def test_parse_open_modal_turmas_extracts_fields():
    class DummyLink:
        def __init__(self, href: str) -> None:
            self._href = href

        def get(self, name: str, default=None):
            if name == "href":
                return self._href
            return default

    href = "javascript:openModalTurmas('Name', 'slug-example', 110384, 136, 'Presencial', 0, 1, 0);"
    link = DummyLink(href)
    result = _parse_open_modal_turmas(link)
    assert result is not None
    course_id, unit_id, slug, name = result
    assert course_id == 110384
    assert unit_id == 136
    assert slug == "slug-example"
    assert name == "Name"

