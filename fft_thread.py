import time
import threading
import numpy as np
from scipy.fft import fft, fftfreq
from PyQt5.QtCore import QThread, pyqtSignal

class FFTThread(QThread):
    """
    双通道 FFT 计算线程，改进：
      - 使用 Hann 窗口以减少谱泄漏并做幅值校正（coherent gain）
      - 零填充（zero-padding），FFT 点数 Nfft = max(4096, N)
      - 抛物线（parabolic）峰值插值以提高频率估计精度
    信号:
      - result_ready(dict)
      - error(str)
    返回字段新增:
      - 'Nfft' : 用于 FFT 的点数 (零填充后的长度)
      - 'freq_est1' / 'mag_est1' : 经过插值后的主频和幅值估计
      - 'freq_est2' / 'mag_est2' : 通道2 的估计（若有）
    """
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._has_data = False
        self._running = False
        self._ch1 = None
        self._ch2 = None
        self._fs = 1.0
        self.harmonic_count = 10
        self.process_interval = 0.02  # 空闲等待间隔（秒）
        self.zero_pad_target = 4096    # 零填充后的最小 FFT 长度

    def set_input(self, ch1, ch2=None, sample_rate=1.0):
        """
        提交新数据用于计算。ch1/ch2 为 numpy 数组或可转为 numpy 的序列。
        sample_rate: 优先解释为采样频率 (Hz)；若传入值 < 1 则自动视为采样间隔 dt（秒）并转换为 fs = 1.0/dt。
        """
        try:
            a1 = np.asarray(ch1, dtype=float)
            a2 = np.asarray(ch2, dtype=float) if ch2 is not None else None
        except Exception as e:
            self.error.emit(f"输入数据格式错误: {e}")
            return

        # 自动识别传入参数是采样率还是采样间隔
        fs_used = None
        try:
            sr = float(sample_rate)
            if sr <= 0:
                # 非法采样率，使用默认 1.0 并警告
                fs_used = 1.0
                self.error.emit(f"警告：传入 sample_rate={sample_rate} 非正，已改为 1.0 Hz")
            elif sr < 1.0:
                # 很可能传入的是采样间隔 dt (秒)
                fs_used = 1.0 / sr
            else:
                fs_used = sr
        except Exception:
            fs_used = 1.0
            self.error.emit(f"警告：无法解析 sample_rate={sample_rate}，已改为 1.0 Hz")

        with self._lock:
            self._ch1 = a1
            self._ch2 = a2
            self._fs = float(fs_used)
            self._raw_sample_rate = sample_rate  # 保存原始输入便于调试
            self._has_data = True

    def run(self):
        self._running = True
        while self._running:
            if not self._has_data:
                time.sleep(self.process_interval)
                continue

            with self._lock:
                ch1 = None if self._ch1 is None else self._ch1.copy()
                ch2 = None if self._ch2 is None else (self._ch2.copy() if self._ch2 is not None else None)
                fs = self._fs
                self._has_data = False

            try:
                result = self._compute(ch1, ch2, fs)
                self.result_ready.emit(result)
            except Exception as e:
                self.error.emit(f"FFT 计算异常: {e}")

        # 退出前清理
        with self._lock:
            self._ch1 = None
            self._ch2 = None

    def stop(self):
        """停止线程（非阻塞）。"""
        self._running = False

    def _compute(self, ch1, ch2, fs):
        """
        执行 FFT 计算并返回结果字典（包含改进：窗口、零填充、插值估计）
        """
        if ch1 is None or len(ch1) == 0:
            raise ValueError("ch1 数据为空")

        N = len(ch1)
        # 若 ch2 长度与 ch1 不一致，裁切或补零以匹配 ch1 长度
        if ch2 is not None:
            if len(ch2) != N:
                if len(ch2) > N:
                    ch2 = ch2[:N]
                else:
                    pad = np.zeros(N - len(ch2), dtype=float)
                    ch2 = np.concatenate([ch2, pad])

        # 去直流（但保存直流分量以便返回）
        dc1 = float(np.mean(ch1))
        dc2 = float(np.mean(ch2)) if ch2 is not None else None
        x1 = ch1 - dc1
        x2 = (ch2 - dc2) if ch2 is not None else None

        # 窗口（Hann）与幅值校正（coherent gain）
        if N >= 1:
            w = np.hanning(N)
            x1w = x1 * w
            cg = np.sum(w) / N  # coherent gain
            x2w = (x2 * w) if x2 is not None else None
        else:
            x1w = x1
            x2w = x2
            cg = 1.0

        # 零填充后的 FFT 点数（至少 zero_pad_target）
        Nfft = max(self.zero_pad_target, N)

        # 计算 FFT 幅值谱（使用原始 N 做幅值归一化，以保持物理含义）
        X1 = fft(x1w, n=Nfft)
        mag1 = np.abs(X1[:Nfft // 2]) * 2.0 / N
        mag1 = mag1 / cg  # 窗口幅值校正
        f = fftfreq(Nfft, 1.0 / fs)[:Nfft // 2]

        mag2 = None
        if x2w is not None:
            X2 = fft(x2w, n=Nfft)
            mag2 = np.abs(X2[:Nfft // 2]) * 2.0 / N
            mag2 = mag2 / cg

        # 峰峰值（时域）按新要求：每次数据的最大值减去直流分量后乘以2
        # 旧：
        # ptp1 = float((np.max(ch1) - dc1) * 2.0)
        # ptp2 = float((np.max(ch2) - dc2) * 2.0) if ch2 is not None else None

        # 改为：用 top/bottom 百分位均值更稳健（例如 top_pct=0.05 -> 顶部 5% 样本均值）
        def robust_ptp(samples, top_pct=0.05):
            if samples is None or len(samples) == 0:
                return None, None, None
            arr = np.asarray(samples, dtype=float)
            n = max(1, int(len(arr) * top_pct))
            sorted_idx = np.argsort(arr)
            top_vals = arr[sorted_idx[-n:]]
            bot_vals = arr[sorted_idx[:n]]
            top_mean = float(np.mean(top_vals))
            bot_mean = float(np.mean(bot_vals))
            dc_est = (top_mean + bot_mean) / 2.0
            ptp_est = top_mean - bot_mean
            return ptp_est, top_mean, bot_mean

        ptp1, top1, bot1 = robust_ptp(ch1, top_pct=0.05)
        ptp2, top2, bot2 = robust_ptp(ch2, top_pct=0.05) if ch2 is not None else (None, None, None)

        # 抛物线插值函数（用于在谱峰周围做精确频率估计）
        def parabolic_peak(freqs, mags, peak_idx):
            if peak_idx <= 0 or peak_idx >= len(mags) - 1:
                return float(freqs[peak_idx]), float(mags[peak_idx])
            alpha = mags[peak_idx - 1]
            beta = mags[peak_idx]
            gamma = mags[peak_idx + 1]
            denom = (alpha - 2.0 * beta + gamma)
            if denom == 0:
                p = 0.0
            else:
                p = 0.5 * (alpha - gamma) / denom  # 偏移（单位：bin）
            df = freqs[1] - freqs[0] if len(freqs) > 1 else 0.0
            freq_est = freqs[peak_idx] + p * df
            mag_est = beta - 0.25 * (alpha - gamma) * p
            return float(freq_est), float(mag_est)

        # 主频（排除直流分量），并使用抛物线插值提升精度
        def dominant_freq_and_est(mag_arr):
            if mag_arr is None or len(mag_arr) < 3:
                return 0.0, 0.0, 0  # freq, mag, peak_idx
            # 排除直流分量（索引0）
            peak_idx = int(np.argmax(mag_arr[1:]) + 1)
            freq_est, mag_est = parabolic_peak(f, mag_arr, peak_idx)
            return float(freq_est), float(mag_est), peak_idx

        freq1, magest1, peak_idx1 = dominant_freq_and_est(mag1)
        if mag2 is not None:
            freq2, magest2, peak_idx2 = dominant_freq_and_est(mag2)
        else:
            freq2, magest2, peak_idx2 = None, None, None

        # 谐波标注（基于检测到的 base_freq）
        base_freq = freq1 if freq1 and freq1 > 0.0 else (freq2 if freq2 and freq2 > 0.0 else None)
        harmonics = []
        if base_freq:
            for n in range(1, self.harmonic_count + 1):
                hf = n * base_freq
                if hf > f[-1]:
                    break
                idx = np.argmin(np.abs(f - hf))
                amp = float(mag1[idx]) if idx < len(mag1) else 0.0
                harmonics.append((n, float(f[idx]), amp))

        # 在计算完成前后加入诊断信息
        # 在返回结果中包含用于调试的采样率与是否可能发生混叠的提示
        nyquist = fs / 2.0
        alias_warning = False
        # 如果检测到估计的基频超过 nyquist，标记混叠警告
        if base_freq and base_freq > nyquist:
            alias_warning = True

        # ---------- 新增：基于时域统计占空比与高/低电平时间 ----------
        duration_sec = float(N) / float(fs) if fs > 0 else float(N)
        def duty_stats(samples, top_mean, bot_mean):
            if samples is None or len(samples) == 0:
                return {'duty_cycle': None, 'high_time': None, 'low_time': None,
                        'mean_high': None, 'mean_low': None}
            arr = np.asarray(samples, dtype=float)
            # 阈值：top/bot 均值存在时用其平均，否则退回到样本均值
            if top_mean is not None and bot_mean is not None:
                thresh = (top_mean + bot_mean) / 2.0
            else:
                thresh = float(np.mean(arr))
            high_mask = arr > thresh
            duty = float(np.mean(high_mask))
            high_time = duty * duration_sec
            low_time = max(0.0, duration_sec - high_time)
            mean_high = float(np.mean(arr[high_mask])) if np.any(high_mask) else None
            mean_low = float(np.mean(arr[~high_mask])) if np.any(~high_mask) else None
            return {'duty_cycle': duty, 'high_time': high_time, 'low_time': low_time,
                    'mean_high': mean_high, 'mean_low': mean_low}

        stats1 = duty_stats(ch1, top1, bot1)
        # 只计算并返回通道1的占空比/高低电平时间与均值
        _ = duty_stats(ch2, top2, bot2) if ch2 is not None else None  # 保持原有计算路径（非必须）

        return {
             'f': f/0.8,
             'mag1': mag1,
             'mag2': mag2,
             'ptp1': ptp1,
             'ptp2': ptp2,
             'top1': top1,
             'bot1': bot1,
             'top2': top2,
             'bot2': bot2,
             'freq1': freq1/0.8,
             'freq2': freq2/0.8,
             'freq_est1': magest1 and freq1/0.8,
             'mag_est1': magest1,
             'freq_est2': magest2 and freq2/0.8,
             'mag_est2': magest2,
             'fs_used': fs,
             'N': N,
             'Nfft': Nfft,
             'peak_idx1': peak_idx1,
             'peak_idx2': peak_idx2,
             'alias_warning': alias_warning,
             'raw_sample_rate_input': getattr(self, '_raw_sample_rate', None),
             'dc1': dc1,
             'dc2': dc2,
             'duty1': stats1['duty_cycle'],
             'high_time1': stats1['high_time'],
             'low_time1': stats1['low_time'],
             'mean_high1': stats1['mean_high'],
             'mean_low1': stats1['mean_low']
            #  **extra_duty
         }