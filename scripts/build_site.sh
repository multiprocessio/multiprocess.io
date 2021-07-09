find . -name '*~' -delete
rm -rf build && mkdir -p build/blog build/docs
python3 -m venv .env
.env/bin/pip install -r requirements.txt
.env/bin/python ./scripts/build_site.py
cp assets/* build
