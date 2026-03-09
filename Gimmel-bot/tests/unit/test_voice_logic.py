from absence_bot.models import LastSeenType
from absence_bot.voice_logic import classify_voice_transition


def test_voice_join_updates_last_seen() -> None:
    transition = classify_voice_transition(None, "123")
    assert transition.should_update is True
    assert transition.event_type == LastSeenType.VOICE_JOIN


def test_voice_move_updates_last_seen() -> None:
    transition = classify_voice_transition("123", "456")
    assert transition.should_update is True
    assert transition.event_type == LastSeenType.VOICE_MOVE


def test_mute_only_change_does_not_update() -> None:
    transition = classify_voice_transition("123", "123")
    assert transition.should_update is False
    assert transition.event_type is None
