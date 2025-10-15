import os
import json
import uuid
import datetime as dt
from pathlib import Path

import numpy as np
import torch
import soundfile as sf
from scipy.signal import butter, lfilter, wiener

# --- Constants ---
ROOT_PATH = Path(__file__).parent
MODEL_FILE = ROOT_PATH / "silero_tts_ru_v3_1_ru.pt"
SETTINGS_FILE = ROOT_PATH / "sound.json"
OUTPUTS_DIR = ROOT_PATH / "outputs"
LANGUAGE = 'ru'
MODEL_ID = 'v3_1_ru'

# --- Optional Packages ---
try:
    import noisereduce as nr
    _HAS_NOISEREDUCE = True
except ImportError:
    _HAS_NOISEREDUCE = False

try:
    from deepfilternet import DeepFilterNet
    _HAS_DFN = True
except ImportError:
    _HAS_DFN = False

# --- Global Objects ---
_tts_model = None
_dfn_model = None
_device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# --- Utility Functions ---
def _random_basename(prefix: str = "tts") -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd = uuid.uuid4().hex[:6]
    return f"{prefix}_{stamp}_{rnd}"

def _load_settings():
    if not SETTINGS_FILE.exists():
        raise FileNotFoundError(f"Settings file not found at {SETTINGS_FILE}")
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- DSP Blocks ---
def _normalize(audio: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) + eps
    return (audio / peak).astype(np.float32)

def _butter_lowpass_filter(data: np.ndarray, cutoff=9000, sr=48000, order=4) -> np.ndarray:
    if cutoff <= 0 or cutoff >= sr // 2: return data.astype(np.float32)
    nyq = 0.5 * sr
    normal_cutoff = min(max(cutoff / nyq, 1e-4), 0.999)
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return lfilter(b, a, data).astype(np.float32)

def _smooth_fade(audio: np.ndarray, sr: int, fade_ms: int = 20) -> np.ndarray:
    fade_len = max(1, int(fade_ms * sr / 1000))
    if fade_len * 2 >= audio.size: return audio
    fade = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
    audio[:fade_len] *= fade
    audio[-fade_len:] *= fade[::-1]
    return audio

def _moving_average(audio: np.ndarray, k: int = 5) -> np.ndarray:
    if k <= 1: return audio
    kernel = np.ones(k, dtype=np.float32) / k
    return np.convolve(audio, kernel, mode='same').astype(np.float32)

def _apply_volume_gain(wave: np.ndarray, gain_db: float) -> np.ndarray:
    if abs(gain_db) < 1e-6: return wave
    factor = 10.0 ** (gain_db / 20.0)
    return np.clip(wave.astype(np.float32) * factor, -1.0, 1.0)

def _time_stretch_linear(wave: np.ndarray, rate: float) -> np.ndarray:
    if abs(rate - 1.0) < 1e-3 or wave.size == 0: return wave
    n = wave.shape[0]
    new_len = max(1, int(n / rate))
    x_old = np.linspace(0, 1, n, dtype=np.float32)
    x_new = np.linspace(0, 1, new_len, dtype=np.float32)
    return np.interp(x_new, x_old, wave).astype(np.float32)

def _prepend_append_silence(wave: np.ndarray, sr: int, pre_ms: int, post_ms: int) -> np.ndarray:
    pre = np.zeros(int(sr * pre_ms / 1000), dtype=np.float32) if pre_ms > 0 else np.zeros(0, dtype=np.float32)
    post = np.zeros(int(sr * post_ms / 1000), dtype=np.float32) if post_ms > 0 else np.zeros(0, dtype=np.float32)
    return np.concatenate([pre, wave, post], axis=0)

def _butter_filter(sig, sr, cutoff, btype, order=4):
    nyq = 0.5 * sr
    wn = min(max(cutoff / nyq, 1e-4), 0.999)
    b, a = butter(order, wn, btype=btype, analog=False)
    return lfilter(b, a, sig).astype(np.float32)

def _soft_limiter(x: np.ndarray, drive: float = 1.2):
    return (np.tanh(drive * x) / np.tanh(drive)).astype(np.float32)

def _de_esser(audio: np.ndarray, sr: int, **kwargs) -> np.ndarray:
    if audio.ndim > 1: audio = audio.mean(axis=1)
    high = _butter_filter(audio, sr, kwargs.get('f_split', 4500), btype='high')
    low = audio - high
    env = np.abs(high)
    k = max(1, int(sr * kwargs.get('release_ms', 25) / 1000))
    kernel = np.ones(k, dtype=np.float32) / k
    env = np.convolve(env, kernel, mode='same').astype(np.float32)
    thresh = kwargs.get('thresh', 0.07)
    over = np.maximum(0.0, env - thresh)
    gain = 1.0 / (1.0 + (over / (thresh + 1e-6)) * (kwargs.get('ratio', 6.0) - 1.0))
    high_tamed = high * gain
    return (low + high_tamed).astype(np.float32)

