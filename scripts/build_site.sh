find . -name '*~' -delete

# Grab docs repo
rm -rf datastation-documentation
git clone git@github.com:multiprocessio/datastation-documentation

rm -rf build && mkdir -p build/blog build/docs
python3 -m venv .env
.env/bin/pip install -r requirements.txt
.env/bin/python ./scripts/build_site.py
cp assets/* build

# Update stars count
projects="datastation preview shape cssplus"
for project in $projects; do
    stars="$(curl -L https://api.github.com/repos/multiprocessio/$project | jq '.stargazers_count')"
    sed -i 's/STARS/'"$stars"'/g' build/stars/$project.html
done
