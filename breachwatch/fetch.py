import time
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36 breach-watch/0.1')


def http_get(url: str, timeout: int = 40, retries: int = 1) -> str:
    """Fetch a URL, return decoded text. Raises RuntimeError on failure."""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml,application/json,*/*',
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            return data.decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            # 404/403 etc. - no retry for hard client errors
            raise RuntimeError(f'HTTP {e.code} for {url}')
        except Exception as e:  # URLError, timeout, connection reset
            last = e
            if attempt < retries:
                time.sleep(2)
    raise RuntimeError(f'GET failed after {retries + 1} tries: {url} -> {last}')
