#!/usr/bin/env bash

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

function exit_with_usage {
  cat << EOF
release - Creates build distributions from a git commit hash or from HEAD.
SYNOPSIS
usage: release.sh [--release-prepare | --release-publish]

DESCRIPTION
Perform necessary tasks for a Jupyter Enterprise Gateway release

release-prepare: This form creates a release tag and builds the release distribution artifacts.

--release-prepare --currentVersion="2.0.0.dev0" --releaseVersion="2.0.0" --developmentVersion="2.1.0.dev1" --previousVersion="2.0.0rc2" [--tag="v2.0.0"] [--gitCommitHash="a874b73"]

release-publish: Publish the release distribution artifacts to PyPI.

--release-publish --tag="v2.0.0"

OPTIONS
--currentVersion     - Current development version
--releaseVersion     - Release identifier used when publishing
--developmentVersion - Release identifier used for next development cycle
--previousVersion    - Release identifier left in download links from previous release
--tag                - Release Tag identifier used when taging the release, default 'v$releaseVersion'
--gitCommitHash      - Release tag or commit to build from, default master HEAD
--dryRun             - Dry run only, mostly used for testing.

EXAMPLES
release.sh --release-prepare --currentVersion="2.0.0.dev0" --releaseVersion="2.0.0" --developmentVersion="2.1.0.dev1" --previousVersion="2.0.0rc2"
release.sh --release-prepare --currentVersion="2.0.0.dev0" --releaseVersion="2.0.0" --developmentVersion="2.1.0.dev1" --previousVersion="2.0.0rc2" --tag="v2.0.0" --dryRun

release.sh --release-publish --gitTag="v2.0.0"
EOF
  exit 1
}

set -e

if [ $# -eq 0 ]; then
  exit_with_usage
fi


# Process each provided argument configuration
while [ "${1+defined}" ]; do
  IFS="=" read -ra PARTS <<< "$1"
  case "${PARTS[0]}" in
    --release-prepare)
      GOAL="release-prepare"
      RELEASE_PREPARE=true
      shift
      ;;
    --release-publish)
      GOAL="release-publish"
      RELEASE_PUBLISH=true
      shift
      ;;
    --release-snapshot)
      GOAL="release-snapshot"
      RELEASE_SNAPSHOT=true
      shift
      ;;
    --gitCommitHash)
      GIT_REF="${PARTS[1]}"
      shift
      ;;
    --gitTag)
      GIT_TAG="${PARTS[1]}"
      shift
      ;;
    --currentVersion)
      CURRENT_VERSION="${PARTS[1]}"
      shift
      ;;
    --releaseVersion)
      RELEASE_VERSION="${PARTS[1]}"
      shift
      ;;
    --developmentVersion)
      DEVELOPMENT_VERSION="${PARTS[1]}"
      shift
      ;;
    --previousVersion)
      PREVIOUS_VERSION="${PARTS[1]}"
      shift
      ;;
    --tag)
      RELEASE_TAG="${PARTS[1]}"
      shift
      ;;
    --dryRun)
      DRY_RUN="-DdryRun=true"
      shift
      ;;

    *help* | -h)
      exit_with_usage
     exit 0
     ;;
    -*)
     echo "Error: Unknown option: $1" >&2
     exit 1
     ;;
    *)  # No more options
     break
     ;;
  esac
done


if [[ "$RELEASE_PREPARE" == "true" && -z "$RELEASE_VERSION" ]]; then
    echo "ERROR: --releaseVersion must be passed as an argument to run this script"
    exit_with_usage
fi

if [[ "$RELEASE_PREPARE" == "true" && -z "$DEVELOPMENT_VERSION" ]]; then
    echo "ERROR: --developmentVersion must be passed as an argument to run this script"
    exit_with_usage
fi

if [[ "$RELEASE_PREPARE" == "true" && -z "$PREVIOUS_VERSION" ]]; then
    echo "ERROR: --previousVersion must be passed as an argument to run this script"
    exit_with_usage
fi

if [[ "$RELEASE_PUBLISH" == "true"  ]]; then
    if [[ "$GIT_REF" && "$GIT_TAG" ]]; then
        echo "ERROR: Only one argumented permitted when publishing : --gitCommitHash or --gitTag"
        exit_with_usage
    fi
    if [[ -z "$GIT_REF" && -z "$GIT_TAG" ]]; then
        echo "ERROR: --gitCommitHash OR --gitTag must be passed as an argument to run this script"
        exit_with_usage
    fi
fi

if [[ "$RELEASE_PUBLISH" == "true" && "$DRY_RUN" ]]; then
    echo "ERROR: --dryRun not supported for --release-publish"
    exit_with_usage
fi

# Commit ref to checkout when building
GIT_REF=${GIT_REF:-HEAD}
if [[ "$RELEASE_PUBLISH" == "true" && "$GIT_TAG" ]]; then
    GIT_REF="tags/$GIT_TAG"
fi

BASE_DIR=$(pwd)
WORK_DIR=$(pwd)/build/release
SOURCE_DIR=$(pwd)/build/release/enterprise_gateway

if [ -z "$RELEASE_TAG" ]; then
  RELEASE_TAG="v$RELEASE_VERSION"
fi


echo "  "
echo "Base directory:   $BASE_DIR"
echo "Work directory:   $WORK_DIR"
echo "Source directory: $SOURCE_DIR"
echo "  "
echo "-------------------------------------------------------------"
echo "------- Release preparation with the following parameters ---"
echo "-------------------------------------------------------------"
echo "Executing            ==> $GOAL"
echo "Git reference        ==> $GIT_REF"
echo "Release version      ==> $RELEASE_VERSION"
echo "Development version  ==> $DEVELOPMENT_VERSION"
echo "Tag                  ==> $RELEASE_TAG"
if [ "$DRY_RUN" ]; then
   echo "dry run ?           ==> true"
