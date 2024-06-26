import backtrader as bt
import pandas as pd
from .base_strategy import BaseStrategy


import backtrader as bt
import pandas as pd
import math
from copy import deepcopy


class CustomMLStrategy(BaseStrategy):
    """
    该Base策略对齐BigQuant的量化交易策略
    Args:
        BaseStrategy (_type_): _description_

    Returns:
        _type_: _description_
    """

    params = {
        "model_pred_dataframe": pd.DataFrame(),
        "min_holding_period": 5,
        "max_cash_per_instrument": 0.1,
        "top_n": 3,
        "min_size": 100,
    }

    def __init__(self):
        super().__init__()  # 调用基础策略的初始化方法
        # 计算股票的权重
        self.stock_weights = [1 / math.log(i + 2) for i in range(self.params.top_n)]
        self.stock_weights = [w / sum(self.stock_weights) for w in self.stock_weights]  # Norm
        # 获取模型预测
        self.stock_for_buy, self.stock_for_sell = self.get_model_prediction()
        self.holding_period = {}

    def get_model_prediction(self):
        def get_stock_for_buy(group):
            filtered_group = group[group["label_pred"] > 0.0]
            top_n = filtered_group.nlargest(self.params.top_n, "label_pred")
            return top_n.to_dict("records")

        def get_stock_for_sell(group):
            filtered_group = group[group["label_pred"] < 0.0]
            bottom_n = filtered_group.nsmallest(self.params.top_n, "label_pred")
            return bottom_n.to_dict("records")

        model_prediction = self.params.model_pred_dataframe
        model_prediction["stock_code"] = model_prediction["stock_code"].map(lambda x: str(x).zfill(6))
        stock_for_buy = model_prediction.groupby("datetime").apply(get_stock_for_buy).to_dict()
        stock_for_sell = model_prediction.groupby("datetime").apply(get_stock_for_sell).to_dict()
        return stock_for_buy, stock_for_sell

    def next(self):
        # 获取当前日期
        current_date = self.datas[0].datetime.date(0).isoformat()
        print(f"current_date: {current_date} ================================================================================")
        # 获取当前日期预测的买入名单
        today_buy_stocks = [i.get("stock_code") for i in self.stock_for_buy.get(current_date, [])]
        print(f"today_buy_stocks: {today_buy_stocks}")
        # 获取当前日期预测的卖出名单
        today_sell_stocks = [i.get("stock_code") for i in self.stock_for_sell.get(current_date, [])]
        print(f"today_sell_stocks: {today_sell_stocks}")
        # 获取当前可用现金
        current_cash = self.broker.getcash()
        print(f"current_cash: {current_cash}")
        print(f"current_holding: {self.holding_period}")

        # 遍历预定的买入股票
        for i, stock_code in enumerate(today_buy_stocks):
            # 获取对应的数据
            data = self.getdatabyname(stock_code)
            # 确定投资金额
            cash = current_cash * self.stock_weights[i]
            cash = min(cash, self.broker.getvalue() * self.params.max_cash_per_instrument)
            # 计算可以买多少股
            size = int(cash / data.close[0])
            if size > self.params.min_size:  # 最少股数量
                self.buy(data=data, size=size, exectype=bt.Order.Market)
                # 更新持仓天数
                self.holding_period[data._name] = 1

        # 检查是否需要卖出股票
        for data in self.getpositions():
            position = self.getpositionbyname(data._name)
            if position.size > 0:
                holding_period_condition = self.holding_period[data._name] >= self.params.min_holding_period
                model_pred_condition = data._name in today_sell_stocks
                if holding_period_condition and model_pred_condition:
                    self.close(data=data, exectype=bt.Order.Market)
                    self.holding_period.pop(data._name, None)

        # 更新持仓天数信息
        for k in self.holding_period.keys():
            self.holding_period[k] += 1
