import tensorflow as tf
from tensorflow.keras.initializers import glorot_normal, Zeros
from tensorflow.keras.regularizers import l2


class DnnLayer(tf.keras.layers.Layer):
    def __init__(self, hidden_units=[64, 32], activation="relu", dropout_rate=0.2, use_bn=True, l2_reg=0.0, seed=1024, **kwargs):
        super(DnnLayer, self).__init__(**kwargs)
        self.hidden_units = hidden_units
        self.activation = activation
        self.dropout_rate = dropout_rate
        self.use_bn = use_bn
        self.l2_reg = l2_reg
        self.seed = seed
        self.dense_layers = []
        self.activation_layers = []
        self.dropout_layers = []
        self.bn_layers = []

    def build(self, input_shape):
        for index, units in enumerate(self.hidden_units):
            self.dense_layers.append(
                tf.keras.layers.Dense(
                    units=units,
                    activation=None,  # 移除激活函数
                    kernel_initializer=glorot_normal(seed=self.seed + index),
                    bias_initializer=Zeros(),
                    kernel_regularizer=l2(self.l2_reg),
                )
            )
            # 激活函数作为单独一层
            self.activation_layers.append(tf.keras.activations.get(self.activation))
            if self.use_bn:
                self.bn_layers.append(tf.keras.layers.BatchNormalization())
            self.dropout_layers.append(tf.keras.layers.Dropout(rate=self.dropout_rate, seed=self.seed + index))

        super(DnnLayer, self).build(input_shape)

    def call(self, inputs):
        x = inputs
        for i in range(len(self.hidden_units)):
            x = self.dense_layers[i](x)
            if self.use_bn:
                x = self.bn_layers[i](x)
            # 激活函数应用在BN之后，或直接在Dense之后（如果没有BN）
            x = self.activation_layers[i](x)
            x = self.dropout_layers[i](x)
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
