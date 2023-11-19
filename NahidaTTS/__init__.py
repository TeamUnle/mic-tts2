import numpy as np
import pydub
from torch import no_grad, LongTensor


from NahidaTTS import utils
from NahidaTTS.models import SynthesizerTrn
from NahidaTTS.text import text_to_sequence
from NahidaTTS import commons

def get_text(text, hps, is_phoneme):
    text_norm = text_to_sequence(text, hps.symbols, [] if is_phoneme else hps.data.text_cleaners)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = LongTensor(text_norm)
    return text_norm

def create_tts_fn(model, hps, speaker_ids):
    def tts_fn(text, speaker, speed, path, is_phoneme=False):
        speaker_id = speaker_ids[speaker]
        stn_tst = get_text(text, hps, is_phoneme)
        with no_grad():
            x_tst = stn_tst.unsqueeze(0)
            x_tst_lengths = LongTensor([stn_tst.size(0)])
            sid = LongTensor([speaker_id])
            audio = model.infer(x_tst, x_tst_lengths, sid=sid, noise_scale=.667, noise_scale_w=0.8,
                                length_scale=1.0 / speed)[0][0, 0].data.cpu().float().numpy()
        del stn_tst, x_tst, x_tst_lengths, sid
        
        # convert to 16-bit wav
        audio = audio.astype(np.float32)
        audio = audio / np.max(np.abs(audio))
        audio = audio * 32767 * 0.9
        audio = audio.astype(np.int16)
        # conver wav to mp3
        audio = pydub.AudioSegment(audio.tobytes(), frame_rate=hps.data.sampling_rate, sample_width=2, channels=1)
        audio = audio.set_frame_rate(24000)
        audio = audio.set_channels(1)
        audio = audio.set_sample_width(2)
        # can i change bitrate to 32kbps?
        audio.export(path, format='mp3', bitrate='32k')
        
    return tts_fn

def get_tts(model_path, config_path):
    hps = utils.get_hparams_from_file(config_path)
    model = SynthesizerTrn(
        len(hps.symbols),
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        **hps.model)
    utils.load_checkpoint(model_path, model, None)
    model.eval()
    return create_tts_fn(model, hps, [0])

__all__ = [
    "get_tts"
]