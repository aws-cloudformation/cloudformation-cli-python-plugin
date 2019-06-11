import unittest

from cfn_resource.exceptions import Codes, InternalFailure


class TestCodes(unittest.TestCase):

    def test_is_handled(self):
        self.assertEqual(False, Codes.is_handled(ValueError()))
        self.assertEqual(True, Codes.is_handled(InternalFailure()))
