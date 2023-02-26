import unittest


class TestStringMethods(unittest.TestCase):

    def setUp(self):
        pass

    def test_cpu_usage_widget(self):
        from tsvi.mth5_tsviewer.helpers import cpu_usage_widget
        cpu_usage_widget()

    def test_memory_usage_widget(self):
        from tsvi.mth5_tsviewer.helpers import memory_usage_widget
        memory_usage_widget()

    def test_isupper(self):
        pass
        # self.assertTrue('FOO'.isupper())
        # self.assertFalse('Foo'.isupper())

    def test_split(self):
        s = 'hello world'
        self.assertEqual(s.split(), ['hello', 'world'])
        # check that s.split fails when the separator is not a string
        with self.assertRaises(TypeError):
            s.split(2)

if __name__ == '__main__':
    unittest.main()