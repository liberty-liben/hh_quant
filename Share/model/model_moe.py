import tensorflow as tf
from .layers import DnnLayer, BitWiseSeNet


class QuantModel(tf.keras.Model):
    def __init__(self, config, **kwargs):
        super(QuantModel, self).__init__(**kwargs)
        self.config = config
        self.lookup_layers = {}
        self.embedding_layers = {}

        # 创建整数特征的查找层和嵌入层
        for feature_name, vocab in self.config.get("integer_categorical_features_with_vocab").items():
            self.lookup_layers[feature_name] = tf.keras.layers.IntegerLookup(vocabulary=vocab, name=f"{feature_name}_lookup")
            self.embedding_layers[feature_name] = tf.keras.layers.Embedding(
                input_dim=len(vocab) + 1,
                output_dim=self.config.get("feature_embedding_dims", 4),
                embeddings_initializer=tf.keras.initializers.glorot_normal(self.config.get("seed", 1024)),
                name=f"{feature_name}_embedding",
            )
        # 创建字符串特征的查找层和嵌入层
        for feature_name, vocab in self.config.get("string_categorical_features_with_vocab").items():
            self.lookup_layers[feature_name] = tf.keras.layers.StringLookup(vocabulary=vocab, name=f"{feature_name}_lookup")
            self.embedding_layers[feature_name] = tf.keras.layers.Embedding(
                input_dim=len(vocab) + 1,
                output_dim=self.config.get("feature_embedding_dims", 4),
                embeddings_initializer=tf.keras.initializers.glorot_normal(self.config.get("seed", 1024)),
                name=f"{feature_name}_embedding",
            )

        # 自定义层相关
        self.experts = []
        for expert_nums in range(self.config.get("expert_nums", 3)):
            expert_part = tf.keras.Sequential(
                [
                    BitWiseSeNet(
                        reduction_ratio=self.config.get("reduction_ratio", 3),
                        l2_reg=self.config.get("l2_reg", 0.0),
                        seed=self.config.get("seed", 1024) + expert_nums,
                    ),
                    DnnLayer(
                        hidden_units=self.config.get("dnn_hidden_units", [64, 32]),
                        activation=self.config.get("dnn_activation", "relu"),
                        dropout_rate=self.config.get("dnn_dropout", 0.2),
                        use_bn=self.config.get("dnn_use_bn", True),
                        l2_reg=self.config.get("l2_reg", 0.001),
                        seed=self.config.get("seed", 1024) + expert_nums,
                    ),
                ]
            )
            self.experts.append(expert_part)
        self.gate = tf.keras.layers.Dense(
            self.config.get("expert_nums", 3),
            activation=self.config.get("gate_activation", "sigmoid"),
        )

        self.output_tower = DnnLayer(
            hidden_units=self.config.get("dnn_hidden_units", [64, 32]),
            activation=self.config.get("dnn_activation", "relu"),
            dropout_rate=self.config.get("dnn_dropout", 0.2),
            use_bn=self.config.get("dnn_use_bn", True),
            l2_reg=self.config.get("l2_reg", 0.001),
            seed=self.config.get("seed", 1024) + expert_nums,
        )

        self.wide_output_layer = tf.keras.layers.Dense(1, activation=None)
        self.deep_output_layer = tf.keras.layers.Dense(1, activation=None)

    def get_sparse_dense_features(self, inputs):
        sparse_features = []  # list of [B, emb]
        dense_features = []  # [B, N]
        for feature_name, feature_value in inputs.items():
            if feature_name in self.lookup_layers:
                lookup_layer = self.lookup_layers[feature_name]
                embedding_layer = self.embedding_layers[feature_name]
                encode_feature = embedding_layer(lookup_layer(feature_value))
                sparse_features.append(encode_feature)
            else:
                dense_features.append(feature_value)
        return sparse_features, dense_features

    def call(self, inputs, training=False):
        if not isinstance(inputs, dict):
            raise ValueError("The inputs to the model should be a dictionary where keys are feature names.")

        # 处理Deep侧特征
        sparse_features, dense_features = self.get_sparse_dense_features(inputs)
        dense_emb = tf.stack(dense_features, axis=-1)
        sparse_emb = tf.concat(sparse_features, axis=-1)

        # Wide..........................................................................................
        wide_logit = self.wide_output_layer(dense_emb)

        # Deep..........................................................................................
        deep_input = tf.concat([sparse_emb, dense_emb], axis=-1)
        expert_outputs = [expert(deep_input) for expert in self.experts]
        expert_output = tf.stack(expert_outputs, axis=1)  # [B, expert_nums, dim]
        gate_output = self.gate(deep_input)  # [B, expert_nums]
        gate_output = tf.expand_dims(gate_output, axis=-1)  # [B, expert_nums, 1]
        deep_output = tf.multiply(gate_output, expert_output)  # [B, expert_nums, dim]
        deep_output = tf.keras.layers.Flatten()(deep_output)  # [B, expert_nums * dim]
        deep_output = self.output_tower(deep_output)  # [B, dim]
        deep_logit = self.deep_output_layer(deep_output)  # [B, 1]

        # Output........................................................................................
        final_logit = deep_logit + wide_logit
        return final_logit

    def get_config(self):
        config = super(QuantModel, self).get_config()
        config.update({"config": self.config})
        return config
