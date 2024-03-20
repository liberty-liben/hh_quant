import tensorflow as tf
from tensorflow.keras.initializers import glorot_normal, Zeros
from tensorflow.keras.regularizers import l2


class SeNetLayer(tf.keras.layers.Layer):
    def __init__(self, reduction_ratio=3, l2_reg=0.0001, seed=1024, **kwargs):
        super(SeNetLayer, self).__init__(**kwargs)
        self.reduction_ratio = reduction_ratio
        self.l2_reg = l2_reg
        self.seed = seed

    def build(self, input_shape):
        if not isinstance(input_shape, list) or len(input_shape) < 2:
            raise ValueError("A `Senet` layer should be called on a list of at least 2 inputs")
        self.field_size = len(input_shape)
        self.reduction_size = max(1, self.field_size // self.reduction_ratio)
        self.W_1 = self.add_weight(
            shape=(self.field_size, self.reduction_size),
            initializer=glorot_normal(seed=self.seed),
            regularizer=l2(self.l2_reg),
            trainable=True,
            name="senet_w_1",
        )
        self.W_2 = self.add_weight(
            shape=(self.reduction_size, self.field_size),
            initializer=glorot_normal(seed=self.seed),
            regularizer=l2(self.l2_reg),
            trainable=True,
            name="senet_w_2",
        )
        # Be sure to call this somewhere!
        super(SeNetLayer, self).build(input_shape)

    def call(self, inputs, training=False):
        inputs = tf.stack(inputs, axis=1)  # [B, N, dim]
        Z = tf.reduce_mean(inputs, axis=-1)  # [B, N]
        A_1 = tf.nn.relu(tf.matmul(Z, self.W_1))  # [B, x]
        A_2 = tf.nn.sigmoid(tf.matmul(A_1, self.W_2))  # [B, N]
        output = inputs + inputs * tf.expand_dims(A_2, axis=-1)  # skip-connection
        return output  # [B, N, dim]

    def get_config(self):
        config = super(SeNetLayer, self).get_config()
        config.update(
            {
                "reduction_ratio": self.reduction_ratio,
                "l2_reg": self.l2_reg,
                "seed": self.seed,
            }
        )
        return config


# class CrossNetLayer(tf.keras.layers.Layer):
#     def __init__(self, layer_num=2, parameterization="vector", seed=1024, **kwargs):
#         super(CrossNetLayer, self).__init__(**kwargs)
#         self.layer_num = layer_num
#         self.parameterization = parameterization
#         self.seed = seed
#         print("CrossNet parameterization:", self.parameterization)

#     def build(self, input_shape):
#         if len(input_shape) != 2:
#             raise ValueError(f"Unexpected inputs dimensions {len(input_shape)}, expect to be 2 dimensions")

#         # input_shape: (batch_size, feature_dim)
#         feature_dim = int(input_shape[-1])

#         # 配置crossNet的Kernels
#         if self.parameterization == "vector":
#             self.kernels = [
#                 self.add_weight(
#                     shape=(feature_dim, 1),
#                     initializer=glorot_normal(seed=self.seed),
#                     trainable=True,
#                     name=f"crossnet_kernel_{i}",
#                 )
#                 for i in range(self.layer_num)
#             ]
#         elif self.parameterization == "matrix":
#             self.kernels = [
#                 self.add_weight(
#                     shape=(feature_dim, feature_dim),
#                     initializer=glorot_normal(seed=self.seed),
#                     trainable=True,
#                     name=f"crossnet_kernel_{i}",
#                 )
#                 for i in range(self.layer_num)
#             ]
#         else:  # error
#             raise ValueError("parameterization should be 'vector' or 'matrix'")

#         # 配置crossNet的Bias
#         self.bias = [
#             self.add_weight(
#                 shape=(feature_dim, 1),
#                 initializer=Zeros(),
#                 trainable=True,
#                 name=f"crossnet_bias_{i}",
#             )
#             for i in range(self.layer_num)
#         ]

#         # Be sure to call this somewhere!
#         super(CrossNetLayer, self).build(input_shape)

#     def call(self, inputs, **kwargs):
#         x0 = tf.expand_dims(inputs, -1)  # [B, dim, 1]
#         xi = x0  # xi: 上一层的输出[B, dim, 1], 初始化xi=x0
#         for i in range(self.layer_num):
#             if self.parameterization == "vector":
#                 # xi = x0.trans(xi).wi + bi + xi
#                 xiw = tf.tensordot(xi, self.kernels[i], axes=(1, 0))
#                 xi = tf.matmul(x0, xiw) + self.bias[i] + xi
#             elif self.parameterization == "matrix":
#                 xiw = tf.einsum("ij,bjk->bik", self.kernels[i], xi)  # [B, dim, 1]
#                 xi = x0 * (xiw + self.bias[i]) + xi
#             else:  # error
#                 raise ValueError("parameterization should be 'vector' or 'matrix'")
#         output = tf.squeeze(xi, axis=-1)
#         return output

#     def get_config(self):
#         config = super(CrossNetLayer, self).get_config()
#         config.update({"layer_num": self.layer_num, "parameterization": self.parameterization, "seed": self.seed})
#         return config


class CINLayer(tf.keras.layers.Layer):
    def __init__(self, cin_size=(64, 64), l2_reg=0.0001, seed=1024, **kwargs):
        super(CINLayer, self).__init__(**kwargs)
        self.cin_size = cin_size  # List of the number of CIN units at each layer
        self.l2_reg = l2_reg
        self.seed = seed

    def build(self, input_shape):
        if len(input_shape) != 3:
            raise ValueError(f"Unexpected inputs dimensions {len(input_shape)}, expect to be 3 dimensions (batch_size, field_num, embedding_size)")
        self.field_num = input_shape[1]
        self.embedding_size = input_shape[2]
        # Compressed interaction network weights
        self.cin_weights = [
            self.add_weight(
                name=f"cin_W_{i}",
                shape=(self.cin_size[i], self.field_num * (self.cin_size[i - 1] if i > 0 else self.field_num), self.embedding_size),
                initializer=glorot_normal(seed=self.seed),
                regularizer=l2(self.l2_reg),
                trainable=True,
            )
            for i in range(len(self.cin_size))
        ]
        # Compressed interaction network biases
        self.cin_biases = [
            self.add_weight(
                name=f"cin_b_{i}",
                shape=(self.cin_size[i],),
                initializer=Zeros(),
                regularizer=l2(self.l2_reg),
                trainable=True,
            )
            for i in range(len(self.cin_size))
        ]
        # Be sure to call this somewhere!
        super(CINLayer, self).build(input_shape)

    def call(self, inputs, **kwargs):
        # The inputs here should be a 3D tensor with shape (batch_size, field_num, embedding_size)
        cin_results = [inputs]
        for layer_idx in range(len(self.cin_size)):
            x0 = cin_results[0]  # 输入的初始特征映射 H_0，形状为 ：(batch_size, field_num, embedding_size)
            xk = cin_results[-1]  # 上一层的特征映射 H_(k-1)，形状为： (batch_size, H_(k-1)_size, embedding_size)
            xk = tf.einsum(
                "bhd,bmd->bhmd", xk, x0
            )  # 计算外积，依次对每个样本的特征映射进行外积操作，得到形状为 (batch_size, H_(k-1)_size, field_num, embedding_size) 的张量
            xk = tf.reshape(
                xk, [-1, self.field_num * xk.shape[1], self.embedding_size]
            )  # 将张量重新整形，合并第二维和第三维，得到形状为 (batch_size, H_(k-1)_size * field_num, embedding_size) 的张量
            xk = tf.einsum("bhm,fhm->bmf", xk, self.cin_weights[layer_idx])  # [batch_size, embedding_size, CIN_k_size]
            # 加上偏置，并通过激活函数进行非线性变换
            xk = tf.nn.bias_add(xk, self.cin_biases[layer_idx])  # [batch_size, embedding_size, CIN_k_size]
            xk = tf.nn.relu(xk)
            xk = tf.transpose(xk, perm=[0, 2, 1])
            cin_results.append(xk)
        # 汇总所有层的结果
        final_result = tf.concat(cin_results, axis=1)  # [batch_size, sum(CIN_size), embedding_size]
        final_result = tf.reduce_sum(final_result, axis=-1)  # [batch_size, sum(CIN_size)] 在 embedding_size 维度上进行求和
        return final_result

    def get_config(self):
        config = super(CINLayer, self).get_config()
        config.update(
            {
                "cin_size": self.cin_size,
                "l2_reg": self.l2_reg,
                "seed": self.seed,
            }
        )
        return config


class DnnLayer(tf.keras.layers.Layer):
    def __init__(self, hidden_units=[64, 32], activation="relu", dropout_rate=0.2, use_bn=True, l2_reg=0.0001, seed=1024, **kwargs):
        super(DnnLayer, self).__init__(**kwargs)
        self.hidden_units = hidden_units
        self.activation = activation
        self.dropout_rate = dropout_rate
        self.use_bn = use_bn
        self.l2_reg = l2_reg
        self.seed = seed
        self.dense_layers = []
        self.dropout_layers = []
        self.bn_layers = []

    def build(self, input_shape):
        for units in self.hidden_units:
            self.dense_layers.append(
                tf.keras.layers.Dense(
                    units=units,
                    activation=self.activation,
                    kernel_initializer=glorot_normal(seed=self.seed),
                    bias_initializer=Zeros(),
                    kernel_regularizer=l2(self.l2_reg),
                )
            )
            self.dropout_layers.append(tf.keras.layers.Dropout(rate=self.dropout_rate, seed=self.seed))
            if self.use_bn:
                self.bn_layers.append(tf.keras.layers.BatchNormalization())
        # Be sure to call this somewhere!
        super(DnnLayer, self).build(input_shape)

    def call(self, inputs, training=False):
        # print(f"Dnn Is Training Mode: {training}")
        x = inputs
        for i in range(len(self.hidden_units)):
            x = self.dense_layers[i](x)
            if self.use_bn:
                x = self.bn_layers[i](x, training=training)
            x = self.dropout_layers[i](x, training=training)
        return x

    def get_config(self):
        config = super(DnnLayer, self).get_config()
        config.update(
            {
                "hidden_units": self.hidden_units,
                "activation": self.activation,
                "dropout_rate": self.dropout_rate,
                "use_bn": self.use_bn,
                "l2_reg": self.l2_reg,
                "seed": self.seed,
            }
        )
        return config
