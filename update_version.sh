#!/bin/bash
V=`npm run env | grep npm_package_version | cut -f 2 -d=`
# number of commits since last tag
#N=`git rev-list $(git describe --abbrev=0)..HEAD --count`
#branch
B=`git rev-parse --abbrev-ref HEAD`
#short git commit description
S=`git rev-parse --short HEAD`
#H=`git describe --always --long`
# compose a version compatible with git describe, but with newer version
H="$V-g$S-$B"
C=`git rev-parse --verify HEAD`
echo "New version in src/version.py: $H"
VERSION_PY=$(cat <<EOF
__version__ = "$V"
__long_version__ = "$H"
__git_commit__ = "$C"
__git_branch__ = "$B"
EOF
)
echo "$VERSION_PY" > src/version.py
echo
echo "Satified with this release? Do a "
echo "   git push && git push --tags"
echo "to push this release to the remote repository"
