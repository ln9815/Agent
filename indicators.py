import pandas as pd
import numpy as np

def add_technical_indicators(data, price_col='c'):
    """
    在原始数据列表中添加技术指标
    
    参数:
    data: list of dict, 必须包含 't'(时间), 'o'(开盘价), 'h'(最高价), 'l'(最低价), 'c'(收盘价)
    price_col: str, 计算指标使用的价格列名，默认使用收盘价'c'
    
    返回:
    添加技术指标后的list of dict
    """
    
    def calculate_ma(prices, period):
        """计算移动平均线"""
        return pd.Series(prices).rolling(window=period).mean().round(2)

    def calculate_boll(prices, period=20, k=2):
        """计算布林带"""
        mid = pd.Series(prices).rolling(window=period).mean().round(2)
        std = pd.Series(prices).rolling(window=period).std().round(2)
        up = (mid + k * std).round(2)
        down = (mid - k * std).round(2)
        return mid, up, down

    def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
        """计算MACD"""
        ema_fast = pd.Series(prices).ewm(span=fast_period, adjust=False).mean().round(2)
        ema_slow = pd.Series(prices).ewm(span=slow_period, adjust=False).mean().round(2)
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signal_period, adjust=False).mean().round(2)
        histogram = (macd - signal).round(2)
        return macd, signal, histogram

    def calculate_rsi(prices, period=14):
        """计算RSI"""
        delta = pd.Series(prices).diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean().round(2) # type: ignore
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean().round(2) # type: ignore
        rs = gain / loss.replace(to_replace=0, method='ffill') # type: ignore
        return (100 - (100 / (1 + rs))).round(2)

    def calculate_kdj(high, low, close, n=9):
        """计算KDJ"""
        rsv = pd.Series(0.0, index=close.index)
        for i in range(n-1, len(close)):
            period_low = low[i-n+1:i+1].min()
            period_high = high[i-n+1:i+1].max()
            if period_high != period_low:
                rsv[i] = (close[i] - period_low) / (period_high - period_low) * 100
            else:
                rsv[i] = 100

        k = pd.Series(50.0, index=close.index)
        d = pd.Series(50.0, index=close.index)
        j = pd.Series(50.0, index=close.index)

        for i in range(1, len(close)):
            k[i] = (2/3 * k[i-1] + 1/3 * rsv[i]).round(2) # type: ignore
            d[i] = (2/3 * d[i-1] + 1/3 * k[i]).round(2) # type: ignore
            j[i] = (3 * k[i] - 2 * d[i]).round(2) # type: ignore

        return k, d, j

    # 转换为DataFrame
    df = pd.DataFrame(data)

    prices = df[price_col]
    
    # 添加MA
    df['MA5'] = calculate_ma(prices, 5)
    df['MA10'] = calculate_ma(prices, 10)
    df['MA20'] = calculate_ma(prices, 20)
    
    # 添加BOLL
    df['BOLL_MID'], df['BOLL_UP'], df['BOLL_DOWN'] = calculate_boll(prices)
    
    # 添加MACD
    df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = calculate_macd(prices)
    
    # 添加RSI
    df['RSI'] = calculate_rsi(prices)
    
    # 添加KDJ
    df['K'], df['D'], df['J'] = calculate_kdj(df['h'], df['l'], df[price_col])
    
    # 转换回list of dict
    result = df.to_dict('records')
    
    return result

# 使用示例：
if __name__ == "__main__":
    # 测试数据
    test_data = [
        {"t": "2023-01-01", "o": 100.0, "h": 102.0, "l": 99.0, "c": 101.0, "v": 10000, "a": 1010000, "pc": 99.5},
        {"t": "2023-01-02", "o": 101.0, "h": 103.0, "l": 100.0, "c": 102.0, "v": 12000, "a": 1224000, "pc": 101.0},
        {"t": "2023-01-03", "o": 102.0, "h": 104.0, "l": 101.0, "c": 103.0, "v": 11000, "a": 1133000, "pc": 102.0},
        {"t": "2023-01-04", "o": 103.0, "h": 105.0, "l": 102.0, "c": 104.0, "v": 13000, "a": 1352000, "pc": 103.0},
        {"t": "2023-01-05", "o": 104.0, "h": 106.0, "l": 103.0, "c": 105.0, "v": 14000, "a": 1470000, "pc": 104.0},
    ]
    
    # 添加技术指标
    result = add_technical_indicators(test_data)
    
    # 打印结果
    print(f"\n计算结果:\n{pd.DataFrame(result).tail(5)}")