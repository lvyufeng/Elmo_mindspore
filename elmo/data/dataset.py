import glob
import random
import numpy as np
from mindspore.log import logging


def _get_batch(generator, batch_size, num_steps, max_word_length):
    """
    Read batches of input.
    """
    cur_stream = [None] * batch_size
    no_more_data = False

    while True:
        inputs = np.zeros([batch_size, num_steps], np.int32)
        if max_word_length is not None:
            char_inputs = np.zeros([batch_size, num_steps, max_word_length], np.int32)
        else:
            char_inputs = None

        targets = np.zeros([batch_size, num_steps], np.int32)
        for i in range(batch_size):
            cur_pos = 0
            while cur_pos < num_steps:
                if cur_stream[i] is None or len(cur_stream[i][0]) <= 1:
                    try:
                        cur_stream[i] = list(next(generator))
                    except StopIteration:
                        no_more_data = True
                        break
                
                how_many = min(len(cur_stream[i][0]) - 1, num_steps - cur_pos)
                next_pos = cur_pos + how_many

                inputs[i, cur_pos:next_pos] = cur_stream[i][0][:how_many]
                if max_word_length is not None:
                    char_inputs[i, cur_pos:next_pos] = cur_stream[i][1][:how_many]

                targets[i, cur_pos:next_pos] = cur_stream[i][0][1:how_many+1]
                
                cur_pos = next_pos

                cur_stream[i][0] = cur_stream[i][0][how_many:]
                if max_word_length is not None:
                    cur_stream[i][1] = cur_stream[i][1][how_many:]

        if no_more_data:
            # There is no more data.  Note: this will not return data
            # for the incomplete batch
            break

        X = {'token_ids': inputs, 'tokens_characters': char_inputs,
                 'next_token_id': targets}

        yield X                
                
class LMDataset(object):
    """
    Hold a language model dataset.

    A dataset is a list of tokenized files. Each file contains one sentence per line.
    Each sentence is pre-tokenized and white space jointed
    """
    def __init__(self, filepattern, vocab, test=False, shuffle_on_load=False, reverse=False):
        self._vocab = vocab
        self._all_shards = glob.glob(filepattern)
        logging.info('Found %d shards at %s' % (len(self._all_shards), filepattern))
        self._shards_to_choose = []
        self._reverse = reverse

        self._test = test
        self._shuffle_on_load = shuffle_on_load
        self._use_char_inputs = hasattr(vocab, 'encode_chars')

        self._ids = self._load_random_shard()
        

    def _choose_random_shard(self):
        if len(self._shards_to_choose) == 0:
            self._shards_to_choose = list(self._all_shards)
            random.shuffle(self._shards_to_choose)
        shard_name = self._shards_to_choose.pop()
        return shard_name

    def _load_random_shard(self):
        if self._test:
            if len(self._all_shards) == 0:
                raise StopIteration
            else:
                shard_name = self._all_shards.pop()
        else:
            shard_name = self._choose_random_shard()
        
        ids = self._load_shard(shard_name)
        self._i = 0
        self._nids = len(ids)
        return ids
    
    def _load_shard(self, shard_name):
        logging.info('Loading data from: %s' % shard_name)
        with open(shard_name) as f:
            sentences = f.readlines()

        if self._reverse:
            sentences_reverse = []
            for sentence in sentences:
                splitted = sentence.split()
                splitted.reverse()
                sentences_reverse.append(' '.join(splitted))
            sentences = sentences_reverse

        if self._shuffle_on_load:
            random.shuffle(sentences)
        
        ids = [self.vocab.encode(sentence, self._reverse) for sentence in sentences]
        if self._use_char_inputs:
            chars_ids = [self.vocab.encode_chars(sentence, self._reverse) for sentence in sentences]
        else:
            chars_ids = [None] * len(ids)
        logging.info('Loaded %d sentences.' % len(ids))
        return list(zip(ids, chars_ids))
    
    def get_sentence(self):
        while True:
            if self._i == self._nids:
                self._ids = self._load_random_shard()
            ret = self._ids[self._i]
            self._i += 1
            yield ret

    @property
    def max_word_length(self):
        if self._use_char_inputs:
            return self._vocab.max_word_length
        else:
            return None
    
    def iter_batches(self, batch_size, num_steps):
        for X in _get_batch(self.get_sentence(), batch_size, num_steps, 
                            self.max_word_length):
            # token_ids(batch_size, num_steps)
            # char_inputs = (batch_size, num_steps, max_word_length)
            # targets = Word id of next word (batch_size, num_steps)
            yield X
    
    @property
    def vocab(self):
        return self._vocab
    
class BidirectionalLMDataset(object):
    def __init__(self, filepattern, vocab, test=False, shuffle_on_load=False):
        '''
        bidirectional version of LMDataset
        '''
        self._data_forward = LMDataset(filepattern, vocab, test=test, reverse=False,
                                        shuffle_on_load=shuffle_on_load)
        self._data_backward = LMDataset(filepattern, vocab, test=test, reverse=True,
                                        shuffle_on_load=shuffle_on_load)
                                        
    def iter_batches(self, batch_size, num_steps):
        max_word_length = self._data_forward.max_word_length
        for X, Xr in zip(
            _get_batch(self._data_forward.get_sentence(), batch_size,
                        num_steps, max_word_length),
            _get_batch(self._data_backward.get_sentence(), batch_size,
                        num_steps, max_word_length)
        ):
            for k, v in Xr.items():
                X[k + '_reverse'] = v
            yield X