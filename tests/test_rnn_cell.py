import unittest
import mindspore
import numpy as np
from mindspore import Tensor
from elmo.nn.rnn_cells import LSTMCellWithProjection, LSTMCell

class TestRNNCells(unittest.TestCase):
    def test_lstm_cell(self):
        inputs = Tensor(np.random.randn(1, 10), mindspore.float32)
        hx = Tensor(np.random.randn(1, 20), mindspore.float32)
        cx = Tensor(np.random.randn(1, 20), mindspore.float32)
        cell = LSTMCellWithProjection(10, 20)

        hy, cy = cell(inputs, (hx, cx))

        assert hy.shape[-1] == 20

    def test_lstm_cell_with_projection(self):
        inputs = Tensor(np.random.randn(1, 10), mindspore.float32)
        hx = Tensor(np.random.randn(1, 20), mindspore.float32)
        cx = Tensor(np.random.randn(1, 20), mindspore.float32)
        cell = LSTMCellWithProjection(10, 20, True, 1, 30, 1)

        hy, cy = cell(inputs, (hx, cx))

        assert hy.shape[-1] == 30