# vibrate_calculate
# Random Vibration & Fatigue Calculator (VRS / Dirlik)

這是一個基於 Python Streamlit 的工程分析工具，專門用於隨機振動 (Random Vibration) 的分析。
它可以根據輸入的功率頻譜密度 (PSD) 曲線，計算振動響應頻譜 (VRS)，並利用 Dirlik 方法估算結構的疲勞壽命。

## 主要功能

1.  **VRS 計算 (Vibration Response Spectrum)**
    *   基於單自由度 (SDOF) 模型計算不同自然頻率下的加速度響應 (Grms)。
    *   支援自訂品質因子 (Q Factor)。

2.  **疲勞壽命估算 (Fatigue Life Estimation)**
    *   使用 **Dirlik Method** (頻域疲勞分析的標準方法) 計算累積損傷。
    *   支援自訂 S-N 曲線參數 ($m$, $C$) 或使用內建常用材料參數 (鋼、鋁合金等)。
    *   支援應力轉換係數 ($k$) 設定 (將加速度 g 轉換為應力 MPa)。

3.  **互動式圖表與報告**
    *   繪製 Input PSD 與 VRS 比較圖。
    *   繪製應力 PSD (Stress PSD) 與損傷密度 (Damage Density) 分佈圖。
    *   計算並顯示 Grms、頻譜矩 (Spectral Moments)、每小時損傷率與預估壽命。

4.  **資料匯出**
    *   可下載計算後的 VRS 數據 (.csv)。
    *   可下載詳細的疲勞分析數據 (.csv)。

## 安裝需求

請確保您的環境已安裝 Python 3.8+，並安裝以下套件：

```bash
pip install streamlit pandas numpy scipy plotly openpyxl
```

*注意：本程式依賴 `numpy`，若您使用 NumPy 2.0+ 版本，程式碼中使用 `np.trapezoid`；若使用舊版 NumPy (< 2.0)，請將程式碼中的 `np.trapezoid` 修改為 `np.trapz`。*

## 使用方法

1.  **啟動應用程式**
    在終端機執行以下指令：
    ```bash
    streamlit run vibe_app.py
    ```

2.  **上傳資料**
    *   準備一個 CSV 或 Excel 檔案。
    *   **第一欄**：頻率 (Frequency, Hz)。
    *   **第二欄**：功率頻譜密度 (PSD, $g^2/Hz$)。
    *   程式會自動讀取前兩欄數值資料。

3.  **調整參數**
    *   在左側側邊欄調整 **Q Factor** (阻尼相關)。
    *   設定疲勞參數：轉換係數 $k$、S-N 曲線斜率 $m$ 與截距 $C$。
    *   設定暴露時間 (Exposure Hours) 以計算總損傷。

## 理論基礎

*   **VRS**: 對輸入 PSD 與 SDOF 傳遞函數進行積分，求得各個自然頻率下的響應 RMS 值。
*   **Dirlik Method**: 一種基於頻譜矩 (Spectral Moments $m_0, m_1, m_2, m_4$) 的經驗公式，用於估算隨機過程中的雨流計數 (Rainflow Counting) 分佈，進而計算疲勞損傷。