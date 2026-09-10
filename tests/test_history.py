from coach.history import History, contains_japanese


def test_contains_japanese():
    assert contains_japanese("猫が寝ている")
    assert contains_japanese("ねこ")
    assert not contains_japanese("just english")


def test_history_roundtrip(tmp_path):
    h = History(tmp_path / "h.jsonl")
    assert h.entries() == []
    h.log("sentence", text="猫")
    h.log("lookup", word="猫", found=True)
    entries = h.entries()
    assert [e["kind"] for e in entries] == ["sentence", "lookup"]
    assert entries[1]["word"] == "猫" and "ts" in entries[0]
