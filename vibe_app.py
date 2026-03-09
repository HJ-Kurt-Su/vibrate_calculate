import streamlit as st
import pandas as pd
import numpy as np
import scipy.interpolate as interp
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. 核心計算函數
# ---------------------------------------------------------
def calculate_vrs(f_in, psd_in, Q=10, fn_points=200):
    """計算 Vibration Response Spectrum (VRS) 與 Input Grms"""
    f_in = np.array(f_in)
    psd_in = np.array(psd_in)
    valid_idx = (f_in > 0) & (psd_in > 0)
    f_in = f_in[valid_idx]
    psd_in = psd_in[valid_idx]

    f_fine = np.logspace(np.log10(f_in.min()), np.log10(f_in.max()), 5000)
    
    log_f_in = np.log10(f_in)
    log_psd_in = np.log10(psd_in)
    psd_fine = 10 ** np.interp(np.log10(f_fine), log_f_in, log_psd_in)

    # 計算輸入的整體 Grms (PSD 曲線下面積開根號)
    input_grms = np.sqrt(np.trapezoid(psd_fine, f_fine))

    zeta = 1 / (2 * Q)
    fn_array = np.logspace(np.log10(f_in.min()), np.log10(f_in.max()), fn_points)
    vrs_array = []

    for fn in fn_array:
        rho = f_fine / fn
        T2 = (1 + (2 * zeta * rho)**2) / ((1 - rho**2)**2 + (2 * zeta * rho)**2)
        response_psd = T2 * psd_fine
        variance = np.trapezoid(response_psd, f_fine)
        vrs_array.append(np.sqrt(variance))

    return fn_array, np.array(vrs_array), input_grms

def interp_to_grid(f_src, S_src, f_grid):
    """將 PSD 線性插值到等間距的頻率網格上"""
    interp_func = interp.interp1d(f_src, S_src, kind='linear', bounds_error=False, fill_value=0.0)
    return interp_func(f_grid)

def dirlik_damage_rate(Ssigma, freq, df, m, C):
    """依照 Dirlik / 窄頻近似的疲勞損傷率計算"""
    m0 = np.sum(Ssigma) * df
    m1 = np.sum((2*np.pi*freq) * Ssigma) * df
    m2 = np.sum((2*np.pi*freq)**2 * Ssigma) * df
    m4 = np.sum((2*np.pi*freq)**4 * Ssigma) * df

    if m0 <= 0:
        return 0.0, np.zeros_like(freq), 0, 0, 0

    nu_p = np.sqrt(m2 / m0) / (2*np.pi) * np.sqrt(max(1.0 - (m1**2)/(m0*m2), 1e-30))
    if nu_p <= 0:
        nu_p = np.sqrt(m2 / m0) / (2*np.pi)

    sigma_rms = np.sqrt(Ssigma * df)
    sigma_peak = sigma_rms * np.sqrt(2.0)

    n_cycles_per_hour = nu_p * 3600.0 * (Ssigma / (m0 + 1e-30))

    damage_per_hour = np.zeros_like(Ssigma)
    mask = sigma_peak > 0
    damage_per_hour[mask] = n_cycles_per_hour[mask] / (C * sigma_peak[mask]**m)

    D_dot = np.sum(damage_per_hour)
    return D_dot, damage_per_hour, m0, m2, m4

# ---------------------------------------------------------
# 2. Streamlit UI 介面
# ---------------------------------------------------------
st.set_page_config(page_title="VRS & Fatigue Damage Calculator", layout="wide")

st.title("🌊 Random Vibration: VRS 與疲勞壽命 (Dirlik) 計算工具")
st.markdown("""
上傳包含 **Frequency (Hz)** 與 **PSD (g²/Hz)** 的資料表。
程式將計算 VRS，並依據您設定的轉換係數與材料 S-N 曲線參數，估算疲勞損傷率。
""")

