def video_url(video_id):
    return "https://www.youtube.com/watch?v=" + video_id

def normalize_playlist(items):
    if items is None:
        return []
    result = []
    seen = set()
    for item in items:
        if item is None:
            continue
        try:
            video_id = item["id"]
        except (KeyError, TypeError):
            continue
        if not isinstance(video_id, str):
            continue
        if video_id.strip():
            if video_id not in seen:
                seen.add(video_id)
                result.append(video_id)
    return result

def playlist_title(playlist):
    if playlist is None:
        return "Untitled"
    try:
        title = playlist.get("title", "")
        if not title or not isinstance(title, str):
            return "Untitled"
        return title.strip()
    except (KeyError, TypeError, AttributeError):
        return "Untitled"
