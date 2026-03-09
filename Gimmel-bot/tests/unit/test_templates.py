from absence_bot.templates import chunk_lines, days_word_ru, render_user_line


def test_days_word_ru_forms() -> None:
    assert days_word_ru(1) == "день"
    assert days_word_ru(2) == "дня"
    assert days_word_ru(5) == "дней"
    assert days_word_ru(21) == "день"


def test_render_user_line_with_days() -> None:
    line = render_user_line(
        "Прошло {days} {days_word}: {display_name}",
        days=3,
        display_name="Валерий",
        user_id="42",
        user_mention="<@42>",
        last_seen_date="2024-01-01",
        last_seen_channel_id="100",
    )
    assert line == "Прошло 3 дня: Валерий"


def test_render_user_line_without_data() -> None:
    line = render_user_line(
        "unused",
        days=None,
        display_name="Иван",
        user_id="42",
        user_mention="<@42>",
        last_seen_date=None,
        last_seen_channel_id=None,
    )
    assert "Нет данных" in line


def test_chunk_lines_limits_message_length() -> None:
    lines = ["a" * 1200, "b" * 1200]
    chunks = chunk_lines(lines, max_len=2000)
    assert len(chunks) == 2
    assert all(len(chunk) <= 2000 for chunk in chunks)
