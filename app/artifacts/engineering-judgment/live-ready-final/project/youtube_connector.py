def video_url(video_id):
    return "https://www.youtube.com/watch?v=" + video_id

def normalize_playlist(items):
    if items is None:
        return []
    seen = set()
    result = []
    for item in items:
        # Only non-blank string IDs are valid
        if isinstance(item, dict) and "id" in item:
            vid = item["id"]
            # Check: must be a string, not None, not blank/whitespace
            if isinstance(vid, str) and vid.strip():
                # Retain order without duplicates
                if vid not in seen:
                    seen.add(vid)
                    result.append(vid)
    return result

def playlist_title(playlist):
    if playlist is None:
        return "Untitled"
    title = playlist.get("title", "")
    if not title or not title.strip():
        return "Untitled"
    return title.strip()