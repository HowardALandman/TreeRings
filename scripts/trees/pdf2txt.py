import sys, pypdf
src, dst = sys.argv[1], sys.argv[2]
r = pypdf.PdfReader(src)
with open(dst, "w") as f:
    for i, p in enumerate(r.pages):
        f.write(f"\n[[page {i+1}]]\n" + (p.extract_text() or ""))
print(src.rsplit("/",1)[-1], len(r.pages), "pages")
