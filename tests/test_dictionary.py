from coach.dictionary import parse_jisho

SAMPLE = {
    "data": [
        {
            "is_common": True,
            "jlpt": ["jlpt-n5"],
            "japanese": [{"word": "勉強", "reading": "べんきょう"}],
            "senses": [
                {"english_definitions": ["study"], "parts_of_speech": ["Noun", "Suru verb"], "tags": []},
                {"english_definitions": ["discount", "reduction"], "parts_of_speech": ["Noun"], "tags": []},
            ],
        },
        {
            "is_common": False,
            "jlpt": [],
            "japanese": [{"reading": "べんきょうか"}],
            "senses": [{"english_definitions": ["studious person"], "parts_of_speech": ["Noun"], "tags": []}],
        },
    ]
}


def test_parse_trims_fields():
    entries = parse_jisho(SAMPLE)
    assert len(entries) == 2
    first = entries[0]
    assert first["word"] == "勉強"
    assert first["reading"] == "べんきょう"
    assert first["common"] is True
    assert first["jlpt"] == ["jlpt-n5"]
    assert first["senses"][0]["meanings"] == ["study"]
    # kana-only entries fall back to the reading as the word
    assert entries[1]["word"] == "べんきょうか"


def test_parse_respects_limit():
    assert len(parse_jisho(SAMPLE, limit=1)) == 1
