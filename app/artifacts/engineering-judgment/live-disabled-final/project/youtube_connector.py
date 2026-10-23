def video_url(video_id):
    return "https://www.youtube.com/watch?v=" + video_id

def normalize_playlist(items):
    if items is None:
        return []
    valid_ids = []
    seen = set()
    for item in items:
        # Skip non-dict items
        if not isinstance(item, dict):
            continue
        # Get id safely
        item_id = item.get("id")
        # Skip None, non-string, or blank/whitespace IDs
        if item_id is None:
            continue
        if not isinstance(item_id, str):
            continue
        if not item_id.strip():
            continue
        # Retain valid string IDs in order without duplicates
        if item_id not in seen:
            valid_ids.append(item_id)
            seen.add(item_id)
    return valid_ids

def playlist_title(playlist):
    if playlist is None:
        return "Untitled"
    title = playlist.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        return "Untitled"
    return title.strip()