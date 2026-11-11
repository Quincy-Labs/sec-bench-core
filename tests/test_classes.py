from sec_bench_core.classes import LABEL_PRINCIPLE, class_guide


def test_class_guide_renders_principle_and_one_line_per_class():
    text = class_guide({"a": "first thing", "none": "no bug"})
    assert text.startswith(LABEL_PRINCIPLE)
    assert text.endswith("- `a`: first thing\n- `none`: no bug")
