import sys
import argparse
import unittest
import os
from nb_entity import NBCodeEntity
from itest_notebook import NotebookTestCase


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def parse_arg():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_kernels', default=None)
    parser.add_argument('--notebook_files', default=None)
    parser.add_argument('--notebook_dir', default='../notebooks')
    parser.add_argument('--continue_when_error', type=str2bool, default=True)
    parser.add_argument('--host', default='localhost:8888')
    parser.add_argument('--username', default=None)
    parser.add_argument('--enforce_impersonation', type=str2bool, default=False)

    return parser.parse_args()


def init_nb_test_case(args):
    target_kernels = None
    if args.target_kernels is not None:
        target_kernels = set(str(args.target_kernels).split(","))
    nb_entities_list = list([])
    if args.notebook_files is not None:
        # If any target notebook_file is provided, test only those files
        notebook_file_list = str(args.notebook_files).split(",")
        for nb_file_path in notebook_file_list:
            nb_entity = NBCodeEntity(nb_file_path)
            if not target_kernels or nb_entity.kernel_spec_name in target_kernels:
                nb_entities_list.append(nb_entity)
    else:
        # Otherwise, test all ipynb files in notebook_dir provided, and default is ../notebooks
        for nb_file_path in os.listdir(args.notebook_dir):
            if nb_file_path.endswith("pynb"):
                nb_file_path = os.path.join(args.notebook_dir, nb_file_path)
                nb_entity = NBCodeEntity(nb_file_path)
                if not target_kernels or nb_entity.kernel_spec_name in target_kernels:
                    nb_entities_list.append(nb_entity)

    if args.enforce_impersonation is not True:
        args.enforce_impersonation = False

    return NotebookTestCase(method, nb_entities_list, **args.__dict__)


if __name__ == '__main__':
    arguments = parse_arg()
    suite = unittest.TestSuite()
    for method in dir(NotebookTestCase):
        if method.startswith("test"):
            suite.addTest(init_nb_test_case(arguments))

    result = unittest.TextTestRunner().run(suite)
    sys.exit(not result.wasSuccessful())