def _dfn_denoise(audio: np.ndarray, sr: int) -> np.ndarray:
    global _dfn_model
    if not _HAS_DFN: return audio.astype(np.float32)
    if _dfn_model is None: _dfn_model = DeepFilterNet()
    if audio.ndim > 1: audio = audio.mean(axis=1)
    return np.asarray(_dfn_model.filter(audio.astype(np.float32, copy=False), sr), dtype=np.float32)

# --- Core Logic ---
def _ensure_model_loaded():
    global _tts_model
    if _tts_model is not None: return

    print("Loading SileroTTS model...")
    if not MODEL_FILE.is_file():
        print(f"Model file not found at {MODEL_FILE}, downloading...")
        torch.hub.download_url_to_file(
            f'https://models.silero.ai/models/tts/{LANGUAGE}/{MODEL_ID}.pt',
            MODEL_FILE
        )
    _tts_model = torch.package.PackageImporter(str(MODEL_FILE)).load_pickle("tts_models", "model")
    _tts_model.to(_device)
    print("SileroTTS model loaded.")

def _postprocess_audio(audio: np.ndarray, sr: int, pp_settings: dict) -> np.ndarray:
    if not pp_settings.get('enable', True):
        return audio.astype(np.float32)

    audio = _normalize(audio)
    if pp_settings.get('use_dfn', True) and _HAS_DFN:
        try: audio = _dfn_denoise(audio, sr)
        except Exception as e: print(f"DFN failed: {e}")
    if pp_settings.get('use_nr', True) and _HAS_NOISEREDUCE:
        try: audio = nr.reduce_noise(y=audio.astype(np.float32), sr=sr)
        except Exception as e: print(f"Noisereduce failed: {e}")

    audio = _de_esser(audio, sr)
    try: audio = wiener(audio).astype(np.float32)
    except Exception as e: print(f"Wiener filter failed: {e}")

    audio = _smooth_fade(audio, sr, fade_ms=pp_settings.get('fade_ms', 20))
    audio = _butter_lowpass_filter(audio, cutoff=pp_settings.get('lp_cutoff', 9000), sr=sr)
    if (k := pp_settings.get('smooth_k', 5)) > 1:
        audio = _moving_average(audio, k=int(k))

    audio = _soft_limiter(audio, drive=1.12)
    audio = _normalize(audio)
    return audio.astype(np.float32)

async def synthesize_text(text: str) -> str:
    """
    Main function to synthesize text to an audio file.
    Loads settings, ensures model is loaded, runs TTS, post-processes,
    and saves the file.
    Returns the web-accessible path to the audio file.
    """
    try:
        settings = _load_settings()
        tts_settings = settings.get('tts_settings', {})
        pp_settings = settings.get('post_processing', {})
        effects = settings.get('effects', {})

        _ensure_model_loaded()

        # Limit threads to avoid overwhelming the CPU on servers
        torch.set_num_threads(max(1, os.cpu_count() // 2))

        audio = _tts_model.apply_tts(
            text=text.strip(),
            speaker=tts_settings.get('speaker', 'aidar'),
            sample_rate=tts_settings.get('sample_rate', 48000),
            put_accent=tts_settings.get('put_accent', True),
            put_yo=tts_settings.get('put_yo', True)
        ).cpu().numpy().astype(np.float32)

        sample_rate = tts_settings.get('sample_rate', 48000)

        # Apply effects
        audio = _time_stretch_linear(audio, effects.get('speed', 1.0))
        audio = _prepend_append_silence(audio, sample_rate, effects.get('pre_sil_ms', 0), effects.get('post_sil_ms', 0))
        audio = _apply_volume_gain(audio, effects.get('gain_db', 0.0))

        # Post-process
        audio = _postprocess_audio(audio, sample_rate, pp_settings)

        # Save to file
        OUTPUTS_DIR.mkdir(exist_ok=True)
        base_name = _random_basename("tts")
        output_path = OUTPUTS_DIR / f"{base_name}.wav"

        sf.write(output_path, audio, sample_rate, format='WAV')

        # Return the path that the frontend can use
        return f"/sound/outputs/{base_name}.wav"

    except Exception as e:
        print(f"Error during TTS synthesis: {e}")
        # Re-raise to be caught by the API endpoint
        raise e
