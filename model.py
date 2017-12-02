import tensorflow as tf
from tensorflow.python.ops.rnn_cell import GRUCell
from tensorflow.python.ops.nn import bidirectional_dynamic_rnn
from func import dropout, stacked_gru, pointer, dot_attention, summ


class Model(object):
    def __init__(self, config, batch, word_mat=None, char_mat=None, trainable=True):
        self.config = config
        self.global_step = tf.get_variable('global_step', shape=[], dtype=tf.int32,
                                           initializer=tf.constant_initializer(0), trainable=False)
        self.c, self.q, self.ch, self.qh, self.y1, self.y2, self.qa_id = batch
        self.is_train = tf.get_variable(
            "is_train", shape=[], dtype=tf.bool, trainable=False)
        self.word_mat = dropout(tf.get_variable("word_mat", initializer=tf.constant(
            word_mat, dtype=tf.float32), trainable=False), keep_prob=config.emb_keep_prob, is_train=self.is_train, mode="embedding")
        self.char_mat = dropout(tf.get_variable("char_mat", initializer=tf.constant(
            char_mat, dtype=tf.float32)), keep_prob=config.emb_keep_prob, is_train=self.is_train, mode="embedding")

        self.c_mask = tf.cast(self.c, tf.bool)
        self.q_mask = tf.cast(self.q, tf.bool)
        self.c_len = tf.reduce_sum(tf.cast(self.c_mask, tf.int32), axis=1)
        self.q_len = tf.reduce_sum(tf.cast(self.q_mask, tf.int32), axis=1)

        self.ch_len = tf.reshape(tf.reduce_sum(
            tf.cast(tf.cast(self.ch, tf.bool), tf.int32), axis=2), [-1])
        self.qh_len = tf.reshape(tf.reduce_sum(
            tf.cast(tf.cast(self.qh, tf.bool), tf.int32), axis=2), [-1])

        self.ready()

        if trainable:
            self.lr = tf.get_variable(
                "lr", shape=[], dtype=tf.float32, trainable=False)
            self.opt = tf.train.AdadeltaOptimizer(
                learning_rate=self.lr, epsilon=1e-6)
            grads = self.opt.compute_gradients(self.loss)
            gradients, variables = zip(*grads)
            capped_grads, _ = tf.clip_by_global_norm(
                gradients, config.grad_clip)
            self.train_op = self.opt.apply_gradients(
                zip(capped_grads, variables), global_step=self.global_step)

    def ready(self):
        config = self.config
        N, PL, QL, CL, d, dc, dg = config.batch_size, config.para_limit, config.ques_limit, config.char_limit, config.hidden, config.char_dim, config.char_hidden

        with tf.variable_scope("emb"):
            with tf.variable_scope("char"):
                ch_emb = tf.reshape(tf.nn.embedding_lookup(
                    self.char_mat, self.ch), [-1, CL, dc])
                qh_emb = tf.reshape(tf.nn.embedding_lookup(
                    self.char_mat, self.qh), [-1, CL, dc])
                ch_emb = dropout(ch_emb, keep_prob=config.keep_prob,
                                 is_train=self.is_train)
                qh_emb = dropout(qh_emb, keep_prob=config.keep_prob,
                                 is_train=self.is_train)

                cell_fw = GRUCell(dg)
                cell_bw = GRUCell(dg)

                _, (qh_fw, qh_bw) = bidirectional_dynamic_rnn(
                    cell_fw, cell_bw, qh_emb, self.qh_len, dtype=tf.float32)
                tf.get_variable_scope().reuse_variables()
                _, (ch_fw, ch_bw) = bidirectional_dynamic_rnn(
                    cell_fw, cell_bw, ch_emb, self.ch_len, dtype=tf.float32)
                ch_emb = tf.reshape(
                    tf.concat([ch_fw, ch_bw], axis=1), [-1, PL, 2 * dg])
                qh_emb = tf.reshape(
                    tf.concat([qh_fw, qh_bw], axis=1), [-1, QL, 2 * dg])

            with tf.name_scope("word"):
                c_emb = tf.nn.embedding_lookup(self.word_mat, self.c)
                q_emb = tf.nn.embedding_lookup(self.word_mat, self.q)
            c_emb = tf.concat([c_emb, ch_emb], axis=2)
            q_emb = tf.concat([q_emb, qh_emb], axis=2)

        with tf.variable_scope("encoder"):
            c = stacked_gru(c_emb, N, d, num_layers=3, seq_len=self.c_len, keep_prob=config.keep_prob,
                            is_train=self.is_train)
            tf.get_variable_scope().reuse_variables()
            q = stacked_gru(q_emb, N, d, num_layers=3, seq_len=self.q_len, keep_prob=config.keep_prob,
                            is_train=self.is_train)

        with tf.variable_scope("attention"):
            qc_att = dot_attention(c, q, mask=self.q_mask, hidden=d,
                                   keep_prob=config.keep_prob, is_train=self.is_train)
            att = stacked_gru(qc_att, N, d, num_layers=1, seq_len=self.c_len,
                              keep_prob=config.keep_prob, is_train=self.is_train)

        with tf.variable_scope("match"):
            self_att = dot_attention(
                att, att, mask=self.c_mask, hidden=d, keep_prob=config.keep_prob, is_train=self.is_train)
            match = stacked_gru(self_att, N, d, num_layers=1, seq_len=self.c_len,
                                keep_prob=config.keep_prob, is_train=self.is_train)

        with tf.variable_scope("pointer"):
            d_q = dropout(q[:, :, -2 * d:],
                          keep_prob=config.keep_prob, is_train=self.is_train)
            d_match = dropout(match, keep_prob=config.keep_prob,
                              is_train=self.is_train)
            init = summ(d_q, d, mask=self.q_mask)
            hidden = init.get_shape().as_list()[-1]
            with tf.variable_scope("fw"):
                cell_fw = GRUCell(hidden)
                inp, logits1_fw = pointer(d_match, init, d, mask=self.c_mask)
                _, state = cell_fw(inp, init)
                tf.get_variable_scope().reuse_variables()
                _, logits2_fw = pointer(d_match, state, d, mask=self.c_mask)
            with tf.variable_scope("bw"):
                cell_bw = GRUCell(hidden)
                inp, logits2_bw = pointer(d_match, init, d, mask=self.c_mask)
                _, state = cell_bw(inp, init)
                tf.get_variable_scope().reuse_variables()
                _, logits1_bw = pointer(d_match, state, d, mask=self.c_mask)
            logits1 = (logits1_fw + logits1_bw) / 2.
            logits2 = (logits2_fw + logits2_bw) / 2.

        with tf.variable_scope("predict"):
            outer = tf.matmul(tf.expand_dims(tf.nn.softmax(logits1), axis=2),
                              tf.expand_dims(tf.nn.softmax(logits2), axis=1))
            outer = tf.matrix_band_part(outer, 0, 15)
            self.yp1 = tf.argmax(tf.reduce_max(outer, axis=2), axis=1)
            self.yp2 = tf.argmax(tf.reduce_max(outer, axis=1), axis=1)
            losses = tf.nn.softmax_cross_entropy_with_logits(
                logits=logits1, labels=self.y1)
            losses2 = tf.nn.softmax_cross_entropy_with_logits(
                logits=logits2, labels=self.y2)
            self.loss = tf.reduce_mean(losses + losses2)

    def get_loss(self):
        return self.loss

    def get_global_step(self):
        return self.global_step