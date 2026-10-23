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
            video_id = item.get("id")
            if video_id and isinstance(video_id, str) and video_id.strip():
                if video_id not in seen:
                    seen.add(video_id)
                    result.append(video_id)
        except (KeyError, TypeError, AttributeError):
            continue
    return result

def playlist_title(playlist):
    return playlist["title"]
