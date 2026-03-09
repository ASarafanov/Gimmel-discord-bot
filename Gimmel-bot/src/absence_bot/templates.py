from __future__ import annotations

from typing import Dict, Optional


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def days_word_ru(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    if days % 10 in (2, 3, 4) and days % 100 not in (12, 13, 14):
        return "дня"
    return "дней"


def render_user_line(
    template_text: str,
    *,
    days: Optional[int],
    display_name: str,
    user_id: str,
    user_mention: str,
    last_seen_date: Optional[str],
    last_seen_channel_id: Optional[str],
) -> str:
    if days is None:
        return f"Нет данных о визитах для {display_name}."

    context: Dict[str, str] = {
        "days": str(days),
        "days_word": days_word_ru(days),
        "display_name": display_name,
        "user_id": user_id,
        "user_mention": user_mention,
        "last_seen_date": last_seen_date or "-",
        "last_seen_channel_id": last_seen_channel_id or "-",
    }
    return template_text.format_map(SafeDict(context))


def chunk_lines(lines: list[str], max_len: int = 2000) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        text = line.strip()
        if not text:
            continue
        line_len = len(text)

        if line_len > max_len:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            chunks.append(text[:max_len])
            continue

        add_len = line_len if not current else line_len + 1
        if current_len + add_len > max_len:
            chunks.append("\n".join(current))
            current = [text]
            current_len = line_len
        else:
            current.append(text)
            current_len += add_len

    if current:
        chunks.append("\n".join(current))

    return chunks
