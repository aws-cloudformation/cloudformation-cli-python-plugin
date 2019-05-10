import unittest

from cfn_resource.base_resource_model import BaseResourceModel


class TestResourceModel(unittest.TestCase):

    def test_new(self):
        model = BaseResourceModel.new()
        self.assertEqual({}, model.__dict__)
