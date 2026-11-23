from smallobj import labels


def test_parse_labels_from_model_reply():
    # 模型回复里可能带 ```json 围栏和前后说明文字；类别统一小写、去重、去掉太长的短语
    text = ('Here is the list:\n```json\n{"labels": ["Cup", "sticky notes", "cup", " power outlet ", '
            '"a very long descriptive phrase of a thing", "", "log"]}\n```\nDone.')
    assert labels.parse(text) == ["cup", "sticky note", "power outlet", "log"]


def test_parse_labels_bad_reply():
    assert labels.parse("I could not read the images.") == []


def test_merge_keeps_fixed_order_and_adds_new():
    fixed = ["cup", "tv_monitor", "picture frame", "remote control"]
    proposed = ["cup", "tv monitor", "power outlet", "picture frame", "charger", "power outlet"]
    assert labels.merge(fixed, proposed) == ["cup", "tv_monitor", "picture frame", "remote control", "power outlet", "charger"]
