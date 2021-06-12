# datastation.multiprocess.io

This repo controls the configuration and deployment of both
datastation.multiprocess.io and app.datastation.multiprocess.io (the
in-browser demo).

## To build the site

```
./scripts/build_site.sh
```

To run the site locally:

```
python3 -m http.server --directory build 8080
```

## To deploy

This deploys both the site and the demo.

You need to have your public key in the `fedora` user's .ssh
directory.

```
./scripts/deploy.sh
```
