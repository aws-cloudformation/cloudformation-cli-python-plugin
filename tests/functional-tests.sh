#!/usr/bin/env bash -e

function F_cleanup() {
        EXITCODE=$?
        if [[ -z ${BASE_DIR+x} ]]; then
            exit ${EXITCODE}
        else
            if [[ "${EXITCODE}" != "0" ]] ; then cat ${BASE_DIR}/rpdk.log || True ; fi
            rm -rf ${BASE_DIR}
            exit ${EXITCODE}
        fi
}

trap F_cleanup EXIT

# Absolute path to runtime wrapper package, if not specified will use what init places into requirements.txt
RUNTIME_WRAPPER_PATH=$(pwd)/${1}
RESOURCE_TYPE=Org::Segment::Product
PACKAGE_NAME=$(echo $RESOURCE_TYPE | awk '{print tolower($0)}'  | sed 's/::/_/g')
SCHEMA_FILE_NAME=$(echo $RESOURCE_TYPE | awk '{print tolower($0)}'  | sed 's/::/-/g').json
SCRIPT_DIR=$(cd ${BASH_SOURCE%/*} ; pwd)
PY_VER=3.7



## Package zip file
function package_zip() {
    mkdir -p ${BASE_DIR}/target/
    rm ${BASE_DIR}/target/${PACKAGE_NAME}.zip 2> /dev/null || True
    zip -r ${BASE_DIR}/target/${PACKAGE_NAME}.zip . > /dev/null
    cd ${BASE_DIR}
    zip -r ${BASE_DIR}/target/${PACKAGE_NAME}.zip ./resource_model > /dev/null
    if [[ "${RUNTIME_WRAPPER_PATH}" != "" ]] ; then
        echo ${RUNTIME_WRAPPER_PATH} > requirements.txt
    fi
    pip install -qqq -r requirements.txt -t ./build/
    cd ./build/
    zip -r --exclude='*.dist-info*' --exclude='pip/*' --exclude='setuptools/*' --exclude='pkg_resources/*' \
        --exclude='easy_install.py' --exclude='*__pycache__*' \
        ${BASE_DIR}/target/${PACKAGE_NAME}.zip . > /dev/null
}

## run tests

for dir in $(ls -1 ${SCRIPT_DIR}/data/) ; do
    for test in $(ls -1 ${SCRIPT_DIR}/data/${dir}/*.json) ; do
        test_file=$(echo ${test} | awk -F / '{print $NF}')
        BASE_DIR=$(mktemp -d)
        cd ${BASE_DIR}
        echo "Org::Segment::Product
        2" | cfn-cli init > /dev/null # Assumes only the python plugin is installed, python36 is option 1, python37 option 2
        echo "" > ${BASE_DIR}/rpdk.log # empty log if cfn-cli execution successful
        cfn-cli generate > /dev/null # run this just to be sure generate works when called by itself
        echo "" > ${BASE_DIR}/rpdk.log # empty log if cfn-cli execution successful
        mkdir ${BASE_DIR}/sam_output/
        # get generic expected response from folder
        expected_output=$(cat ${SCRIPT_DIR}/data/${dir}/expected)
        # if defined get expected response for this request
        [[ -f ${SCRIPT_DIR}/data/${dir}/${test_file}.expected ]] && expected_output=$(cat ${SCRIPT_DIR}/data/${dir}/${test_file}.expected) || True
        # set handler path
        handler_path=${BASE_DIR}/${PACKAGE_NAME}
        [[ -d ${SCRIPT_DIR}/data/${dir}/handler ]] && handler_path=${SCRIPT_DIR}/data/${dir}/handler || True
        [[ -d ${SCRIPT_DIR}/data/${dir}/${test_file}.handler ]] && handler_path=${SCRIPT_DIR}/data/${dir}/${test_file}.handler || True
        cd ${handler_path}
        package_zip
        echo "invoking sam local with event data/${dir}/${test_file}"
        cd ${BASE_DIR}
        sam local invoke -e ${SCRIPT_DIR}/data/${dir}/${test_file} > ${BASE_DIR}/sam_output/${test_file}.outp 2> ${BASE_DIR}/sam_output/${test_file}.outp_stderr
        received_output=$(cat ${BASE_DIR}/sam_output/${test_file}.outp)
        if [[ "${received_output}" != "${expected_output}" ]] ; then
            echo "-------------------------------------------"
            echo "Test failed. Expected output does not match"
            echo "-------------------------------------------"
            echo "EXPECTED: ${expected_output}"
            echo "RECEIVED: ${received_output}"
            echo "-------------------------------------------"
            echo "STDERR Output:"
            echo "-------------------------------------------"
            cat ${BASE_DIR}/sam_output/${test_file}.outp_stderr
            exit 1
        else
            echo "Test passed"
        fi
    done
done

exit 0
