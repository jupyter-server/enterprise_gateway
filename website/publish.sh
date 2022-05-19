#!/usr/bin/env bash

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.


set -e

BASE_DIR=$(pwd)
WORK_DIR=$(pwd)/build
SOURCE_DIR=$(pwd)/build/enterprise_gateway/website
HTML_DIR=$(pwd)/build/website


echo "  "
echo "-------------------------------------------------------------"
echo "-------       Build and publish project website       -------"
echo "-------------------------------------------------------------"
echo "  "
echo "Base directory:   $BASE_DIR"
echo "Work directory:   $WORK_DIR"
echo "Source directory: $SOURCE_DIR"
echo "HTML directory:   $HTML_DIR"
echo "  "

set -o xtrace


function checkout_code {
    rm -rf $WORK_DIR
    mkdir -p $WORK_DIR
    cd $WORK_DIR
    # Checkout code
    git clone git@github.com:jupyter/enterprise_gateway.git
    cd enterprise_gateway
    git_hash=`git rev-parse --short HEAD`
    echo "Checked out Jupyter Enterprise Gateway git hash $git_hash"
}

function build_website {
    rm -rf $HTML_DIR
    mkdir -p $HTML_DIR
    cd $SOURCE_DIR
    jekyll clean
    jekyll build -d $HTML_DIR
}

function publish_website {
    cd $WORK_DIR/enterprise_gateway
    git checkout gh-pages
    git branch --set-upstream-to=origin/gh-pages gh-pages
    git pull --rebase
    rm -rf *
    git checkout .gitignore
    git checkout README.md
    cp -r $HTML_DIR/ $WORK_DIR/enterprise_gateway
    git add *
    git commit -a -m"Publishing website using commit $git_hash"
    echo "Publishing website using commit $git_hash"
    git push origin gh-pages
}

echo "Preparing to publish website..."

checkout_code

build_website

publish_website


echo "Website published..."
echo "   https://jupyter.org/enterprise_gateway/"
echo "   https://jupyter.github.io/enterprise_gateway/"


cd "$BASE_DIR" #return to base dir
