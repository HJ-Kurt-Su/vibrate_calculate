import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import BytesIO

# ---------------------------------------------------------
# 1. VRS 計算核心函數
# ---------------------------------------------------------
def calculate_vrs(f_in, psd_in, Q=10, fn_points=200):
    """
    計算 Vibration Response Spectrum (VRS)
    f_in: 輸入頻率 array (Hz)
    psd_in: 輸入 PSD array (g^2/Hz)
    Q: Quality factor (預設為 10)
    fn_points: 計算的自然頻率點數
    """
    # 確保資料為 numpy array 並過濾掉 0 以避免 log 錯誤
    f_in = np.array(f_in)
    psd_in = np.array(psd_in)
    valid_idx = (f_in > 0) & (psd_in > 0)
    f_in = f_in[valid_idx]
    psd_in = psd_in[valid_idx]

    # 建立細緻的頻率網格以進行準確的數值積分 (Log-space)
    f_fine = np.logspace(np.log10(f_in.min()), np.log10(f_in.max()), 5000)
    
    # 由於 PSD 是在 Log-Log 尺度下定義的，必須在 Log 空間中進行插值
    log_f_in = np.log10(f_in)
    log_psd_in = np.log10(psd_in)
    log_f_fine = np.log10(f_fine)
    psd_fine = 10 ** np.interp(log_f_fine, log_f_in, log_psd_in)

    # 阻尼比
    zeta = 1 / (2 * Q)
    
    # 定義要計算 VRS 的自然頻率陣列 (fn)
    fn_array = np.logspace(np.log10(f_in.min()), np.log10(f_in.max()), fn_points)
    vrs_array = []

    # 計算每個自然頻率 fn 下的 RMS 響應
    for fn in fn_array:
        rho = f_fine / fn
        # 絕對加速度傳遞函數的平方 |T(f)|^2
        T2 = (1 + (2 * zeta * rho)**2) / ((1 - rho**2)**2 + (2 * zeta * rho)**2)
        
        # 響應 PSD
        response_psd = T2 * psd_fine
        
        # 積分求變異數 (Variance)，並開根號得到 RMS (G_rms)
        variance = np.trapezoid(response_psd, f_fine)
        vrs_array.append(np.sqrt(variance))

    return fn_array, np.array(vrs_array)

# ---------------------------------------------------------
# 2. Streamlit UI 介面
# ---------------------------------------------------------
st.set_page_config(page_title="Random Vibration VRS Calculator", layout="wide")

st.title("🌊 Random Vibration: VRS 計算與視覺化工具")
st.markdown("""
請上傳包含 **Frequency (Hz)** 與 **PSD (g²/Hz)** 的兩欄位資料表（支援 CSV 或 Excel）。
程式將自動計算 Vibration Response Spectrum (VRS) 並繪製圖表。
""")

# 側邊欄設定參數
st.sidebar.header("⚙️ 計算參數設定")
Q_factor = st.sidebar.slider("Quality Factor (Q)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)
fn_points = st.sidebar.number_input("VRS 計算解析度 (點數)", min_value=50, max_value=1000, value=200, step=50)

# 檔案上傳
uploaded_file = st.file_uploader("上傳 PSD Profile (CSV 或 Excel)", type=['csv', 'xls', 'xlsx'])

if uploaded_file is not None:
    try:
        # 讀取檔案
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 檢查欄位數量
        if df.shape[1] < 2:
            st.error("上傳的檔案必須至少包含兩個欄位 (Frequency 和 PSD)！")
        else:
            # 假設第一欄是頻率，第二欄是 PSD
            freq_col = df.columns[0]
            psd_col = df.columns[1]
            
            f_in = df[freq_col].values
            psd_in = df[psd_col].values
            
            st.success("✅ 檔案讀取成功！")
            
            # 顯示原始資料
            with st.expander("查看原始輸入資料"):
                st.dataframe(df.head(10))
            
            # 執行計算
            with st.spinner('正在計算 VRS，請稍候...'):
                fn_array, vrs_array = calculate_vrs(f_in, psd_in, Q=Q_factor, fn_points=fn_points)
                
                # 建立輸出 DataFrame
                df_vrs = pd.DataFrame({
                    'Natural Frequency (Hz)': fn_array,
                    'VRS (G_rms)': vrs_array
                })

            st.markdown("---")
            st.subheader("📊 VRS 與 PSD 分析圖表")

            # 使用 Plotly 繪圖
            fig = go.Figure()

            # 繪製輸入的 PSD (使用右側 Y 軸)
            fig.add_trace(go.Scatter(
                x=f_in, y=psd_in, 
                mode='lines+markers',
                name=f'Input PSD ({psd_col})',
                line=dict(color='gray', dash='dash'),
                yaxis='y2'
            ))

            # 繪製計算出的 VRS (使用左側 Y 軸)
            fig.add_trace(go.Scatter(
                x=fn_array, y=vrs_array, 
                mode='lines',
                name=f'VRS (Q={Q_factor})',
                line=dict(color='blue', width=2)
            ))

            # 設定圖表版面 (Log-Log scale)
            fig.update_layout(
                title='VRS (Vibration Response Spectrum) Profile',
                xaxis=dict(title='Frequency (Hz)', type='log'),
                yaxis=dict(title='VRS (G_rms)', type='log', color='blue'),
                yaxis2=dict(title='PSD (g²/Hz)', type='log', color='gray', overlaying='y', side='right'),
                legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)'),
                hovermode='x unified',
                height=600
            )

            st.plotly_chart(fig, use_container_width=True)

            # ---------------------------------------------------------
            # 3. CSV 下載功能
            # ---------------------------------------------------------
            st.markdown("---")
            st.subheader("💾 下載計算結果")
            
            csv = df_vrs.to_csv(index=False).encode('utf-8-sig') # 加上 sig 讓 Excel 開啟不亂碼
            
            st.download_button(
                label="📥 點此下載 VRS 資料 (CSV)",
                data=csv,
                file_name=f'VRS_Output_Q{int(Q_factor)}.csv',
                mime='text/csv',
            )

    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")
        st.info("請確認上傳的檔案格式是否正確（第一欄為數值頻率，第二欄為數值 PSD）。")