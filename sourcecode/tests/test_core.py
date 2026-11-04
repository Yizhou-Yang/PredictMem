"""Offline tests for the SDK core (no network)."""

from predictmem import EffectRecord, EffectStore, Prediction, PredictMem, agree


def test_agree_containment():
    assert agree("TikTok", "The platform was TikTok.")
    assert not agree("TikTok", "Instagram")


def test_store_versioning(tmp_path):
    store = EffectStore(tmp_path / "effects.jsonl")
    store.add(EffectRecord(state="s", action="a", predicted="p1", observed="o1"))
    store.add(EffectRecord(state="s", action="a", predicted="p2", observed="o2"))
    assert len(store) == 1
    assert store.lookup("s", "a").observed == "o2"


def test_store_search():
    store = EffectStore()
    store.add(EffectRecord(state="order 123 refund", action="refund(123)", predicted="", observed="ok"))
    store.add(EffectRecord(state="weather paris", action="lookup()", predicted="", observed="sunny"))
    hits = store.search("refund order")
    assert len(hits) == 1 and "refund" in hits[0].action


def test_predictmem_commits_on_agreement():
    pm = PredictMem(lambda state, proposed: Prediction(expected_effect=proposed))
    decision, action = pm.step("evidence", "TikTok")
    assert decision.commit and decision.reason == "agreement"


def test_predictmem_expands_once_on_disagreement():
    calls = {"n": 0}

    def predict(state, proposed):
        calls["n"] += 1
        return Prediction(expected_effect="TikTok" if state == "wide" else "Instagram")

    pm = PredictMem(predict)
    decision, action = pm.step("narrow", "TikTok", expand=lambda s: "wide")
    assert decision.commit
    assert decision.reason == "agreement_after_expansion"
    assert calls["n"] == 2


def test_skeletonize_drops_values():
    from predictmem import skeletonize

    out = skeletonize("get_order_details(order_id='#W123', user_id='u9')")
    assert "get_order_details" in out and "<from current task>" in out and "W123" not in out


def test_controller_expands_once():
    from predictmem import controller
    from predictmem.core import Prediction

    calls = {"n": 0}

    def predict(state, action):
        calls["n"] += 1
        return Prediction(expected_effect="x" if state == "wide" else "y")

    out = controller.run(predict, "narrow", "x", expand=lambda s: "wide")
    assert out.expanded and out.committed and calls["n"] == 2
