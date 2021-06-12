import glob

from jinja2 import Environment, FileSystemLoader

for file in glob.glob("site/*.*"):
    if file.endswith('.tmpl'):
        continue
    f = open(file, "r").read()
    tmpl = Environment(loader=FileSystemLoader("site/")).from_string(f)
    out = file.replace('site/', 'build/')
    print(out)
    with open(out, 'w') as fw:
        fw.write(tmpl.render())
