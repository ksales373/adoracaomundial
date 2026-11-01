"""Builds a short change report for every update to the public site.

Run by .github/workflows/avisos.yml on each push. It compares the site's settings
before and after the push and lists which church each change belongs to, so the
owner can see at a glance whether anything outside Newark was touched.
"""
import json, re, subprocess, sys

WATCH = "newark"  # church that other editors are allowed to change
NAMES = {}


def config_at(sha):
    try:
        page = subprocess.run(["git", "show", f"{sha}:index.html"], capture_output=True, text=True, check=True).stdout
    except Exception:
        return {}
    m = re.search(r'id="site-config">(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else {}


def by_id(items):
    return {x.get("id") or json.dumps(x, sort_keys=True): x for x in items or []}


def label(loc):
    return NAMES.get(loc, loc) if loc else "Todas as igrejas"


def main(before, after):
    old, new = config_at(before), config_at(after)
    for c in (old, new):
        for l in c.get("locations", []):
            NAMES[l["id"]] = l.get("short") or l.get("label") or l["id"]
    changes = []  # (church id or "", description)

    def diff_list(key, what, locs_of, name_of):
        o, n = by_id(old.get(key)), by_id(new.get(key))
        for k in sorted(set(o) | set(n)):
            if o.get(k) == n.get(k):
                continue
            item = n.get(k) or o.get(k)
            verb = "adicionado" if k not in o else "removido" if k not in n else "alterado"
            locs = set(locs_of(o.get(k) or {})) | set(locs_of(n.get(k) or {}))
            for loc in locs or {""}:
                changes.append((loc, f"{what} {verb}: {name_of(item)}"))

    diff_list("locations", "Dados da igreja", lambda x: [x.get("id", "")], lambda x: x.get("label") or x.get("id"))
    diff_list("staff", "Equipe", lambda x: x.get("locs") or [""], lambda x: x.get("name", "?"))
    diff_list("schedule", "Escala", lambda x: [x.get("loc", "")], lambda x: f"{x.get('date','')} {x.get('type','')}".strip())
    diff_list("albums", "Álbum de fotos", lambda x: [x.get("loc", "")], lambda x: x.get("title") or x.get("id"))
    diff_list("events", "Evento", lambda x: [x.get("loc", "")], lambda x: x.get("title", "?"))
    diff_list("schedThemes", "Tema do mês", lambda x: [x.get("loc", "")], lambda x: f"{x.get('month','')} {x.get('theme','')}")
    handled = {"locations", "staff", "schedule", "albums", "events", "schedThemes"}
    for key in sorted((set(old) | set(new)) - handled):
        if old.get(key) != new.get(key):
            changes.append(("", f"Configuração geral do site: {key}"))

    files = subprocess.run(["git", "diff", "--name-only", before, after], capture_output=True, text=True).stdout.split()
    other_files = [f for f in files if f not in ("index.html", "live.json") and not f.startswith("img/")]
    for f in other_files:
        changes.append(("", f"Arquivo do sistema: {f}"))
    imgs = [f for f in files if f.startswith("img/")]

    outside = sorted({label(l) for l, _ in changes if l != WATCH})
    lines = []
    for loc in sorted({l for l, _ in changes}, key=lambda l: (l != WATCH, label(l))):
        lines.append(f"\n**{label(loc)}**{' ✅' if loc == WATCH else ' ⚠️'}")
        lines += [f"- {d}" for l, d in changes if l == loc]
    if imgs:
        lines.append(f"\n**Fotos:** {len(imgs)} arquivo(s) de imagem")
    if not changes and not imgs:
        lines.append("\nNenhuma mudança de conteúdo (só arquivos técnicos).")
    title = ("⚠️ Site atualizado — mudou fora de Newark: " + ", ".join(outside)) if outside else "Site atualizado — somente Newark"
    open("report_title.txt", "w").write(title[:240])
    open("report.md", "w").write("\n".join(lines))
    print(title)
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
