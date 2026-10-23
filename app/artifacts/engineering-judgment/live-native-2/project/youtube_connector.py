def video_url(video_id):
    return "https://www.youtube.com/watch?v=" + video_id

def normalize_playlist(items):
    if items is None:
        return []
    seen = set()
    result = []
    for item in items:
        if item is None:
            continue
        item_id = item.get("id")
        if not item_id or item_id == "":
            continue
        if item_id not in seen:
            seen.add(item_id)
            result.append(item_id)
    return result

def playlist_title(playlist):
    if playlist is None:
        return "Untitled"
    title = playlist.get("title", "")
    if not title or title.strip() == "":
        return "Untitled"
    return title.strip()