from __future__ import annotations

from typing import Optional

from .models import LastSeenType, VoiceTransition


def classify_voice_transition(
    before_channel_id: Optional[str],
    after_channel_id: Optional[str],
) -> VoiceTransition:
    if before_channel_id is None and after_channel_id is not None:
        return VoiceTransition(
            should_update=True,
            event_type=LastSeenType.VOICE_JOIN,
            new_last_voice_channel_id=after_channel_id,
        )

    if (
        before_channel_id is not None
        and after_channel_id is not None
        and before_channel_id != after_channel_id
    ):
        return VoiceTransition(
            should_update=True,
            event_type=LastSeenType.VOICE_MOVE,
            new_last_voice_channel_id=after_channel_id,
        )

    return VoiceTransition(
        should_update=False,
        event_type=None,
        new_last_voice_channel_id=after_channel_id,
    )
