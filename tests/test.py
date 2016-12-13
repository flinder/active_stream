# Run all tests for the application

import unittest


## Streaming
class TestListener(unittest.TestCase):

    def setUp(self):
        pass
    
    def test_on_status(self):
        self.asserTrue(True)

    def test_on_er(self):
        # make sure the shuffled sequence does not lose any elements
        random.shuffle(self.seq)
        self.seq.sort()
        self.assertEqual(self.seq, list(range(10)))

## Text Processing


## Classification


## Training


## Annotation

if __name__ == '__main__':
    unittest.main()


