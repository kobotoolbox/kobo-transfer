from urllib.parse import urlsplit, urlunsplit


def rebase(url, base):
    """
    `url` with the scheme and host of `base`: KoboToolbox builds absolute URLs (`next`
    pages, attachment downloads) from the host it thinks it has, which isn't the one this
    script reached it at when it sits behind a proxy or another name. Keeps the path and
    query; `None` stays `None`.
    """
    if not url:
        return url
    u, b = urlsplit(url), urlsplit(base)
    return urlunsplit((b.scheme, b.netloc, u.path, u.query, u.fragment))
