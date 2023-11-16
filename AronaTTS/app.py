import json
import os
import re
import librosa
import numpy as np
import torch
from torch import no_grad, LongTensor
import commons
import utils
import gradio as gr
from models import SynthesizerTrn
from text import text_to_sequence, _clean_text
from mel_processing import spectrogram_torch

limitation = os.getenv("SYSTEM") == "spaces"  # limit text and audio length in huggingface spaces

max_length = 1000

def get_text(text, hps, is_phoneme):
    text_norm = text_to_sequence(text, hps.symbols, [] if is_phoneme else hps.data.text_cleaners)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = LongTensor(text_norm)
    return text_norm


def create_tts_fn(model, hps, speaker_ids):
    def tts_fn(text, speaker, speed, is_phoneme):
        if limitation:
            text_len = len(text)
            max_len = max_length
            if text_len > max_len:
                return "Error: Text is too long", None

        speaker_id = speaker_ids[speaker]
        stn_tst = get_text(text, hps, is_phoneme)
        with no_grad():
            x_tst = stn_tst.unsqueeze(0)
            x_tst_lengths = LongTensor([stn_tst.size(0)])
            sid = LongTensor([speaker_id])
            audio = model.infer(x_tst, x_tst_lengths, sid=sid, noise_scale=.667, noise_scale_w=0.8,
                                length_scale=1.0 / speed)[0][0, 0].data.cpu().float().numpy()
        del stn_tst, x_tst, x_tst_lengths, sid
        return "Success", (hps.data.sampling_rate, audio)

    return tts_fn


def create_to_phoneme_fn(hps):
    def to_phoneme_fn(text):
        return _clean_text(text, hps.data.text_cleaners) if text != "" else ""

    return to_phoneme_fn


css = """
        #advanced-btn {
            color: white;
            border-color: black;
            background: black;
            font-size: .7rem !important;
            line-height: 19px;
            margin-top: 24px;
            margin-bottom: 12px;
            padding: 2px 8px;
            border-radius: 14px !important;
        }
        #advanced-options {
            display: none;
            margin-bottom: 20px;
        }
"""


if __name__ == '__main__':
    models_tts = []
    name = '아로나(アロナ) TTS'
    lang = '日本語 (Japanese)'
    example = 'おはようございます、先生。'
    config_path = f"saved_model/config.json"
    model_path = f"saved_model/model.pth"
    cover_path = f"saved_model/cover.png"
    hps = utils.get_hparams_from_file(config_path)
    model = SynthesizerTrn(
        len(hps.symbols),
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        **hps.model)
    utils.load_checkpoint(model_path, model, None)
    model.eval()
    speaker_ids = [0]
    speakers = [name]

    t = 'vits'
    models_tts.append((name, cover_path, speakers, lang, example,
                        create_tts_fn(model, hps, speaker_ids),
                        create_to_phoneme_fn(hps)))

    app = gr.Blocks(css=css)

    with app:
        gr.Markdown("![visitor badge](https://visitor-badge.glitch.me/badge?page_id=kdrkdrkdr.AronaTTS)\n\n")
        
        for i, (name, cover_path, speakers, lang, example, tts_fn, to_phoneme_fn) in enumerate(models_tts):

            with gr.Column():
                gr.Markdown(f"## {name}\n\n"
                            f"![cover](file/{cover_path})\n\n"
                            f"lang: {lang}")
                tts_input1 = gr.TextArea(label=f"Text ({max_length} words limitation)", value=example,
                                            elem_id=f"tts-input{i}")
                tts_input2 = gr.Dropdown(label="Speaker", choices=speakers,
                                            type="index", value=speakers[0])
                tts_input3 = gr.Slider(label="Speed", value=1, minimum=0.5, maximum=2, step=0.1)
                
                tts_submit = gr.Button("Generate", variant="primary")
                tts_output1 = gr.Textbox(label="Output Message")
                tts_output2 = gr.Audio(label="Output Audio", elem_id="tts-audio")
                tts_submit.click(tts_fn, inputs=[tts_input1, tts_input2, tts_input3],
                                    outputs=[tts_output1, tts_output2], api_name="tts")
                
    app.queue().launch(server_name = "0.0.0.0")
