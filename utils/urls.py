from urllib.parse import urlsplit, urlunsplit


def _label(host):
    return (host or '').split('.', 1)[0]


def rebase(url, config_loc):
    """
    `url` as this script can reach it. KoboToolbox builds absolute URLs (`next` pages,
    attachment downloads) from the host it thinks it has, which isn't the one this
    script reached it at when it sits behind a proxy, a port forward or another name
    (e.g. it says kf.kobo.local, it was reached as kf.kobo-ab12.local).

    Only such URLs are rewritten: one whose host isn't a configured one but starts
    with the same label as `kf_url`'s (or `kc_url`'s) gets that address's scheme and
    host. URLs on the configured hosts themselves, on other servers or on storage
    (older releases send kc-host media URLs; some servers send storage URLs) are
    left as they are. Keeps the path and query; `None` stays `None`.
    """
    if not url:
        return url
    u = urlsplit(url)
    targets = [urlsplit(config_loc[k]) for k in ('kf_url', 'kc_url') if config_loc.get(k)]
    if any(u.netloc == t.netloc for t in targets):
        return url
    for t in targets:
        if _label(u.hostname) == _label(t.hostname):
            return urlunsplit((t.scheme, t.netloc, u.path, u.query, u.fragment))
    return url
