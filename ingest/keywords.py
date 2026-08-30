from collections import Counter


def harvest_tags(posts, known):
    exclude = {k.strip().lstrip('#').strip().casefold() for k in known}
    counts = Counter()
    for post in posts:
        tags = post.get('tags')
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if not isinstance(tag, str):
                continue
            keyword = tag.strip().lstrip('#').strip()
            if not keyword or keyword.casefold() in exclude:
                continue
            counts[keyword] += 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
