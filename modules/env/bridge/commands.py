try:
    from . import client
except ImportError:
    import client

def notify(title: str, message: str, progress: Optional[int] = None, tag: str = "agy_status") -> Dict[str, Any]:
    payload = {"title": title, "message": message, "tag": tag}
    if progress is not None:
        payload["progress"] = max(0, min(100, progress))
    return client.send_command("notify", payload)

def open_url(url: str) -> Dict[str, Any]:
    return client.send_command("open_url", {"url": url})

def wakelock(acquire: bool = True, tag: str = "agy_task") -> Dict[str, Any]:
    action = "acquire" if acquire else "release"
    return client.send_command("wakelock", {"action": action, "tag": tag})

def clipboard_set(text: str) -> Dict[str, Any]:
    return client.send_command("clipboard_set", {"text": text})
