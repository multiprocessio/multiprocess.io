rm -rf build && mkdir build
python3 -m venv .env
.env/bin/pip install -r requirements.txt
.env/bin/python ./scripts/build_site.py
cp assets/* build
