"""Build the 3D pages in docs/ from their templates and the exported mesh data.

    python docs/src/build_pages.py <scene.js> <geom.js>

``scene.js`` comes from ``scene/export_scene.py`` and ``geom.js`` from
``lab-day/export_geom.py`` (see docs/src/README.md). Writes:

    docs/g1-open-day-scene.html      the Open Day scene (template + window.SCENE)
    docs/g1-open-day-animation.html  the same page with animation-only.html injected
    docs/g1-lab-day.html             the lab day guide (template + window.GEOM)
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
DOCS = SRC.parent


# The templates are written without <html>/<head>/<body>; this is the document skeleton around them.
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>')


LAB_HEAD = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n')


def wrap(page: str) -> str:
    """Skeleton around a template: the head ends after its first <style> block."""
    i = page.index("</style>") + len("</style>")
    return HEAD + page[:i] + "</head><body>" + page[i:] + "</body></html>"


def wrap_lab(page: str) -> str:
    """The lab day guide's skeleton (Chinese page, one tag per line)."""
    i = page.index("</style>") + len("</style>")
    body = page[i:].lstrip("\n")
    return LAB_HEAD + page[:i] + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"


def build(scene_js: str, geom_js: str) -> dict:
    scene_tpl = (SRC / "scene" / "template.html").read_text(encoding="utf-8")
    lab_tpl = (SRC / "lab-day" / "template.html").read_text(encoding="utf-8")
    assert scene_tpl.count("/*SCENE*/") == 1 and lab_tpl.count("/*GEOM*/") == 1
    scene = wrap(scene_tpl.replace("/*SCENE*/", scene_js.strip()))
    lab = wrap_lab(lab_tpl.replace("/*GEOM*/", geom_js.strip()))

    snippet = (SRC / "animation-only.html").read_text(encoding="utf-8")
    style = snippet[snippet.index("<style"):snippet.index("</style>") + len("</style>")]
    script = snippet[snippet.index("<script>"):].strip()
    head_end = scene.index("</style></head><body>") + len("</style>")
    anim = scene[:head_end] + style + scene[head_end:]
    anim = anim.replace("<title>G1 Open Day Scene</title>", "<title>G1 Open Day Animation</title>", 1)
    body_end = anim.rindex("</body>")
    anim = anim[:body_end] + script + anim[body_end:]
    return {"g1-open-day-scene.html": scene, "g1-open-day-animation.html": anim, "g1-lab-day.html": lab}


if __name__ == "__main__":
    pages = build(Path(sys.argv[1]).read_text(encoding="utf-8"), Path(sys.argv[2]).read_text(encoding="utf-8"))
    for name, html in pages.items():
        (DOCS / name).write_text(html, encoding="utf-8")
        print("wrote docs/%s (%d kB)" % (name, len(html.encode("utf-8")) // 1024))