fi


set -o xtrace

function checkout_code {
    rm -rf $WORK_DIR
    mkdir -p $WORK_DIR
    cd $WORK_DIR
    # Checkout code
    git clone git@github.com:jupyter/enterprise_gateway.git
    cd enterprise_gateway
    git checkout $GIT_REF
    git_hash=`git rev-parse --short HEAD`
    echo "Checked out Jupyter Enterprise Gateway git hash $git_hash"
}

function update_version_to_release {
    cd $SOURCE_DIR

    # Update tbump-managed versions
    pip install tbump
    tbump --non-interactive --no-tag --no-push $RELEASE_VERSION

    # Update Kubernetes Helm chart and values files (tbump will handle appVersion in Chart.yaml)
    # We need to inject "-" prior to pre-release suffices for 'version:' since it follows strict semantic version rules.
    # For example 3.0.0rc1 -> 3.0.0-rc1
    k8s_version=`echo $RELEASE_VERSION | sed 's/\([0-9]\)\([a-z]\)/\1-\2/'`
    sed -i .bak "s@version: [0-9,\.,a-z,-]*@version: $k8s_version@g" etc/kubernetes/helm/enterprise-gateway/Chart.yaml

    sed -i .bak "s@elyra/enterprise-gateway:dev@elyra/enterprise-gateway:$RELEASE_VERSION@g" etc/kubernetes/helm/enterprise-gateway/values.yaml
    sed -i .bak "s@elyra/kernel-image-puller:dev@elyra/kernel-image-puller:$RELEASE_VERSION@g" etc/kubernetes/helm/enterprise-gateway/values.yaml

    # Update Docker compose version
    sed -i .bak "s@elyra/enterprise-gateway:dev@elyra/enterprise-gateway:$RELEASE_VERSION@g" etc/docker/docker-compose.yml
    sed -i .bak "s@elyra/kernel-image-puller:dev@elyra/kernel-image-puller:$RELEASE_VERSION@g" etc/docker/docker-compose.yml

    # Update documentation - this is a one-way change since links will not be valid in dev "releases".
    find docs/source -name "*.md" -type f -exec sed -i .bak "s@$PREVIOUS_VERSION@$RELEASE_VERSION@g" {} \;
}

function update_version_to_development {
    cd $SOURCE_DIR

    # Update tbump-managed versions
    pip install tbump
    tbump --non-interactive --no-tag --no-push $DEVELOPMENT_VERSION

    # Update Kubernetes Helm chart and values files (tbump will handle appVersion in Chart.yaml)
    # We need to replace ".devN" suffix with "-devN for 'version:' since it follows strict semantic version rules.
    # For example 3.0.0.dev1 -> 3.0.0-dev1
    k8s_version=`echo $DEVELOPMENT_VERSION | sed 's/\.\(dev\)/-\1/'`
    sed -i .bak "s@version: [0-9,\.,a-z,-]*@version: $k8s_version@g" etc/kubernetes/helm/enterprise-gateway/Chart.yaml

    sed -i .bak "s@elyra/enterprise-gateway:$RELEASE_VERSION@elyra/enterprise-gateway:dev@g" etc/kubernetes/helm/enterprise-gateway/values.yaml
    sed -i .bak "s@elyra/kernel-image-puller:$RELEASE_VERSION@elyra/kernel-image-puller:dev@g" etc/kubernetes/helm/enterprise-gateway/values.yaml

    # Update Docker compose version
    sed -i .bak "s@elyra/enterprise-gateway:$RELEASE_VERSION@elyra/enterprise-gateway:dev@g" etc/docker/docker-compose.yml
    sed -i .bak "s@elyra/kernel-image-puller:$RELEASE_VERSION@elyra/kernel-image-puller:dev@g" etc/docker/docker-compose.yml
}

if [[ "$RELEASE_PREPARE" == "true" ]]; then
    echo "Preparing release $RELEASE_VERSION ($RELEASE_VERSION)"
    # Checkout code
    checkout_code

    update_version_to_release

    cd $SOURCE_DIR
    if [ -z "$DRY_RUN" ]; then
        make MULTIARCH_BUILD=y clean dist release docs docker-images
    else
        make clean dist docs docker-images
    fi
    mkdir -p $WORK_DIR/$RELEASE_TAG
    cp $SOURCE_DIR/dist/jupyter_enterprise_gateway* $WORK_DIR/$RELEASE_TAG

    # Build and prepare the release
    git commit -a -m "Prepare release $RELEASE_VERSION"
    git tag $RELEASE_TAG

    update_version_to_development

    cd $SOURCE_DIR
    mv dist $WORK_DIR/$RELEASE_TAG
    mv build $WORK_DIR/$RELEASE_TAG
    make clean dist docs

    # Build next development iteraction
    git commit -a -m"Prepare for next development interaction $DEVELOPMENT_VERSION"

    if [ -z "$DRY_RUN" ]; then
        git push
        git push --tags
    fi

    cd "$BASE_DIR" #exit target

    exit 0
fi


if [[ "$RELEASE_PUBLISH" == "true" ]]; then
    echo "Publishing release $RELEASE_VERSION"
    # Checkout code
    checkout_code
    cd $SOURCE_DIR
    git checkout $RELEASE_TAG
    git clean -d -f -x

    make clean dist docs

    cd "$BASE_DIR" #exit target

    exit 0
fi

cd "$BASE_DIR" #return to base dir
rm -rf target
echo "ERROR: wrong execution goals"
exit_with_usage
