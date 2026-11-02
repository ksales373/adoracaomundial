#!/usr/bin/env python3
"""Turn the published Claude artifact page into the GitHub Pages site (index.html + img/).

Usage: python3 scripts/build_from_artifact.py ARTIFACT.html [IMAGE_DIR ...]

- Keeps the repo's own <head> (lang, description, favicon).
- Points images at img/<id>.jpg instead of the artifact's /_blob/<id>.
- Turns the AI chat off (it only works inside Claude).
- Copies any image the page needs from IMAGE_DIR (files named <id>.jpg / <id>.png),
  and deletes images in img/ that the page no longer uses.
"""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = "569f690325138fc4db2591a39b664b30"
CFG_RE = re.compile(r'(<script type="application/json" id="site-config">)(.*?)(</script>)', re.S)


def main():
    src = open(sys.argv[1], encoding="utf-8").read()
    image_dirs = sys.argv[2:]
    current = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()

    # 1. head: repo's first line (custom <head> + <title>) replaces the artifact's first two lines
    repo_head = current.split("\n", 1)[0]
    art_lines = src.split("\n")
    assert art_lines[1].startswith("<title>"), "unexpected artifact header"
    out = repo_head + "\n" + "\n".join(art_lines[2:])

    # 2. config: chat off on the public site
    m = CFG_RE.search(out)
    cfg = json.loads(m.group(2))
    cfg["chatOn"] = False
    out = out[:m.start(2)] + json.dumps(cfg, ensure_ascii=False).replace("<", "\\u003c") + out[m.end(2):]

    # 3. images served from the repo
    old_img = 'const img = id => "/_blob/"+encodeURIComponent(id);'
    assert old_img in out, "img() helper not found"
    out = out.replace(old_img, 'const img = id => "img/"+encodeURIComponent(id)+(id==="%s"?".png":".jpg");' % LOGO)
    out = out.rstrip("\n")
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(out)

    # 4. sync img/ with the ids the config uses
    ids = set(re.findall(r'"([0-9a-f]{32})"', json.dumps(cfg)))
    img_dir = os.path.join(ROOT, "img")
    have = {f.split(".")[0] for f in os.listdir(img_dir)}
    missing = []
    for i in sorted(ids - have):
        ext = ".png" if i == LOGO else ".jpg"
        for d in image_dirs:
            p = os.path.join(d, i + ext)
            if os.path.exists(p):
                shutil.copyfile(p, os.path.join(img_dir, i + ext)); break
        else:
            missing.append(i)
    removed = 0
    for f in os.listdir(img_dir):
        if f.split(".")[0] not in ids:
            os.remove(os.path.join(img_dir, f)); removed += 1
    print(f"index.html written; {len(ids)} images used, {removed} removed, missing: {missing}")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