# --- 側邊欄設定 ---
st.sidebar.header("⚙️ VRS 計算參數")
Q_factor = st.sidebar.slider("Quality Factor (Q)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)
fn_points = st.sidebar.number_input("VRS 計算解析度 (點數)", min_value=50, max_value=1000, value=200, step=50)

st.sidebar.header("⚙️ 疲勞評估參數 (Fatigue & S-N)")
k_factor = st.sidebar.number_input("轉換係數 k (MPa per g)", value=1.0, step=0.1)

# --- 材料 S-N 參數預設選單 ---
material_dict = {
    "自訂 (Custom)": {"m": 3.0, "C": 1.0e12},
    "一般鋼結構 (Generic Steel, m=3)": {"m": 3.0, "C": 2.0e11},
    "高強度鋼材 (High Strength Steel, m=4)": {"m": 4.0, "C": 5.0e13},
    "鋁合金 6061-T6 (Aluminum, m=6.4)": {"m": 6.4, "C": 2.5e18},
    "鋁合金 7075-T6 (Aluminum, m=7.3)": {"m": 7.3, "C": 1.0e20}
}

selected_material = st.sidebar.selectbox("📝 常用材料 S-N 參數預設 (僅供參考)", list(material_dict.keys()))

default_m = material_dict[selected_material]["m"]
default_C = material_dict[selected_material]["C"]

m_param = st.sidebar.number_input("S-N 曲線指數 m", value=default_m, step=0.1, format="%.1f")
C_param = st.sidebar.number_input("S-N 曲線常數 C", value=default_C, format="%.2e")

exposure_hours = st.sidebar.number_input("暴露時間 (小時)", value=3.0, step=0.5)
df_step = st.sidebar.number_input("頻率網格解析度 df (Hz)", value=1.0, step=0.5)

st.sidebar.markdown("*(註: 疲勞參數 $m$ 與 $C$ 易受表面粗糙度、應力集中、尺寸效應等影響，評估時請確認保守餘裕)*")

# --- 檔案上傳 ---
uploaded_file = st.file_uploader("上傳 PSD Profile (CSV 或 Excel)", type=['csv', 'xls', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_input = pd.read_csv(uploaded_file)
        else:
            df_input = pd.read_excel(uploaded_file)
        
        if df_input.shape[1] < 2:
            st.error("上傳的檔案必須至少包含兩個欄位 (Frequency 和 PSD)！")
        else:
            f_in = df_input.iloc[:, 0].values
            psd_in = df_input.iloc[:, 1].values
            
            st.success("✅ 檔案讀取成功！開始執行分析...")
            
            with st.spinner('正在計算 VRS 與疲勞損傷...'):
                # 1. 計算 VRS 與 Input Grms
                fn_array, vrs_array, input_grms = calculate_vrs(f_in, psd_in, Q=Q_factor, fn_points=fn_points)
                
                # 2. 建立等間距網格以進行 Dirlik 計算
                f_min = max(2.0, f_in.min())
                f_max = f_in.max()
                freq_grid = np.arange(f_min, f_max + df_step, df_step)
                
                # 3. 插值並轉換為應力 PSD
                psd_interp = interp_to_grid(f_in, psd_in, freq_grid)
                Ssigma = (k_factor**2) * psd_interp 
                
                # 4. 計算 Dirlik 損傷
                D_dot, damage_density, m0, m2, m4 = dirlik_damage_rate(Ssigma, freq_grid, df_step, m_param, C_param)
                D_total = D_dot * exposure_hours
                life_hours = 1.0 / D_dot if D_dot > 0 else np.inf

            # --- 顯示結果 Summary ---
            st.markdown("---")
            st.subheader("📝 計算結果摘要")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Input G_rms", f"{input_grms:.3f} g")
            col2.metric("Spectral Moment (m0)", f"{m0:.2e}")
            col3.metric("每小時損傷率 (D_dot)", f"{D_dot:.4e}")
            col4.metric(f"總損傷 ({exposure_hours} hrs)", f"{D_total:.4e}")
            col5.metric("預估壽命 (Hours)", f"{life_hours:.2e}")

            # --- 繪圖區 ---
            st.markdown("---")
            st.subheader("📊 分析圖表")
            
            # 將兩張子圖的 secondary_y 皆設為 True
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True,
                vertical_spacing=0.1,
                specs=[[{"secondary_y": True}],  
                       [{"secondary_y": True}]], # 這裡改為 True，啟用第二張圖的雙 Y 軸
                subplot_titles=("Input PSD & VRS Profile", "Stress PSD & Damage Density")
            )

            # --- Plot 1: Input PSD & VRS ---
            # VRS (畫在左側 Y 軸)
            fig.add_trace(go.Scatter(
                x=fn_array, y=vrs_array, name=f'VRS (Q={Q_factor})', line=dict(color='blue', width=2)
            ), row=1, col=1, secondary_y=False)

            # Input PSD (畫在右側 Y 軸)
            fig.add_trace(go.Scatter(
                x=f_in, y=psd_in, name=f'Input PSD (Grms: {input_grms:.2f} g)', line=dict(color='gray', dash='dash')
            ), row=1, col=1, secondary_y=True)


            # --- Plot 2: Stress PSD & Damage Density ---
            # Stress PSD (畫在左側 Y 軸)
            fig.add_trace(go.Scatter(
                x=freq_grid, y=Ssigma, name='Stress PSD (MPa²/Hz)', line=dict(color='orange')
            ), row=2, col=1, secondary_y=False)
            
            # Damage Density (畫在右側 Y 軸)
            fig.add_trace(go.Scatter(
                x=freq_grid, y=damage_density, name='Damage Density (/Hz)', line=dict(color='red')
            ), row=2, col=1, secondary_y=True)

            # 更新版面配置與兩側 Y 軸的設定
            fig.update_layout(height=800, hovermode='x unified')
            
            # --- 第一張圖 (Plot 1) 軸設定 ---
            fig.update_xaxes(type="log", row=1, col=1)
            # 左側 (VRS)
            fig.update_yaxes(title_text="VRS (G_rms)", type="log", title_font=dict(color="blue"), tickfont=dict(color="blue"), row=1, col=1, secondary_y=False)
            # 右側 (PSD)
            fig.update_yaxes(title_text="Input PSD (g²/Hz)", type="log", title_font=dict(color="gray"), tickfont=dict(color="gray"), row=1, col=1, secondary_y=True)
            
            # --- 第二張圖 (Plot 2) 軸設定 ---
            fig.update_xaxes(title_text="Frequency (Hz)", type="log", row=2, col=1)
            # 左側 (Stress PSD)
            fig.update_yaxes(title_text="Stress PSD (MPa²/Hz)", type="log", title_font=dict(color="orange"), tickfont=dict(color="orange"), row=2, col=1, secondary_y=False)
            # 右側 (Damage Density)
            fig.update_yaxes(title_text="Damage Density (/Hz)", type="log", title_font=dict(color="red"), tickfont=dict(color="red"), row=2, col=1, secondary_y=True)
            
            st.plotly_chart(fig, width="stretch")

            # --- 資料下載 ---
            st.markdown("---")
            st.subheader("💾 下載計算結果")
            
            df_out_vrs = pd.DataFrame({'Natural_Freq_Hz': fn_array, 'VRS_Grms': vrs_array})
            df_out_fatigue = pd.DataFrame({
                'Freq_Hz': freq_grid,
                'Interpolated_PSD_g2_Hz': psd_interp,
                'Stress_PSD_MPa2_Hz': Ssigma,
                'Damage_Density_per_hour': damage_density
            })

            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                csv_vrs = df_out_vrs.to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 下載 VRS 結果 (CSV)", data=csv_vrs, file_name='VRS_Output.csv', mime='text/csv')
                
            with col_btn2:
                csv_fatigue = df_out_fatigue.to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 下載 Fatigue 結果 (CSV)", data=csv_fatigue, file_name='Fatigue_Dirlik_Output.csv', mime='text/csv')

    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")